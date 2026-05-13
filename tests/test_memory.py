"""Tests for the synthesis_engine three-tier memory architecture.

Run modes:
  - Default: most tests skip unless RAGBOT_MEMORY_TEST_URL is set to a
    reachable postgres DSN with pgvector installed.
  - Stub-implementation tests run without any DB and confirm the ABC is
    real (a fresh in-memory backend that implements only the interface
    passes the same shape of integration tests).

To exercise the live path:

    export RAGBOT_MEMORY_TEST_URL=postgresql://ragbot:ragbot_dev_password_change_me@127.0.0.1:5433/ragbot
    pytest tests/test_memory.py -v
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.memory import (  # noqa: E402
    AttributeValue,
    Entity,
    Memory,
    MemoryQuery,
    MemoryResult,
    Provenance,
    Relation,
    SessionMemory,
    UserMemory,
    consolidate_session,
    reset_memory,
    three_tier_retrieve,
)
from synthesis_engine.memory.base import require_provenance  # noqa: E402
from synthesis_engine.vectorstore import SearchHit  # noqa: E402


# ---------------------------------------------------------------------------
# Stub backend — proves the ABC is real
# ---------------------------------------------------------------------------


class StubMemory(Memory):
    """In-memory Memory implementation used to validate the ABC.

    Storage is two dicts and two lists. The stub does not implement
    bi-temporal supersession transactionally — that test is reserved
    for the live pgvector path — but it implements every other contract
    so the surface area of the ABC is exercised without a database.
    """

    backend_name = "stub"

    def __init__(self) -> None:
        self.entities: Dict[UUID, Entity] = {}
        self.relations: Dict[UUID, Relation] = {}
        self.sessions: Dict[str, SessionMemory] = {}
        self.users: Dict[str, UserMemory] = {}
        self.chunks: List[SearchHit] = []

    def upsert_entity(self, entity: Entity) -> Entity:
        existing = self.get_entity(
            workspace=entity.workspace, type=entity.type, name=entity.name
        )
        if existing is not None:
            merged = {**existing.attributes, **entity.attributes}
            new = existing.model_copy(update={"attributes": merged})
            self.entities[new.id] = new
            return new
        new = entity.model_copy(update={"id": uuid4()})
        self.entities[new.id] = new
        return new

    def get_entity(
        self,
        entity_id: Optional[UUID] = None,
        *,
        workspace: Optional[str] = None,
        type: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Entity]:
        if entity_id is not None:
            return self.entities.get(entity_id)
        for e in self.entities.values():
            if (
                e.workspace == workspace
                and e.type == type
                and e.name == name
            ):
                return e
        return None

    def list_entities(
        self,
        workspace: str,
        *,
        type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        rows = [
            e
            for e in self.entities.values()
            if e.workspace == workspace and (type is None or e.type == type)
        ]
        return rows[offset : offset + limit]

    def upsert_relation(
        self,
        relation: Relation,
        *,
        supersedes: Optional[UUID] = None,
    ) -> Relation:
        require_provenance(relation.provenance)
        if supersedes is not None:
            prior = self.relations.get(supersedes)
            if prior is None:
                raise ValueError(f"supersedes={supersedes!s} not found")
            self.relations[supersedes] = prior.model_copy(
                update={"validity_end": _utcnow()}
            )
        new = relation.model_copy(update={"id": uuid4()})
        if new.validity_start is None:
            new = new.model_copy(update={"validity_start": _utcnow()})
        self.relations[new.id] = new
        return new

    def get_relation(self, relation_id: UUID) -> Optional[Relation]:
        return self.relations.get(relation_id)

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
        frontier = set(seed_entity_ids)
        visited = set(seed_entity_ids)
        touched: List[Relation] = []
        for _ in range(depth):
            next_frontier = set()
            for r in self.relations.values():
                if r.workspace != workspace:
                    continue
                if relation_types and r.type not in relation_types:
                    continue
                if not _validity_match(r, validity_at):
                    continue
                if r.from_entity in frontier or r.to_entity in frontier:
                    touched.append(r)
                    next_frontier.add(r.from_entity)
                    next_frontier.add(r.to_entity)
            frontier = next_frontier - visited
            visited |= frontier
            if not frontier:
                break
        # Dedupe by relation id and limit
        seen = set()
        result: List[Relation] = []
        for r in touched:
            if r.id in seen:
                continue
            seen.add(r.id)
            result.append(r)
        return result[:limit]

    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        return self.sessions.get(session_id)

    def set_session(self, session: SessionMemory) -> SessionMemory:
        self.sessions[session.session_id] = session
        return session

    def get_user(self, user_id: str) -> Optional[UserMemory]:
        return self.users.get(user_id)

    def set_user(self, user: UserMemory) -> UserMemory:
        self.users[user.user_id] = user
        return user

    def search_vector(
        self,
        workspace: str,
        query_vector: List[float],
        *,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        return self.chunks[:limit]

    def search_three_tier(
        self,
        query: MemoryQuery,
        *,
        query_vector: Optional[List[float]] = None,
    ) -> List[MemoryResult]:
        return three_tier_retrieve(self, query, query_vector=query_vector)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _validity_match(r: Relation, validity_at: Optional[datetime]) -> bool:
    if validity_at is None:
        return r.validity_end is None
    start = r.validity_start or _utcnow()
    end = r.validity_end
    return start <= validity_at and (end is None or end > validity_at)


# ---------------------------------------------------------------------------
# ABC contract tests — run without DB on the stub
# ---------------------------------------------------------------------------


class TestStubBackendAgainstABC:
    """Pluggability: a stub Memory implementation passes the same shape
    of tests the pgvector backend does. Proves the abstraction is real."""

    def test_upsert_and_get_entity(self):
        m = StubMemory()
        prov = Provenance(source="test", confidence=1.0)
        e = m.upsert_entity(
            Entity(
                workspace="ws",
                type="person",
                name="Alice",
                attributes={
                    "role": AttributeValue(value="engineer", provenance=prov)
                },
            )
        )
        assert e.id is not None
        fetched = m.get_entity(e.id)
        assert fetched is not None
        assert fetched.name == "Alice"
        assert fetched.attributes["role"].value == "engineer"
        assert fetched.attributes["role"].provenance.source == "test"

    def test_relation_requires_provenance(self):
        m = StubMemory()
        prov = Provenance(source="test")
        alice = m.upsert_entity(Entity(workspace="ws", type="person", name="Alice"))
        bob = m.upsert_entity(Entity(workspace="ws", type="person", name="Bob"))
        # No provenance on the Relation construction should fail validation
        with pytest.raises(Exception):
            Relation(
                workspace="ws",
                from_entity=alice.id,
                to_entity=bob.id,
                type="knows",
            )
        # With provenance, the upsert succeeds
        r = m.upsert_relation(
            Relation(
                workspace="ws",
                from_entity=alice.id,
                to_entity=bob.id,
                type="knows",
                provenance=prov,
            )
        )
        assert r.id is not None
        assert r.validity_end is None

    def test_supersession_records_audit(self):
        m = StubMemory()
        prov = Provenance(source="test")
        alice = m.upsert_entity(Entity(workspace="ws", type="person", name="Alice"))
        company_a = m.upsert_entity(Entity(workspace="ws", type="org", name="A"))
        company_b = m.upsert_entity(Entity(workspace="ws", type="org", name="B"))
        r1 = m.upsert_relation(
            Relation(
                workspace="ws",
                from_entity=alice.id,
                to_entity=company_a.id,
                type="works_at",
                provenance=prov,
            )
        )
        # Supersede Alice's employer.
        r2 = m.upsert_relation(
            Relation(
                workspace="ws",
                from_entity=alice.id,
                to_entity=company_b.id,
                type="works_at",
                provenance=prov,
            ),
            supersedes=r1.id,
        )
        # Old relation has its validity_end set; new relation is current.
        assert m.get_relation(r1.id).validity_end is not None
        assert m.get_relation(r2.id).validity_end is None

    def test_three_tier_uses_session_and_graph(self):
        m = StubMemory()
        prov = Provenance(source="test")
        alice = m.upsert_entity(Entity(workspace="ws", type="person", name="Alice"))
        synthesis = m.upsert_entity(
            Entity(workspace="ws", type="concept", name="synthesis engineering")
        )
        m.upsert_relation(
            Relation(
                workspace="ws",
                from_entity=alice.id,
                to_entity=synthesis.id,
                type="authored",
                provenance=prov,
            )
        )
        m.set_session(
            SessionMemory(
                session_id="sess-1",
                user_id="u",
                workspace="ws",
                payload={"summary": "Alice is the lead on synthesis engineering."},
            )
        )
        results = three_tier_retrieve(
            m,
            MemoryQuery(
                text="Alice authored work on synthesis engineering",
                workspace="ws",
                user_id="u",
                session_id="sess-1",
            ),
        )
        tiers = {r.tier for r in results}
        assert "graph" in tiers
        assert "session" in tiers


# ---------------------------------------------------------------------------
# Live pgvector path — skipped unless the test DSN is set
# ---------------------------------------------------------------------------


_LIVE_DSN = os.environ.get("RAGBOT_MEMORY_TEST_URL")
live = pytest.mark.skipif(
    not _LIVE_DSN,
    reason=(
        "Set RAGBOT_MEMORY_TEST_URL to a postgres DSN to enable live memory tests. "
        "Example: postgresql://ragbot:ragbot_dev_password_change_me@127.0.0.1:5433/ragbot"
    ),
)


@pytest.fixture()
def memory_workspace(monkeypatch):
    """Live pgvector fixture. Sets env, runs migrations, isolates workspace."""

    from synthesis_engine.memory import get_memory

    monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "pgvector")
    monkeypatch.setenv("RAGBOT_DATABASE_URL", _LIVE_DSN or "")
    # The memory backend resolves the DSN through PgvectorBackend.from_env,
    # which reads the same env vars as the vector store.
    reset_memory()
    memory = get_memory(refresh=True)
    assert memory is not None
    workspace = f"memtest_{uuid.uuid4().hex[:10]}"
    yield memory, workspace
    # Cleanup: drop the workspace's data from both memory tables.
    try:
        with memory._vs._connection() as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute("DELETE FROM relations WHERE workspace = %s", (workspace,))
                cur.execute("DELETE FROM entities WHERE workspace = %s", (workspace,))
                cur.execute(
                    "DELETE FROM session_memory WHERE workspace = %s", (workspace,)
                )
            conn.commit()
    finally:
        reset_memory()


@live
class TestSchemaMigration:
    def test_migrations_apply_cleanly(self, memory_workspace):
        memory, _ = memory_workspace
        # Run migrations a second time; idempotency means no error and
        # no schema_migrations duplication.
        memory._vs._migrated = False  # type: ignore[attr-defined]
        memory._vs._run_migrations()  # type: ignore[attr-defined]
        # Spot-check: tables exist.
        with memory._vs._connection() as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema = 'public'
                       AND table_name IN
                           ('entities','relations','session_memory','user_memory')
                     ORDER BY table_name
                    """
                )
                tables = [r[0] for r in cur.fetchall()]
        assert tables == ["entities", "relations", "session_memory", "user_memory"]


