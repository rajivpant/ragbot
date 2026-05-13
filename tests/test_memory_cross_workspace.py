"""Tests for cross-workspace three-tier retrieval.

Validates that ``three_tier_retrieve_multi``:

* fans out across workspaces under a shared token budget,
* clamps each workspace to ``per_workspace_floor`` minimum,
* redistributes unused budget from sparse workspaces to data-rich ones,
* tags every block with ``source_workspace``,
* preserves the per-workspace score-descending order produced by
  ``three_tier_retrieve``,
* tolerates a workspace whose ``three_tier_retrieve`` raises (the
  remaining workspaces still produce blocks).

The fake Memory implementation here is intentionally workspace-keyed —
it returns pre-built ``MemoryResult`` lists keyed by the
``MemoryQuery.workspace`` so the test fixture controls the exact mix.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.memory import (  # noqa: E402
    Memory,
    MemoryQuery,
    MemoryResult,
    RetrievedBlock,
    three_tier_retrieve_multi,
)
from synthesis_engine.memory.retrieval import _estimate_tokens  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Memory
# ---------------------------------------------------------------------------


class FakeMemory(Memory):
    """Returns deterministic per-workspace results for cross-workspace tests.

    The fake bypasses every other tier (graph, session, user) by returning
    an empty list for each. The single source of cross-workspace data is
    the vector-tier hits we pre-seed per workspace via
    ``set_workspace_results``.

    Because ``three_tier_retrieve_multi`` calls
    ``three_tier_retrieve(memory, query, ...)``, we override the public
    ``search_three_tier`` on this fake to short-circuit the retrieval —
    BUT ``three_tier_retrieve_multi`` doesn't call ``search_three_tier``;
    it calls ``three_tier_retrieve`` directly on the function. Hence we
    must keep ``three_tier_retrieve``'s call paths satisfied by overriding
    the per-tier methods themselves.
    """

    backend_name = "fake"

    def __init__(self) -> None:
        self._workspace_blocks: Dict[str, List[MemoryResult]] = {}
        self._raise_for: set = set()

    def set_workspace_results(
        self, workspace: str, results: List[MemoryResult]
    ) -> None:
        self._workspace_blocks[workspace] = list(results)

    def raise_for_workspace(self, workspace: str) -> None:
        """Make this workspace's per-tier reads raise to test partial failure."""
        self._raise_for.add(workspace)

    # ------------------------------------------------------------------
    # Memory ABC: only the surfaces three_tier_retrieve actually calls
    # need real implementations. The rest raise NotImplementedError so
    # tests don't accidentally exercise them.
    # ------------------------------------------------------------------

    def upsert_entity(self, entity):
        raise NotImplementedError

    def get_entity(self, entity_id=None, *, workspace=None, type=None, name=None):
        return None

    def list_entities(self, workspace, *, type=None, limit=100, offset=0):
        # The seed step in three_tier_retrieve calls list_entities; return
        # an empty list to skip the graph tier entirely.
        if workspace in self._raise_for:
            raise RuntimeError(f"simulated failure for workspace {workspace!r}")
        return []

    def upsert_relation(self, relation, *, supersedes=None):
        raise NotImplementedError

    def get_relation(self, relation_id):
        return None

    def query_graph(
        self,
        workspace,
        *,
        seed_entity_ids,
        depth=2,
        validity_at=None,
        relation_types=None,
        limit=200,
    ):
        return []

    def get_session(self, session_id):
        return None

    def set_session(self, session):
        return session

    def get_user(self, user_id):
        return None

    def set_user(self, user):
        return user

    def search_vector(
        self,
        workspace,
        query_vector,
        *,
        limit=10,
        content_type=None,
    ):
        return []

    def search_three_tier(self, query, *, query_vector=None):
        raise NotImplementedError


# We monkeypatch three_tier_retrieve at the call site to return our
# pre-seeded MemoryResult list per workspace, since wiring the FakeMemory
# through every internal helper would not let us assert per-workspace
# ranking deterministically.


