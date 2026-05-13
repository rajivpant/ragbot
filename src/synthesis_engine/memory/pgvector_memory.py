"""Default Memory implementation against the pgvector backend.

Reuses the connection pool, migrations runner, and pgvector type
registration from ``synthesis_engine.vectorstore.pgvector_backend`` so a
single Postgres database holds Tier 1 (chunks), Tier 2 (entities +
relations), and Tier 3 (session + user memory) with one set of
operational concerns.

Atomic write path. Every multi-statement write (entity-with-attributes
upsert, relation-with-supersession) runs inside one transaction. Half-
state is not externally observable.

Provenance discipline. ``upsert_relation`` rejects calls that omit
:class:`Provenance`. Each entity attribute carries its own provenance
inside the jsonb attributes column so an attribute change records who
made the change.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from ..vectorstore import SearchHit
from ..vectorstore.pgvector_backend import PgvectorBackend
from .base import Memory, require_provenance
from .models import (
    AttributeValue,
    Entity,
    MemoryQuery,
    MemoryResult,
    Provenance,
    Relation,
    SessionMemory,
    UserMemory,
)

logger = logging.getLogger(__name__)


class PgvectorMemory(Memory):
    """Postgres + pgvector implementation of the Memory interface."""

    backend_name = "pgvector"

    def __init__(self, vector_backend: PgvectorBackend) -> None:
        self._vs = vector_backend
        # The vector backend's migration runner applies every SQL file in
        # the migrations/ directory in numerical order, including 0002
        # (memory tables). Triggering it here is a no-op if it has
        # already run.
        self._vs._run_migrations()

    @classmethod
    def from_env(cls) -> "PgvectorMemory":
        """Build memory from env vars; reuses the vector backend's DSN."""

        return cls(PgvectorBackend.from_env())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _jsonb(self, value: Any):
        from psycopg.types.json import Jsonb  # type: ignore

        return Jsonb(value or {})

    def _serialize_attributes(self, attributes: Dict[str, AttributeValue]) -> Dict[str, Any]:
        """Render the AttributeValue map into jsonb-storable shape."""

        out: Dict[str, Any] = {}
        for key, attr in attributes.items():
            out[key] = {
                "value": attr.value,
                "provenance": attr.provenance.model_dump(mode="json"),
                "updated_at": (attr.updated_at or _utcnow()).isoformat(),
            }
        return out

    def _deserialize_attributes(self, raw: Any) -> Dict[str, AttributeValue]:
        if not raw:
            return {}
        out: Dict[str, AttributeValue] = {}
        for key, entry in dict(raw).items():
            if not isinstance(entry, dict) or "value" not in entry:
                # Tolerate legacy shapes where attributes were plain
                # values without provenance — wrap them with a "legacy"
                # provenance marker so the interface stays uniform.
                out[key] = AttributeValue(
                    value=entry,
                    provenance=Provenance(source="legacy:unannotated"),
                )
                continue
            prov_raw = entry.get("provenance") or {"source": "legacy:unannotated"}
            out[key] = AttributeValue(
                value=entry["value"],
                provenance=Provenance.model_validate(prov_raw),
                updated_at=_parse_ts(entry.get("updated_at")),
            )
        return out

    # ------------------------------------------------------------------
    # Entities
    # ------------------------------------------------------------------

    def upsert_entity(self, entity: Entity) -> Entity:
        attrs = self._serialize_attributes(entity.attributes)
        emb = entity.embedding  # list[float] or None
        try:
            with self._vs._connection() as conn:
                with conn.cursor() as cur:
                    # Upsert with a server-side merge of the attributes
                    # jsonb. Existing keys not present in the incoming
                    # payload are preserved; keys in the incoming payload
                    # overwrite the prior entry.
                    cur.execute(
                        """
                        INSERT INTO entities
                            (workspace, type, name, attributes, embedding)
                        VALUES (%s, %s, %s, %s, %s::vector)
                        ON CONFLICT (workspace, type, name) DO UPDATE
                            SET attributes = entities.attributes || EXCLUDED.attributes,
                                embedding  = COALESCE(EXCLUDED.embedding, entities.embedding)
                        RETURNING id, workspace, type, name, attributes,
                                  embedding::text, created_at, updated_at
                        """,
                        (
                            entity.workspace,
                            entity.type,
                            entity.name,
                            self._jsonb(attrs),
                            emb,
                        ),
                    )
                    row = cur.fetchone()
                conn.commit()
            return _row_to_entity(row)
        except Exception as exc:
            logger.error("upsert_entity failed: %s", exc)
            raise

    def get_entity(
        self,
        entity_id: Optional[UUID] = None,
        *,
        workspace: Optional[str] = None,
        type: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Entity]:
        sql = (
            "SELECT id, workspace, type, name, attributes, embedding::text, "
            "       created_at, updated_at "
            "FROM entities "
        )
        params: List[Any] = []
        if entity_id is not None:
            sql += "WHERE id = %s"
            params.append(str(entity_id))
        else:
            if workspace is None or type is None or name is None:
                raise ValueError(
                    "get_entity requires either entity_id or "
                    "(workspace, type, name)."
                )
            sql += "WHERE workspace = %s AND type = %s AND name = %s"
            params.extend([workspace, type, name])
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return _row_to_entity(row) if row else None

    def list_entities(
        self,
        workspace: str,
        *,
        type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        sql = (
            "SELECT id, workspace, type, name, attributes, embedding::text, "
            "       created_at, updated_at "
            "FROM entities WHERE workspace = %s"
        )
        params: List[Any] = [workspace]
        if type is not None:
            sql += " AND type = %s"
            params.append(type)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [_row_to_entity(r) for r in rows]

    # ------------------------------------------------------------------
    # Relations (bi-temporal append-only)
    # ------------------------------------------------------------------

    def upsert_relation(
        self,
        relation: Relation,
        *,
        supersedes: Optional[UUID] = None,
    ) -> Relation:
        prov_dict = require_provenance(relation.provenance)
        try:
            with self._vs._connection() as conn:
                with conn.cursor() as cur:
                    # Inside one transaction:
                    #   1. (optional) close the prior fact's validity window
                    #   2. insert the new fact
                    #   3. (optional) insert a `supersedes` audit relation
                    if supersedes is not None:
                        cur.execute(
                            """
                            UPDATE relations
                               SET validity_end = COALESCE(validity_end, now())
                             WHERE id = %s AND workspace = %s
                             RETURNING id
                            """,
                            (str(supersedes), relation.workspace),
                        )
                        if cur.fetchone() is None:
                            raise ValueError(
                                f"supersedes={supersedes!s} not found in "
                                f"workspace={relation.workspace!r}"
                            )

                    cur.execute(
                        """
                        INSERT INTO relations
                            (workspace, from_entity, to_entity, type,
                             attributes, validity_start, validity_end,
                             provenance)
                        VALUES (%s, %s, %s, %s, %s, COALESCE(%s, now()), %s, %s)
                        RETURNING id, workspace, from_entity, to_entity, type,
                                  attributes, validity_start, validity_end,
                                  provenance, created_at
                        """,
                        (
                            relation.workspace,
                            str(relation.from_entity),
                            str(relation.to_entity),
                            relation.type,
                            self._jsonb(relation.attributes),
                            relation.validity_start,
                            relation.validity_end,
                            self._jsonb(prov_dict),
                        ),
                    )
                    new_row = cur.fetchone()

                    if supersedes is not None:
                        cur.execute(
                            """
                            INSERT INTO relations
                                (workspace, from_entity, to_entity, type,
                                 attributes, provenance)
                            SELECT %s, r.from_entity, r.to_entity,
                                   'supersedes',
                                   jsonb_build_object(
                                       'supersedes', %s::text,
                                       'superseded_by', %s::text
                                   ),
                                   %s
                              FROM relations r
                             WHERE r.id = %s
                            """,
                            (
                                relation.workspace,
                                str(supersedes),
                                str(new_row[0]),
                                self._jsonb(prov_dict),
                                str(supersedes),
                            ),
                        )
                conn.commit()
            return _row_to_relation(new_row)
        except Exception as exc:
            logger.error("upsert_relation failed: %s", exc)
            raise

    def get_relation(self, relation_id: UUID) -> Optional[Relation]:
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, workspace, from_entity, to_entity, type,
                           attributes, validity_start, validity_end,
                           provenance, created_at
                      FROM relations WHERE id = %s
                    """,
                    (str(relation_id),),
                )
                row = cur.fetchone()
        return _row_to_relation(row) if row else None

    def query_graph(
        self,
        workspace: str,
        *,
        seed_entity_ids: List[UUID],
        depth: int = 2,
        validity_at: Optional[datetime] = None,
        relation_types: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Relation]:
        if not seed_entity_ids:
            return []
        seeds = [str(s) for s in seed_entity_ids]

        # Validity predicate, expressed as a SQL fragment + params list.
        if validity_at is None:
            validity_clause = "r.validity_end IS NULL"
            validity_params: List[Any] = []
        else:
            validity_clause = (
                "r.validity_start <= %s AND "
                "(r.validity_end IS NULL OR r.validity_end > %s)"
            )
            validity_params = [validity_at, validity_at]

        type_clause = ""
        type_params: List[Any] = []
        if relation_types:
            type_clause = " AND r.type = ANY(%s::text[])"
            type_params = [list(relation_types)]

        # Recursive CTE for breadth-first traversal up to ``depth`` hops.
        # Each step joins relations whose from_entity matches a frontier
        # node, accumulating visited entities to avoid cycles. We collect
        # the relation ids touched and resolve them in a final SELECT so
        # the recursive step stays light.
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH RECURSIVE walk (entity_id, depth) AS (
                        SELECT id, 0
                          FROM entities
                         WHERE workspace = %s
                           AND id = ANY(%s::uuid[])
                        UNION
                        SELECT
                            CASE WHEN r.from_entity = w.entity_id
                                 THEN r.to_entity
                                 ELSE r.from_entity
                            END AS entity_id,
                            w.depth + 1 AS depth
                          FROM walk w
                          JOIN relations r
                            ON r.workspace = %s
                           AND (r.from_entity = w.entity_id OR r.to_entity = w.entity_id)
                           AND {validity_clause}
                           {type_clause}
                         WHERE w.depth < %s
                    ),
                    touched_relations AS (
                        SELECT DISTINCT r.id
                          FROM relations r
                          JOIN walk w
                            ON (r.from_entity = w.entity_id OR r.to_entity = w.entity_id)
                         WHERE r.workspace = %s
                           AND {validity_clause}
                           {type_clause}
                    )
                    SELECT id, workspace, from_entity, to_entity, type,
                           attributes, validity_start, validity_end,
                           provenance, created_at
                      FROM relations
                     WHERE id IN (SELECT id FROM touched_relations)
                     ORDER BY validity_start DESC
                     LIMIT %s
                    """,
                    [
                        workspace,
                        seeds,
                        workspace,
                        *validity_params,
                        *type_params,
                        depth,
                        workspace,
                        *validity_params,
                        *type_params,
                        limit,
                    ],
                )
                rows = cur.fetchall()
        return [_row_to_relation(r) for r in rows]

    # ------------------------------------------------------------------
    # Session memory
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, user_id, workspace, payload,
                           created_at, updated_at
                      FROM session_memory WHERE session_id = %s
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return SessionMemory(
            session_id=row[0],
            user_id=row[1],
            workspace=row[2],
            payload=dict(row[3] or {}),
            created_at=row[4],
            updated_at=row[5],
        )

    def set_session(self, session: SessionMemory) -> SessionMemory:
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO session_memory
                        (session_id, user_id, workspace, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE
                        SET user_id   = EXCLUDED.user_id,
                            workspace = EXCLUDED.workspace,
                            payload   = EXCLUDED.payload
                    RETURNING session_id, user_id, workspace, payload,
                              created_at, updated_at
                    """,
                    (
                        session.session_id,
                        session.user_id,
                        session.workspace,
                        self._jsonb(session.payload),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return SessionMemory(
            session_id=row[0],
            user_id=row[1],
            workspace=row[2],
            payload=dict(row[3] or {}),
            created_at=row[4],
            updated_at=row[5],
        )

    # ------------------------------------------------------------------
    # User memory
    # ------------------------------------------------------------------

    def get_user(self, user_id: str) -> Optional[UserMemory]:
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, payload, created_at, updated_at
                      FROM user_memory WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return UserMemory(
            user_id=row[0],
            payload=dict(row[1] or {}),
            created_at=row[2],
            updated_at=row[3],
        )

    def set_user(self, user: UserMemory) -> UserMemory:
        with self._vs._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_memory (user_id, payload)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                        SET payload = EXCLUDED.payload
                    RETURNING user_id, payload, created_at, updated_at
                    """,
                    (user.user_id, self._jsonb(user.payload)),
                )
                row = cur.fetchone()
            conn.commit()
        return UserMemory(
            user_id=row[0],
            payload=dict(row[1] or {}),
            created_at=row[2],
            updated_at=row[3],
        )

    # ------------------------------------------------------------------
    # Tier 1 — vector
    # ------------------------------------------------------------------

    def search_vector(
        self,
        workspace: str,
        query_vector: List[float],
        *,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        return self._vs.search(
            workspace, query_vector, limit=limit, content_type=content_type
        )

    # ------------------------------------------------------------------
    # Three-tier merged retrieval
    # ------------------------------------------------------------------

    def search_three_tier(
        self,
        query: MemoryQuery,
        *,
        query_vector: Optional[List[float]] = None,
    ) -> List[MemoryResult]:
        # Delegate the merge logic to the shared retrieval module so any
        # backend that implements the per-tier reads gets the same
        # ranking behavior. We import locally to avoid a cycle with the
        # package __init__.
        from .retrieval import three_tier_retrieve  # noqa: WPS433

        return three_tier_retrieve(self, query, query_vector=query_vector)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _row_to_entity(row) -> Entity:
    """Map a DB row in canonical column order to an Entity model."""

    (
        eid,
        workspace,
        type_,
        name,
        attributes,
        embedding_text,
        created_at,
        updated_at,
    ) = row
    embedding = _parse_pgvector_text(embedding_text)
    attrs = PgvectorMemory._deserialize_attributes_classmethod(attributes)
    return Entity(
        id=eid,
        workspace=workspace,
        type=type_,
        name=name,
        attributes=attrs,
        embedding=embedding,
        created_at=created_at,
        updated_at=updated_at,
    )


def _row_to_relation(row) -> Relation:
    (
        rid,
        workspace,
        from_entity,
        to_entity,
        type_,
        attributes,
        validity_start,
        validity_end,
        provenance,
        created_at,
    ) = row
    return Relation(
        id=rid,
        workspace=workspace,
        from_entity=from_entity,
        to_entity=to_entity,
        type=type_,
        attributes=dict(attributes or {}),
        validity_start=validity_start,
        validity_end=validity_end,
        provenance=Provenance.model_validate(provenance or {"source": "unknown"}),
        created_at=created_at,
    )


def _parse_pgvector_text(text: Any) -> Optional[List[float]]:
    """Turn a pgvector text-form ``'[1.0, 2.0, ...]'`` into ``list[float]``.

    pgvector ships a register_vector hook for psycopg, but we read the
    embedding ``::text`` from the DB so we don't need the adapter
    registered on the read path. Returns None when the value is NULL.
    """

    if text is None:
        return None
    if isinstance(text, list):
        return [float(x) for x in text]
    s = str(text).strip()
    if not s or s in ("None", "NULL"):
        return None
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    if not s:
        return []
    return [float(x.strip()) for x in s.split(",") if x.strip()]


# Helper bridge for the row-to-entity mapper since classmethods are hard
# to call from the module-level helper. Kept here so the deserialization
# logic stays a single source of truth.
def _deserialize_attributes(raw: Any) -> Dict[str, AttributeValue]:
    if not raw:
        return {}
    out: Dict[str, AttributeValue] = {}
    for key, entry in dict(raw).items():
        if not isinstance(entry, dict) or "value" not in entry:
            out[key] = AttributeValue(
                value=entry,
                provenance=Provenance(source="legacy:unannotated"),
            )
            continue
        prov_raw = entry.get("provenance") or {"source": "legacy:unannotated"}
        out[key] = AttributeValue(
            value=entry["value"],
            provenance=Provenance.model_validate(prov_raw),
            updated_at=_parse_ts(entry.get("updated_at")),
        )
    return out


# Expose the helper to ``_row_to_entity`` without paying for a method dispatch.
PgvectorMemory._deserialize_attributes_classmethod = staticmethod(_deserialize_attributes)