@live
class TestPgvectorMemoryRoundtrip:
    def test_upsert_entity_with_provenance(self, memory_workspace):
        memory, ws = memory_workspace
        prov = Provenance(
            source="test:roundtrip",
            agent_run_id=UUID(int=42),
            message_id="msg-1",
            confidence=0.85,
        )
        ent = memory.upsert_entity(
            Entity(
                workspace=ws,
                type="person",
                name="Ada Lovelace",
                attributes={
                    "role": AttributeValue(value="programmer", provenance=prov),
                    "birth_year": AttributeValue(value=1815, provenance=prov),
                },
            )
        )
        assert ent.id is not None

        fetched = memory.get_entity(ent.id)
        assert fetched is not None
        assert fetched.name == "Ada Lovelace"
        assert fetched.attributes["role"].value == "programmer"
        assert fetched.attributes["role"].provenance.source == "test:roundtrip"
        assert fetched.attributes["role"].provenance.confidence == pytest.approx(0.85)
        assert fetched.attributes["birth_year"].value == 1815

    def test_upsert_relation_with_provenance_roundtrip(self, memory_workspace):
        memory, ws = memory_workspace
        prov = Provenance(source="test:rel", confidence=0.9)
        a = memory.upsert_entity(Entity(workspace=ws, type="person", name="Alice"))
        b = memory.upsert_entity(Entity(workspace=ws, type="org", name="Acme"))
        r = memory.upsert_relation(
            Relation(
                workspace=ws,
                from_entity=a.id,
                to_entity=b.id,
                type="works_at",
                provenance=prov,
                attributes={"role": "engineer"},
            )
        )
        assert r.id is not None
        roundtrip = memory.get_relation(r.id)
        assert roundtrip is not None
        assert roundtrip.provenance.source == "test:rel"
        assert roundtrip.provenance.confidence == pytest.approx(0.9)
        assert roundtrip.attributes.get("role") == "engineer"
        assert roundtrip.validity_end is None