def _patched_three_tier(memory, query, *, query_vector=None):
    fake: FakeMemory = memory  # type: ignore[assignment]
    if query.workspace in fake._raise_for:
        raise RuntimeError(f"simulated failure for {query.workspace!r}")
    return list(fake._workspace_blocks.get(query.workspace, []))


@pytest.fixture(autouse=True)
def _patch_three_tier(monkeypatch):
    """Replace the per-workspace retrieve with a deterministic stub."""
    import synthesis_engine.memory.retrieval as retrieval_mod

    monkeypatch.setattr(
        retrieval_mod, "three_tier_retrieve", _patched_three_tier
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block(text: str, score: float, tier: str = "vector") -> MemoryResult:
    return MemoryResult(
        tier=tier,
        score=score,
        text=text,
        metadata={},
    )


def _setup_workspaces(
    memory: FakeMemory,
    spec: Dict[str, List[MemoryResult]],
) -> None:
    for w, blocks in spec.items():
        memory.set_workspace_results(w, blocks)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSourceWorkspaceTagging:
    def test_each_block_carries_source_workspace_attribute(self):
        mem = FakeMemory()
        _setup_workspaces(
            mem,
            {
                "acme-news": [_block("news block 1", 0.9), _block("news block 2", 0.5)],
                "acme-user": [_block("user block 1", 0.8)],
            },
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="who owns the migration?",
            total_budget_tokens=10000,
            per_workspace_floor=100,
        )
        sources = {b.source_workspace for b in blocks}
        assert sources == {"acme-news", "acme-user"}
        for b in blocks:
            assert isinstance(b, RetrievedBlock)
            assert b.result.metadata.get("source_workspace") == b.source_workspace


class TestWorkspaceRankPreservation:
    def test_per_workspace_score_order_preserved(self):
        mem = FakeMemory()
        # Within each workspace, blocks are seeded score-descending (that's
        # what three_tier_retrieve emits) — we verify the multi function
        # preserves that order.
        _setup_workspaces(
            mem,
            {
                "acme-news": [
                    _block("news_high", 0.95),
                    _block("news_mid", 0.6),
                    _block("news_low", 0.2),
                ],
                "acme-user": [
                    _block("user_high", 0.9),
                    _block("user_low", 0.3),
                ],
            },
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="x",
            total_budget_tokens=10000,
            per_workspace_floor=100,
        )
        # Group by workspace, check score-descending within each group.
        per_ws: Dict[str, List[RetrievedBlock]] = {}
        for b in blocks:
            per_ws.setdefault(b.source_workspace, []).append(b)
        assert [b.text for b in per_ws["acme-news"]] == [
            "news_high",
            "news_mid",
            "news_low",
        ]
        assert [b.text for b in per_ws["acme-user"]] == [
            "user_high",
            "user_low",
        ]

    def test_workspace_rank_is_one_based(self):
        mem = FakeMemory()
        _setup_workspaces(
            mem,
            {
                "acme-news": [
                    _block("a", 0.9),
                    _block("b", 0.5),
                ],
            },
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news"],
            query="x",
            total_budget_tokens=10000,
            per_workspace_floor=100,
        )
        assert blocks[0].workspace_rank == 1
        assert blocks[1].workspace_rank == 2


class TestBudgetSplit:
    def test_equal_split_when_budget_is_ample(self):
        mem = FakeMemory()
        # Each workspace has plenty of content; budget is generous.
        _setup_workspaces(
            mem,
            {
                "acme-news": [_block("x" * 200, 0.9)],
                "acme-user": [_block("y" * 200, 0.8)],
                "beta-media": [_block("z" * 200, 0.7)],
            },
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user", "beta-media"],
            query="x",
            total_budget_tokens=900,
            per_workspace_floor=100,
        )
        # All three blocks fit; each costs ~50 tokens, budget is 900/3=300.
        sources = [b.source_workspace for b in blocks]
        assert sources.count("acme-news") == 1
        assert sources.count("acme-user") == 1
        assert sources.count("beta-media") == 1

    def test_per_workspace_floor_honored(self):
        mem = FakeMemory()
        # Budget is tight; floor guarantees each workspace gets a slot.
        _setup_workspaces(
            mem,
            {
                # The acme-news workspace has a single hot block.
                "acme-news": [_block("hot fact about migration", 0.95)],
                # acme-user has many blocks; only its top one should fit.
                "acme-user": [
                    _block("top user fact " + "x" * 100, 0.9),
                    _block("less-relevant user fact " + "x" * 100, 0.5),
                    _block("yet less " + "x" * 100, 0.4),
                ],
            },
        )
        # Tight budget. Floor of 50 should leave each ws with at least one
        # candidate slot.
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="x",
            total_budget_tokens=200,
            per_workspace_floor=50,
        )
        sources = {b.source_workspace for b in blocks}
        assert "acme-news" in sources
        assert "acme-user" in sources

    def test_unused_budget_redistributes_to_demanding_workspaces(self):
        mem = FakeMemory()
        # Workspace A produces NOTHING. Workspace B has many candidates.
        # B should consume A's unused budget and surface more blocks than
        # an equal-split allocation would have allowed.
        big_block_text = "data " * 60  # ~75 tokens via _estimate_tokens
        _setup_workspaces(
            mem,
            {
                "acme-news": [],  # zero candidates
                "acme-user": [
                    _block(big_block_text, 0.9 - i * 0.1) for i in range(8)
                ],
            },
        )
        # Generous total budget so the redistribution can land all of B's
        # blocks. Equal split would give 500 each (B caps at ~6 blocks);
        # with redistribution B should land all 8.
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="x",
            total_budget_tokens=1200,
            per_workspace_floor=100,
        )
        user_blocks = [b for b in blocks if b.source_workspace == "acme-user"]
        assert len(user_blocks) == 8, (
            f"expected redistribution to land all 8 blocks; got {len(user_blocks)}"
        )

    def test_no_redistribution_when_all_workspaces_under_demand(self):
        mem = FakeMemory()
        _setup_workspaces(
            mem,
            {
                "acme-news": [_block("a", 0.9)],
                "acme-user": [_block("b", 0.8)],
            },
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="x",
            total_budget_tokens=10000,
            per_workspace_floor=500,
        )
        assert len(blocks) == 2

    def test_empty_workspaces_list_returns_empty(self):
        mem = FakeMemory()
        assert three_tier_retrieve_multi(mem, [], "x") == []

    def test_duplicate_workspace_names_deduped(self):
        mem = FakeMemory()
        _setup_workspaces(
            mem,
            {"acme-news": [_block("dup-test", 0.5)]},
        )
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-news", "acme-news"],
            query="x",
            total_budget_tokens=2000,
            per_workspace_floor=100,
        )
        # We get a single source workspace's worth of blocks, not three.
        assert all(b.source_workspace == "acme-news" for b in blocks)
        assert len(blocks) == 1


class TestPartialFailure:
    def test_workspace_that_raises_does_not_block_others(self):
        mem = FakeMemory()
        _setup_workspaces(
            mem,
            {
                "acme-news": [_block("recovery", 0.9)],
                # acme-user will raise via raise_for_workspace below.
                "acme-user": [],
            },
        )
        mem.raise_for_workspace("acme-user")
        blocks = three_tier_retrieve_multi(
            mem,
            workspaces=["acme-news", "acme-user"],
            query="x",
            total_budget_tokens=2000,
            per_workspace_floor=100,
        )
        sources = {b.source_workspace for b in blocks}
        assert sources == {"acme-news"}


class TestTokenEstimation:
    def test_estimator_handles_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_estimator_rounds_up(self):
        # 5 chars = 2 tokens (ceil(5/4)).
        assert _estimate_tokens("hello") == 2

    def test_estimator_scales_with_length(self):
        small = _estimate_tokens("x" * 100)
        big = _estimate_tokens("x" * 1000)
        assert big > small * 5
