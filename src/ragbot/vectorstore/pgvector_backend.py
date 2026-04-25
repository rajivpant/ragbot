"""Pgvector backend.

PostgreSQL with the ``pgvector`` extension. Implements the :class:`VectorStore`
interface with:

    * Vector ANN search via cosine distance (HNSW index).
    * Native full-text search via tsvector + GIN (replaces in-process BM25).
    * Single shared schema across workspaces, scoped by a ``workspace`` column.
    * Connection pooling via psycopg's ``ConnectionPool``.
    * Idempotent migration runner that applies SQL files in
      ``vectorstore/migrations/`` on first use.

The schema is documented in ``migrations/0001_initial.sql``.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import Point, SearchHit, VectorStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _resolve_database_url() -> Optional[str]:
    """Resolve the connection string from env vars.

    Priority:
      1. ``RAGBOT_DATABASE_URL``  (preferred — explicit, ragbot-scoped)
      2. ``DATABASE_URL``         (general fallback)
    """

    return (
        os.environ.get("RAGBOT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
    )


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


# ---------------------------------------------------------------------------
# Backend implementation
# ---------------------------------------------------------------------------


class PgvectorBackend(VectorStore):
    backend_name = "pgvector"

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 8) -> None:
        self.dsn = dsn
        self._pool = None
        self._pool_lock = threading.Lock()
        self._migrated = False
        self._min_size = min_size
        self._max_size = max_size

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "PgvectorBackend":
        """Build a backend from env vars, raising if no DSN is configured."""

        dsn = _resolve_database_url()
        if not dsn:
            raise RuntimeError(
                "Pgvector backend requires RAGBOT_DATABASE_URL (or DATABASE_URL). "
                "Set it to a postgres:// connection string and ensure the "
                "pgvector extension is installable on the target server."
            )
        backend = cls(dsn)
        # Eagerly validate connectivity + run migrations. Fail fast if the
        # database is unreachable so the caller can fall back to qdrant.
        backend._ensure_pool()
        backend._run_migrations()
        return backend

    # ------------------------------------------------------------------
    # pool / migrations
    # ------------------------------------------------------------------

    def _ensure_pool(self):
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is not None:
                return self._pool
            try:
                from psycopg_pool import ConnectionPool  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "psycopg[pool] is required for the pgvector backend. "
                    "Install it via the project's requirements.txt."
                ) from exc

            self._pool = ConnectionPool(
                conninfo=self.dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                kwargs={"autocommit": False},
                # Open lazily so import-time test failures don't blow up the
                # whole module; the first acquire() validates the connection.
                open=False,
            )
            self._pool.open()
            return self._pool

    def _connection(self):
        """Acquire a pooled connection with the pgvector type registered."""

        # Local import so the module loads even if pgvector isn't installed.
        from pgvector.psycopg import register_vector  # type: ignore

        pool = self._ensure_pool()
        ctx = pool.connection()
        # The context manager returned by `pool.connection()` will yield a
        # connection on entry; we wrap it so register_vector runs each time.
        return _VectorConn(ctx, register_vector)

    def _run_migrations(self) -> None:
        if self._migrated:
            return
        migrations = sorted(_migrations_dir().glob("*.sql"))
        if not migrations:
            logger.warning("No migrations found for pgvector backend.")
            self._migrated = True
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                for path in migrations:
                    sql = path.read_text()
                    logger.info("Applying migration %s", path.name)
                    cur.execute(sql)
            conn.commit()
        self._migrated = True

    # ------------------------------------------------------------------
    # interface implementations
    # ------------------------------------------------------------------

    def init_collection(self, workspace: str, vector_size: int = 384) -> bool:
        # Schema is shared; "init" simply ensures the workspace row exists
        # and migrations are applied. The vector_size argument is informational
        # (the schema fixes the embedding dimension; mismatches will error
        # when upserting, which is the right loud failure).
        try:
            self._run_migrations()
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO workspaces (name) VALUES (%s) "
                        "ON CONFLICT (name) DO NOTHING",
                        (workspace,),
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.error("PgvectorBackend.init_collection failed: %s", exc)
            return False

    def upsert_points(self, workspace: str, points: List[Point]) -> int:
        if not points:
            return 0
        # Group points by source_path so each unique document gets a single row.
        documents_by_path: Dict[str, Point] = {}
        for p in points:
            if not p.source_path:
                continue
            documents_by_path.setdefault(p.source_path, p)

        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    # Upsert documents, returning their ids.
                    doc_ids: Dict[str, int] = {}
                    for path, ref in documents_by_path.items():
                        cur.execute(
                            """
                            INSERT INTO documents
                                (workspace, source_path, filename, title,
                                 content_type, embedding_model, indexed_at)
                            VALUES (%s, %s, %s, %s, %s, %s, now())
                            ON CONFLICT (workspace, source_path) DO UPDATE
                                SET filename       = EXCLUDED.filename,
                                    title          = EXCLUDED.title,
                                    content_type   = EXCLUDED.content_type,
                                    embedding_model = EXCLUDED.embedding_model,
                                    indexed_at     = now()
                            RETURNING id
                            """,
                            (
                                workspace,
                                path,
                                ref.filename or os.path.basename(path),
                                ref.title,
                                ref.content_type,
                                ref.embedding_model,
                            ),
                        )
                        doc_ids[path] = cur.fetchone()[0]

                    # Upsert chunks. Re-indexing replaces existing chunk rows
                    # for a (workspace, chunk_uid) pair.
                    written = 0
                    for p in points:
                        document_id = doc_ids.get(p.source_path) if p.source_path else None
                        if document_id is None:
                            # No source file? Create a synthetic document row.
                            cur.execute(
                                """
                                INSERT INTO documents
                                    (workspace, source_path, filename, title,
                                     content_type, embedding_model, indexed_at)
                                VALUES (%s, %s, %s, %s, %s, %s, now())
                                ON CONFLICT (workspace, source_path) DO UPDATE
                                    SET indexed_at = now()
                                RETURNING id
                                """,
                                (
                                    workspace,
                                    p.chunk_uid,  # use chunk_uid as the synthetic source_path
                                    p.filename or "",
                                    p.title,
                                    p.content_type,
                                    p.embedding_model,
                                ),
                            )
                            document_id = cur.fetchone()[0]

                        cur.execute(
                            """
                            INSERT INTO chunks
                                (document_id, workspace, chunk_index, chunk_uid,
                                 text, char_start, char_end,
                                 embedding, embedding_model,
                                 content_type, filename, title, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (workspace, chunk_uid) DO UPDATE
                                SET text            = EXCLUDED.text,
                                    chunk_index     = EXCLUDED.chunk_index,
                                    char_start      = EXCLUDED.char_start,
                                    char_end        = EXCLUDED.char_end,
                                    embedding       = EXCLUDED.embedding,
                                    embedding_model = EXCLUDED.embedding_model,
                                    content_type    = EXCLUDED.content_type,
                                    filename        = EXCLUDED.filename,
                                    title           = EXCLUDED.title,
                                    metadata        = EXCLUDED.metadata,
                                    document_id     = EXCLUDED.document_id
                            """,
                            (
                                document_id,
                                workspace,
                                p.chunk_index,
                                p.chunk_uid,
                                p.text,
                                p.char_start,
                                p.char_end,
                                p.vector,
                                p.embedding_model,
                                p.content_type,
                                p.filename,
                                p.title,
                                _to_jsonb(p.metadata),
                            ),
                        )
                        written += 1
                conn.commit()
            return written
        except Exception as exc:
            logger.error("PgvectorBackend.upsert_points failed: %s", exc)
            return 0

    def search(
        self,
        workspace: str,
        query_vector: List[float],
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    if content_type:
                        cur.execute(
                            """
                            SELECT text,
                                   1 - (embedding <=> %s::vector) AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s AND content_type = %s
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (query_vector, workspace, content_type, query_vector, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT text,
                                   1 - (embedding <=> %s::vector) AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s
                            """,
                            (query_vector, workspace, query_vector, limit),
                        )
                    return [_row_to_hit(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("PgvectorBackend.search failed: %s", exc)
            return []

    def keyword_search(
        self,
        workspace: str,
        query: str,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        # Use websearch_to_tsquery: forgiving parser, handles bare strings
        # like "show me my biography" without forcing & between terms.
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    if content_type:
                        cur.execute(
                            """
                            SELECT text,
                                   ts_rank(text_search, websearch_to_tsquery('english', %s)) AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s
                              AND content_type = %s
                              AND text_search @@ websearch_to_tsquery('english', %s)
                            ORDER BY score DESC
                            LIMIT %s
                            """,
                            (query, workspace, content_type, query, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT text,
                                   ts_rank(text_search, websearch_to_tsquery('english', %s)) AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s
                              AND text_search @@ websearch_to_tsquery('english', %s)
                            ORDER BY score DESC
                            LIMIT %s
                            """,
                            (query, workspace, query, limit),
                        )
                    return [_row_to_hit(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("PgvectorBackend.keyword_search failed: %s", exc)
            return []

    def scroll_documents(
        self,
        workspace: str,
        limit: int = 1000,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    if content_type:
                        cur.execute(
                            """
                            SELECT text, 0.0 AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s AND content_type = %s
                            ORDER BY id
                            LIMIT %s
                            """,
                            (workspace, content_type, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT text, 0.0 AS score,
                                   chunk_uid, chunk_index, char_start, char_end,
                                   filename, title, content_type, metadata
                            FROM chunks
                            WHERE workspace = %s
                            ORDER BY id
                            LIMIT %s
                            """,
                            (workspace, limit),
                        )
                    return [_row_to_hit(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("PgvectorBackend.scroll_documents failed: %s", exc)
            return []

    def delete_collection(self, workspace: str) -> bool:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    # Cascade deletes chunks via FK ON DELETE CASCADE.
                    cur.execute("DELETE FROM documents WHERE workspace = %s", (workspace,))
                    cur.execute("DELETE FROM workspaces WHERE name = %s", (workspace,))
                conn.commit()
            return True
        except Exception as exc:
            logger.error("PgvectorBackend.delete_collection failed: %s", exc)
            return False

    def list_collections(self) -> List[str]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT workspace FROM chunks "
                        "UNION SELECT name FROM workspaces "
                        "ORDER BY 1"
                    )
                    return [row[0] for row in cur.fetchall()]
        except Exception as exc:
            logger.error("PgvectorBackend.list_collections failed: %s", exc)
            return []

    def get_collection_info(self, workspace: str) -> Optional[Dict[str, Any]]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT count(*) AS chunk_count,
                               count(DISTINCT document_id) AS document_count,
                               max(updated_at) AS last_indexed
                        FROM chunks
                        WHERE workspace = %s
                        """,
                        (workspace,),
                    )
                    row = cur.fetchone()
            if not row or row[0] == 0:
                return None
            return {
                "backend": self.backend_name,
                "workspace": workspace,
                "count": row[0],
                "document_count": row[1],
                "last_indexed": row[2].isoformat() if row[2] else None,
            }
        except Exception as exc:
            logger.error("PgvectorBackend.get_collection_info failed: %s", exc)
            return None

    def healthcheck(self) -> Dict[str, Any]:
        try:
            with self._connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                    row = cur.fetchone()
                    cur.execute("SELECT count(*) FROM workspaces")
                    workspaces_count = cur.fetchone()[0]
            return {
                "backend": self.backend_name,
                "ok": row is not None,
                "pgvector_version": row[0] if row else None,
                "workspaces": workspaces_count,
            }
        except Exception as exc:
            return {"backend": self.backend_name, "ok": False, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _VectorConn:
    """Thin wrapper that registers pgvector types on each acquired connection."""

    def __init__(self, ctx, register_vector):
        self._ctx = ctx
        self._register = register_vector
        self._conn = None

    def __enter__(self):
        self._conn = self._ctx.__enter__()
        self._register(self._conn)
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        return self._ctx.__exit__(exc_type, exc, tb)


def _row_to_hit(row) -> SearchHit:
    (
        text,
        score,
        chunk_uid,
        chunk_index,
        char_start,
        char_end,
        filename,
        title,
        content_type,
        metadata,
    ) = row
    md: Dict[str, Any] = dict(metadata or {})
    md.setdefault("text", text)
    md.setdefault("chunk_uid", chunk_uid)
    md.setdefault("chunk_index", chunk_index)
    md.setdefault("char_start", char_start)
    md.setdefault("char_end", char_end)
    md.setdefault("filename", filename)
    md.setdefault("title", title)
    md.setdefault("content_type", content_type)
    md.setdefault("source_file", md.get("source_file"))
    return SearchHit(text=text or "", score=float(score) if score is not None else 0.0, metadata=md)


def _to_jsonb(value: Any):
    """Adapt a Python dict for psycopg JSONB binding.

    psycopg requires explicit Jsonb wrapping; the default text adapter does
    not coerce dict → jsonb. Wrap here so call sites stay readable.
    """

    from psycopg.types.json import Jsonb  # type: ignore

    return Jsonb(value or {})