@live
class TestTwoSessionThreeTier:
    def test_session_one_fact_surfaces_to_session_two_via_graph(self, memory_workspace):
        memory, ws = memory_workspace
        prov = Provenance(
            source="session:s1",
            agent_run_id=UUID(int=1),
            message_id="msg-foo",
            confidence=0.95,
        )

        # ---- Session 1: writes a fact about Alice. ----
        alice = memory.upsert_entity(
            Entity(workspace=ws, type="person", name="Alice")
        )
        synth = memory.upsert_entity(
            Entity(workspace=ws, type="concept", name="synthesis engineering")
        )
        memory.upsert_relation(
            Relation(
                workspace=ws,
                from_entity=alice.id,
                to_entity=synth.id,
                type="authored",
                provenance=prov,
                attributes={"published": "2025-11-09"},
            )
        )

        # ---- Session 2: queries about synthesis engineering. ----
        query = MemoryQuery(
            text="synthesis engineering Alice",
            workspace=ws,
            graph_depth=2,
            vector_k=0,        # skip vector tier in this test
            include_session=False,
            include_user=False,
        )
        results = memory.search_three_tier(query)

        graph_hits = [r for r in results if r.tier == "graph"]
        assert graph_hits, "expected at least one graph-tier hit"
        # The original provenance must be attached to the surfaced fact.
        sources = {h.provenance.source for h in graph_hits if h.provenance}
        assert "session:s1" in sources


