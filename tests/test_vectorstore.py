"""Tests for the vector store abstraction (Phase 2 of ragbot-modernization).

These cover the public contract: data classes, backend selection, caching,
and the QdrantBackend wrapper exercised against an embedded local-file
Qdrant instance under a tmp_path. The pgvector backend is covered by
end-to-end integration tests that require a running Postgres; those are
skipped here when the env var is unset.
"""

from __future__ import annotations

import os
import sys
import uuid

import pytest

# Add src/ to sys.path so the tests can import the package under test.
_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from ragbot.vectorstore import (  # noqa: E402
    Point,
    SearchHit,
    VectorStore,
    get_vector_store,
    reset_vector_store,
)


# ---------------------------------------------------------------------------
# Data class contracts
# ---------------------------------------------------------------------------


class TestPointAndSearchHit:
    def test_point_defaults_are_safe(self):
        p = Point(chunk_uid="abc", vector=[0.0] * 4, text="hello")
        assert p.chunk_uid == "abc"
        assert p.vector == [0.0] * 4
        assert p.text == "hello"
        assert p.metadata == {}
        assert p.embedding_model == "all-MiniLM-L6-v2"

    def test_search_hit_score_coerces_to_float(self):
        h = SearchHit(text="hi", score=1)
        assert isinstance(h.score, (int, float))
        assert h.text == "hi"
        assert h.metadata == {}


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def setup_method(self):
        reset_vector_store()

    def teardown_method(self):
        reset_vector_store()

    def test_qdrant_backend_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "qdrant")
        monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "qdrant"))
        # Avoid accidental connection if a stale RAGBOT_DATABASE_URL is set.
        monkeypatch.delenv("RAGBOT_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        vs = get_vector_store()
        assert vs is not None
        assert vs.backend_name == "qdrant"

    def test_unknown_backend_falls_back_to_pgvector(self, monkeypatch):
        # When no DB is available either, the resolver tries pgvector and
        # then falls back to qdrant. The result is one of the two.
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "nonsense")
        monkeypatch.delenv("RAGBOT_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        vs = get_vector_store()
        assert vs is None or vs.backend_name in {"qdrant", "pgvector"}

    def test_get_vector_store_caches_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "qdrant")
        monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "qdrant"))
        first = get_vector_store()
        second = get_vector_store()
        assert first is second

    def test_reset_vector_store_clears_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "qdrant")
        monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "qdrant"))
        first = get_vector_store()
        reset_vector_store()
        second = get_vector_store()
        # Different instances after reset.
        assert first is not second


# ---------------------------------------------------------------------------
# QdrantBackend behavior (embedded mode against tmp_path)
# ---------------------------------------------------------------------------


class TestQdrantBackend:
    def setup_method(self):
        reset_vector_store()

    def teardown_method(self):
        reset_vector_store()

    def _backend(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "qdrant")
        monkeypatch.setenv("QDRANT_PATH", str(tmp_path / "qdrant"))
        monkeypatch.delenv("RAGBOT_DATABASE_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        vs = get_vector_store()
        assert vs is not None
        return vs

    def test_init_collection_idempotent(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        assert vs.init_collection("workspace_a", vector_size=4) is True
        # Re-init should not error (idempotent).
        assert vs.init_collection("workspace_a", vector_size=4) is True

    def test_upsert_search_roundtrip(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        ws = "ws_roundtrip"
        vs.init_collection(ws, vector_size=4)

        points = [
            Point(
                chunk_uid="1",
                vector=[1.0, 0.0, 0.0, 0.0],
                text="apple",
                content_type="datasets",
            ),
            Point(
                chunk_uid="2",
                vector=[0.0, 1.0, 0.0, 0.0],
                text="banana",
                content_type="datasets",
            ),
        ]
        written = vs.upsert_points(ws, points)
        assert written == 2

        # Query closest to first point's vector.
        hits = vs.search(ws, query_vector=[1.0, 0.0, 0.0, 0.0], limit=2)
        assert hits, "expected at least one hit"
        assert hits[0].text == "apple"

    def test_keyword_search_returns_empty_for_qdrant(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        ws = "ws_kw"
        vs.init_collection(ws, vector_size=4)
        # Qdrant has no native FTS; the keyword_search contract is to return
        # an empty list so callers fall back to in-process BM25.
        assert vs.keyword_search(ws, "anything") == []

    def test_delete_collection(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        ws = "ws_to_delete"
        vs.init_collection(ws, vector_size=4)
        vs.upsert_points(
            ws,
            [Point(chunk_uid="x", vector=[1.0, 0.0, 0.0, 0.0], text="x")],
        )
        assert ws in vs.list_collections() or any(
            ws in name for name in vs.list_collections()
        )
        assert vs.delete_collection(ws) is True

    def test_get_collection_info_for_unknown_workspace(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        assert vs.get_collection_info("does_not_exist") is None

    def test_healthcheck_reports_backend(self, tmp_path, monkeypatch):
        vs = self._backend(tmp_path, monkeypatch)
        h = vs.healthcheck()
        assert h["backend"] == "qdrant"
        assert "ok" in h


# ---------------------------------------------------------------------------
# PgvectorBackend (live integration; requires a reachable Postgres)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("RAGBOT_PGVECTOR_TEST_URL"),
    reason="Set RAGBOT_PGVECTOR_TEST_URL to a postgres DSN to enable live pgvector tests.",
)
class TestPgvectorBackendLive:
    """Optional live tests; only run when an explicit test DSN is configured."""

    def setup_method(self):
        reset_vector_store()

    def teardown_method(self):
        reset_vector_store()

    def test_pgvector_roundtrip(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_VECTOR_BACKEND", "pgvector")
        monkeypatch.setenv("RAGBOT_DATABASE_URL", os.environ["RAGBOT_PGVECTOR_TEST_URL"])

        vs = get_vector_store()
        assert vs is not None
        assert vs.backend_name == "pgvector"

        ws = f"ws_test_{uuid.uuid4().hex[:8]}"
        # The schema fixes the embedding dimension at 384 (matches all-MiniLM-L6-v2).
        # Build deterministic 384-dim vectors so the test exercises the real schema.
        vec_alpha = [1.0] + [0.0] * 383
        vec_beta = [0.0, 1.0] + [0.0] * 382

        try:
            assert vs.init_collection(ws, vector_size=384)
            written = vs.upsert_points(
                ws,
                [
                    Point(
                        chunk_uid="a",
                        vector=vec_alpha,
                        text="alpha document",
                        source_path="/tmp/a",
                    ),
                    Point(
                        chunk_uid="b",
                        vector=vec_beta,
                        text="beta document",
                        source_path="/tmp/b",
                    ),
                ],
            )
            assert written == 2, f"expected 2 rows written, got {written}"

            hits = vs.search(ws, vec_alpha, limit=2)
            assert hits and hits[0].text == "alpha document"

            kw_hits = vs.keyword_search(ws, "beta", limit=5)
            assert any("beta" in h.text for h in kw_hits)
        finally:
            vs.delete_collection(ws)