@live
class TestTemporalSupersession:
    def test_supersede_and_validity_at_query(self, memory_workspace):
        memory, ws = memory_workspace
        prov = Provenance(source="test:temporal")
        alice = memory.upsert_entity(Entity(workspace=ws, type="person", name="Alice"))
        acme = memory.upsert_entity(Entity(workspace=ws, type="org", name="Acme"))
        beta = memory.upsert_entity(Entity(workspace=ws, type="org", name="Beta"))

        # t=1: Alice works at Acme.
        t1 = _utcnow() - timedelta(days=10)
        r1 = memory.upsert_relation(
            Relation(
                workspace=ws,
                from_entity=alice.id,
                to_entity=acme.id,
                type="works_at",
                validity_start=t1,
                provenance=prov,
            )
        )

        # t=2: Alice now works at Beta. Supersedes r1.
        r2 = memory.upsert_relation(
            Relation(
                workspace=ws,
                from_entity=alice.id,
                to_entity=beta.id,
                type="works_at",
                provenance=prov,
            ),
            supersedes=r1.id,
        )

        # No timestamp: current fact only.
        current = memory.query_graph(
            ws,
            seed_entity_ids=[alice.id],
            depth=1,
            relation_types=["works_at"],
        )
        assert len(current) == 1
        assert str(current[0].id) == str(r2.id)
        assert current[0].validity_end is None

        # validity_at = midway between t1 and now: Alice still at Acme.
        midpoint = t1 + timedelta(days=5)
        historical = memory.query_graph(
            ws,
            seed_entity_ids=[alice.id],
            depth=1,
            validity_at=midpoint,
            relation_types=["works_at"],
        )
        assert len(historical) == 1
        assert str(historical[0].id) == str(r1.id)

        # The 'supersedes' audit relation should also be present.
        audit = memory.query_graph(
            ws,
            seed_entity_ids=[alice.id, acme.id, beta.id],
            depth=1,
            relation_types=["supersedes"],
        )
        # The supersedes audit relation is recorded; its validity_end
        # is also closed in the same step. So under the "current only"
        # default it doesn't appear. With validity_at=now() it appears.
        # Either way, ensure the database recorded the row:
        with memory._vs._connection() as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM relations WHERE workspace = %s AND type = 'supersedes'",
                    (ws,),
                )
                count = cur.fetchone()[0]
        assert count >= 1


@live
class TestConsolidation:
    def test_consolidation_extracts_facts_with_session_provenance(
        self, memory_workspace
    ):
        memory, ws = memory_workspace
        # Plant a fake session with a transcript-shaped payload.
        session = SessionMemory(
            session_id="sess-consolidate-1",
            user_id="u-1",
            workspace=ws,
            payload={
                "messages": [
                    {
                        "role": "user",
                        "content": "Alice published synthesis engineering articles in November 2025.",
                    },
                    {
                        "role": "assistant",
                        "content": "Noted. Alice's writing on synthesis engineering is at rajiv.com.",
                    },
                ],
                "summary": "Alice authored several articles on synthesis engineering.",
            },
        )
        memory.set_session(session)

        # Deterministic extractor — we don't want to hit an LLM in CI.
        def extractor(text: str) -> Dict[str, Any]:
            assert "synthesis engineering" in text
            return {
                "entities": [
                    {"type": "person", "name": "Alice", "attributes": {"role": "author"}},
                    {"type": "concept", "name": "synthesis engineering"},
                ],
                "relations": [
                    {
                        "from": {"type": "person", "name": "Alice"},
                        "to": {"type": "concept", "name": "synthesis engineering"},
                        "type": "authored",
                        "confidence": 0.92,
                        "attributes": {"date": "2025-11"},
                    }
                ],
            }

        result = consolidate_session(
            memory,
            "sess-consolidate-1",
            ws,
            extractor=extractor,
        )
        assert len(result["entities"]) == 2
        assert len(result["relations"]) == 1

        # Verify the relation in the entity graph has session-pointing provenance.
        alice = memory.get_entity(workspace=ws, type="person", name="Alice")
        assert alice is not None
        rels = memory.query_graph(ws, seed_entity_ids=[alice.id], depth=1)
        authored = [r for r in rels if r.type == "authored"]
        assert authored, "expected a consolidated 'authored' relation"
        assert authored[0].provenance.source == "consolidation:session=sess-consolidate-1"
        assert authored[0].provenance.confidence == pytest.approx(0.92)


@live
class TestAPISurface:
    """Confirms the FastAPI router wires correctly to the backend."""

    def test_router_endpoints_with_test_client(self, memory_workspace, monkeypatch):
        memory, ws = memory_workspace
        from fastapi.testclient import TestClient

        # Build a minimal app to avoid the full ragbot startup.
        from fastapi import FastAPI
        from api.routers import memory as memory_router  # noqa: WPS433

        app = FastAPI()
        app.include_router(memory_router.router)
        client = TestClient(app)

        # Upsert
        payload = {
            "workspace": ws,
            "type": "person",
            "name": "Grace Hopper",
            "attributes": {
                "role": {
                    "value": "rear admiral",
                    "provenance": {"source": "test:api", "confidence": 1.0},
                }
            },
        }
        resp = client.post("/api/memory/entities", json=payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        eid = body["id"]
        assert body["name"] == "Grace Hopper"

        # List
        resp = client.get(f"/api/memory/entities?workspace={ws}")
        assert resp.status_code == 200
        listed = resp.json()
        assert any(e["id"] == eid for e in listed)

        # Detail
        resp = client.get(f"/api/memory/entities/{eid}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["entity"]["name"] == "Grace Hopper"

        # Session PUT/GET
        sess_payload = {
            "session_id": "sess-api-1",
            "user_id": "u",
            "workspace": ws,
            "payload": {"note": "test"},
        }
        resp = client.put("/api/memory/session/sess-api-1", json=sess_payload)
        assert resp.status_code == 200
        resp = client.get("/api/memory/session/sess-api-1")
        assert resp.status_code == 200
        assert resp.json()["payload"]["note"] == "test"
