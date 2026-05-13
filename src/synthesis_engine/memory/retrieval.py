"""Three-tier retrieval merge across the memory tiers.

Public entry points:

    >>> three_tier_retrieve(memory, query)
    [MemoryResult(tier='vector', ...), MemoryResult(tier='graph', ...), ...]

    >>> three_tier_retrieve_multi(
    ...     memory,
    ...     workspaces=["acme-news", "acme-user"],
    ...     query="who owns the migration plan?",
    ...     total_budget_tokens=6000,
    ... )
    [RetrievedBlock(source_workspace='acme-news', ...), ...]

The single-workspace function pulls results from each enabled tier and
merges them into a single ranked list with deduplication. Provenance is
preserved per entry so the agent loop can cite the source of every fact
it surfaces.

The multi-workspace function fans out across workspaces under a shared
token budget, runs the single-workspace retriever per workspace, and
returns blocks tagged with their source workspace so the agent's answer
can cite each block by origin. Unused budget from sparse workspaces is
redistributed proportionally so a thin workspace doesn't starve a rich
one and a rich workspace doesn't drown out a thin one.

Why a module-level function instead of a Memory method.

    The merge logic is the same regardless of backend; only the per-tier
    reads vary. Putting the merge here means a new backend (Mem0, Letta)
    can implement just the per-tier reads and inherit the merge for free,
    keeping the seam thin.

Ranking model.

    Each tier produces scores in its own range. We normalise per-tier
    and apply a small per-tier weight so high-confidence
    explicitly-stored facts (graph relations with provenance.confidence
    near 1.0) edge out fuzzy semantic matches when both surface the same
    information.

    Default weights:
        session > user > graph > vector

    The reasoning: session memory is the freshest, most explicitly
    contextual signal (the agent itself wrote it this turn). User memory
    is the next most explicit. Graph facts have provenance and validity
    windows. Vector hits are the most ambient signal and the easiest to
    over-retrieve from.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from ..vectorstore import SearchHit
from .models import (
    Entity,
    MemoryQuery,
    MemoryResult,
    Provenance,
    Relation,
)

if TYPE_CHECKING:
    from .base import Memory

logger = logging.getLogger(__name__)


# Tier weights are applied to per-tier-normalised scores. Tuned so a
# strong graph fact (score 1.0) beats an average vector hit (0.5).
_TIER_WEIGHTS: Dict[str, float] = {
    "session": 1.2,
    "user": 1.1,
    "graph": 1.0,
    "vector": 0.9,
}


def three_tier_retrieve(
    memory: "Memory",
    query: MemoryQuery,
    *,
    query_vector: Optional[List[float]] = None,
) -> List[MemoryResult]:
    """Run a three-tier retrieval and return the merged ranked list.

    Args:
        memory: The backend implementing the :class:`Memory` interface.
        query: The query envelope, including workspace, k, depth, and
            optional ``validity_at`` for temporal queries.
        query_vector: Optional embedded form of the query. When omitted
            the vector tier is skipped (the caller can supply a vector
            built with whatever embedding model they prefer).

    Returns:
        A merged ranked list of :class:`MemoryResult`, each tagged with
        the tier of origin and the provenance that supports the entry.
    """

    results: List[MemoryResult] = []

    # ------------------------------------------------------------------
    # Tier 1 — vector chunks (workspace-scoped)
    # ------------------------------------------------------------------

    vector_seed_entity_ids: List[UUID] = []
    if query_vector is not None and query.vector_k > 0:
        try:
            hits = memory.search_vector(
                query.workspace, query_vector, limit=query.vector_k
            )
            normalised = _normalise_hits([h.score for h in hits])
            for hit, norm in zip(hits, normalised):
                results.append(
                    MemoryResult(
                        tier="vector",
                        score=norm * _TIER_WEIGHTS["vector"],
                        text=hit.text,
                        metadata={
                            "raw_score": hit.score,
                            **hit.metadata,
                            "tier_label": "Tier 1 — vector",
                        },
                    )
                )
            # Vector hits don't directly give us entity ids. The graph
            # traversal step pulls entity ids from chunk metadata when
            # the chunker has tagged them (a future enhancement: the
            # consolidation pass writes a mirror entity per indexed
            # document). For now we extract any entity_id annotations
            # that the metadata happens to carry.
            for hit in hits:
                ent_id = hit.metadata.get("entity_id")
                if ent_id:
                    try:
                        vector_seed_entity_ids.append(UUID(str(ent_id)))
                    except (ValueError, AttributeError):
                        pass
        except Exception as exc:
            logger.warning("vector tier failed in three_tier_retrieve: %s", exc)

    # ------------------------------------------------------------------
    # Tier 2 — entity graph traversal
    # ------------------------------------------------------------------

    if query.graph_depth >= 0:
        # Build the seed set from (a) any entity-id annotations on the
        # vector hits and (b) entity-name matches in the workspace.
        # Name matching: list entities and filter by token overlap. This
        # is cheap and avoids requiring an entity-text embedding; for a
        # larger graph callers can supply their own seeds via the API.
        seeds: List[UUID] = list(vector_seed_entity_ids)
        if query.text:
            seeds.extend(_seed_entities_by_name(memory, query))
        seeds = _dedupe_uuids(seeds)

        if seeds:
            try:
                relations = memory.query_graph(
                    query.workspace,
                    seed_entity_ids=seeds,
                    depth=query.graph_depth,
                    validity_at=query.validity_at,
                )
                relation_scores = _normalise_hits(
                    [_relation_score(r) for r in relations]
                )
                for rel, norm in zip(relations, relation_scores):
                    results.append(
                        MemoryResult(
                            tier="graph",
                            score=norm * _TIER_WEIGHTS["graph"],
                            text=_render_relation(memory, rel),
                            relation_id=rel.id,
                            provenance=rel.provenance,
                            metadata={
                                "raw_score": _relation_score(rel),
                                "from_entity": str(rel.from_entity),
                                "to_entity": str(rel.to_entity),
                                "type": rel.type,
                                "validity_start": rel.validity_start.isoformat()
                                if rel.validity_start
                                else None,
                                "validity_end": rel.validity_end.isoformat()
                                if rel.validity_end
                                else None,
                                "tier_label": "Tier 2 — entity graph",
                            },
                        )
                    )
            except Exception as exc:
                logger.warning("graph tier failed in three_tier_retrieve: %s", exc)

    # ------------------------------------------------------------------
    # Tier 3a — session memory
    # ------------------------------------------------------------------

    if query.include_session and query.session_id:
        try:
            session = memory.get_session(query.session_id)
            if session and session.payload:
                results.append(
                    MemoryResult(
                        tier="session",
                        score=1.0 * _TIER_WEIGHTS["session"],
                        text=_render_payload("session", session.payload),
                        metadata={
                            "session_id": session.session_id,
                            "workspace": session.workspace,
                            "tier_label": "Tier 3a — session memory",
                        },
                    )
                )
        except Exception as exc:
            logger.warning("session tier failed: %s", exc)

    # ------------------------------------------------------------------
    # Tier 3b — user memory
    # ------------------------------------------------------------------

    if query.include_user and query.user_id:
        try:
            user = memory.get_user(query.user_id)
            if user and user.payload:
                results.append(
                    MemoryResult(
                        tier="user",
                        score=1.0 * _TIER_WEIGHTS["user"],
                        text=_render_payload("user", user.payload),
                        metadata={
                            "user_id": user.user_id,
                            "tier_label": "Tier 3b — user memory",
                        },
                    )
                )
        except Exception as exc:
            logger.warning("user tier failed: %s", exc)

    # ------------------------------------------------------------------
    # Final merge: dedupe by (tier, text) and sort by score desc.
    # ------------------------------------------------------------------

    deduped = _dedupe_results(results)
    deduped.sort(key=lambda r: r.score, reverse=True)
    return deduped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_hits(scores: List[float]) -> List[float]:
    """Min-max normalise tier scores to [0, 1]. Returns 1.0 for ties."""

    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _relation_score(relation: Relation) -> float:
    """Tier-2 raw score: provenance confidence, recency bonus, current bonus."""

    conf = relation.provenance.confidence if relation.provenance else 0.5
    # Current facts get a small bonus; closed-validity facts are still
    # surfaced but ranked below open facts of equal confidence.
    current_bonus = 0.1 if relation.validity_end is None else 0.0
    return conf + current_bonus


def _seed_entities_by_name(memory: "Memory", query: MemoryQuery) -> List[UUID]:
    """Cheap name-overlap seed selection.

    We list entities in the workspace and select those whose name token
    overlaps with the query. This is intentionally simple — production
    callers can pass explicit seeds via a higher-level API. The 100-row
    cap keeps the scan cheap; for very large graphs you'd hand-roll a
    tsvector or trigram index instead.
    """

    try:
        ents = memory.list_entities(query.workspace, limit=200)
    except Exception:
        return []
    query_tokens = {tok.lower() for tok in query.text.split() if len(tok) > 2}
    if not query_tokens:
        return []
    seeds: List[UUID] = []
    for ent in ents:
        name_tokens = {tok.lower() for tok in ent.name.split() if tok}
        if query_tokens & name_tokens:
            if ent.id is not None:
                seeds.append(ent.id)
    return seeds


def _render_relation(memory: "Memory", rel: Relation) -> str:
    """Render a relation as a one-line readable fact suitable for prompting."""

    try:
        from_ent = memory.get_entity(rel.from_entity)
        to_ent = memory.get_entity(rel.to_entity)
    except Exception:
        from_ent = to_ent = None
    from_name = from_ent.name if from_ent else str(rel.from_entity)
    to_name = to_ent.name if to_ent else str(rel.to_entity)
    suffix = ""
    if rel.validity_end is not None:
        suffix = f" (until {rel.validity_end.isoformat()})"
    return f"{from_name} --{rel.type}--> {to_name}{suffix}"


def _render_payload(label: str, payload: Dict) -> str:
    """Render session/user payload as a compact readable block."""

    try:
        import json

        return f"[{label}] " + json.dumps(payload, default=str, sort_keys=True)
    except Exception:
        return f"[{label}] {payload!r}"


def _dedupe_uuids(values: List[UUID]) -> List[UUID]:
    seen: set = set()
    out: List[UUID] = []
    for v in values:
        key = str(v)
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _dedupe_results(results: List[MemoryResult]) -> List[MemoryResult]:
    """Dedupe by (tier, text). Keeps the highest-scoring duplicate."""

    by_key: Dict[tuple, MemoryResult] = {}
    for r in results:
        key = (r.tier, r.text)
        if key not in by_key or r.score > by_key[key].score:
            by_key[key] = r
    return list(by_key.values())


# ---------------------------------------------------------------------------
# Cross-workspace retrieval (multi)
# ---------------------------------------------------------------------------


# Token-estimation heuristic: one token is roughly four characters of
# English prose. Used to size the per-workspace cap and to estimate the
# weight of a candidate block during budget allocation.
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate. Avoids a tokenizer dependency at this layer."""
    if not text:
        return 0
    # Round up so a 1-char string still costs 1 token in budget accounting.
    return max(1, (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


@dataclass
class RetrievedBlock:
    """One retrieval result tagged with its source workspace.

    The agent's final answer iterates over a list of these and cites
    each by ``source_workspace`` + the original ``MemoryResult`` shape.
    The block is intentionally mutable so the budget allocator can
    annotate it with the per-workspace rank in-place.
    """

    source_workspace: str
    result: MemoryResult
    estimated_tokens: int = 0
    workspace_rank: int = 0  # 1-based position within the source workspace

    @property
    def score(self) -> float:
        return self.result.score

    @property
    def text(self) -> str:
        return self.result.text


def _allocate_budgets(
    workspaces: List[str],
    candidates_by_workspace: Dict[str, List[RetrievedBlock]],
    total_budget_tokens: int,
    per_workspace_floor: int,
) -> Dict[str, int]:
    """Allocate per-workspace token budgets.

    Algorithm:

    1. Start with an equal split, floored at ``per_workspace_floor``.
    2. If equal-split-after-floor exceeds the total budget, scale the
       floor down proportionally (the floor is a target, not a guarantee
       — when the budget is too tight, every workspace gets the same
       reduced share).
    3. Compute "demand" per workspace (sum of tokens of candidates).
    4. Workspaces whose demand is below their allocation surrender the
       slack to a redistribution pool.
    5. Redistribute the pool to over-demand workspaces proportionally to
       (demand - allocation).

    The output sums to at most ``total_budget_tokens``.
    """

    n = len(workspaces)
    if n == 0:
        return {}

    # Step 1+2: equal split with floor.
    equal_share = total_budget_tokens // n if n > 0 else 0
    target_floor = min(per_workspace_floor, equal_share) if equal_share > 0 else 0
    allocations: Dict[str, int] = {
        w: max(equal_share, target_floor) for w in workspaces
    }
    # Clip to total budget by reducing all uniformly if needed.
    total_allocated = sum(allocations.values())
    if total_allocated > total_budget_tokens and total_allocated > 0:
        scale = total_budget_tokens / total_allocated
        allocations = {w: int(v * scale) for w, v in allocations.items()}

    # Step 3: demand.
    demands: Dict[str, int] = {}
    for w in workspaces:
        demands[w] = sum(b.estimated_tokens for b in candidates_by_workspace.get(w, []))

    # Step 4: collect slack.
    slack = 0
    for w in workspaces:
        if demands[w] < allocations[w]:
            slack += allocations[w] - demands[w]
            allocations[w] = demands[w]

    # Step 5: redistribute. "Over-demand" weight is (demand - allocation).
    over_weights: Dict[str, int] = {
        w: max(0, demands[w] - allocations[w]) for w in workspaces
    }
    total_weight = sum(over_weights.values())
    if total_weight > 0 and slack > 0:
        # Proportional distribution; remainder rolls to the heaviest.
        distributed = 0
        sorted_ws = sorted(
            workspaces, key=lambda w: -over_weights[w]
        )
        for w in sorted_ws:
            if over_weights[w] == 0:
                continue
            share = int(slack * over_weights[w] / total_weight)
            allocations[w] += share
            distributed += share
        remainder = slack - distributed
        if remainder > 0 and sorted_ws:
            allocations[sorted_ws[0]] += remainder

    return allocations


def three_tier_retrieve_multi(
    memory: "Memory",
    workspaces: List[str],
    query: str,
    *,
    total_budget_tokens: int = 6000,
    per_workspace_floor: int = 800,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    vector_k: int = 10,
    graph_depth: int = 2,
    include_session: bool = True,
    include_user: bool = True,
    query_vector: Optional[List[float]] = None,
) -> List[RetrievedBlock]:
    """Three-tier retrieval fanned out across multiple workspaces.

    For each workspace, the function calls :func:`three_tier_retrieve`
    with a per-workspace :class:`MemoryQuery`, then merges the results
    under a shared token budget. The budget is allocated equally per
    workspace (clamped to ``per_workspace_floor`` minimum) and unused
    budget from sparse workspaces is redistributed to data-rich ones.

    Args:
        memory: The Memory backend.
        workspaces: Ordered list of workspace names to query. Duplicates
            are removed in first-occurrence order. An empty list returns
            an empty result.
        query: The natural-language query.
        total_budget_tokens: The aggregate budget across all workspaces.
        per_workspace_floor: Minimum tokens reserved per workspace
            before redistribution. Clamped down when
            ``total_budget_tokens`` is too tight to honour the floor.
        user_id, session_id, vector_k, graph_depth, include_session,
        include_user, query_vector: Forwarded to the per-workspace
            :class:`MemoryQuery`.

    Returns:
        A flat list of :class:`RetrievedBlock` instances, in workspace
        order. Within each workspace, blocks retain the rank produced
        by :func:`three_tier_retrieve` (score-descending).
    """

    # De-duplicate workspaces while preserving order.
    seen: List[str] = []
    for w in workspaces:
        if isinstance(w, str) and w and w not in seen:
            seen.append(w)
    if not seen:
        return []

    # Per-workspace retrieve. We collect ALL candidates first, then
    # apply the budget. A workspace that produces nothing simply has
    # no blocks in the merged output.
    candidates_by_workspace: Dict[str, List[RetrievedBlock]] = {}
    for ws_name in seen:
        ws_query = MemoryQuery(
            text=query,
            workspace=ws_name,
            user_id=user_id,
            session_id=session_id,
            vector_k=vector_k,
            graph_depth=graph_depth,
            include_session=include_session,
            include_user=include_user,
        )
        try:
            ws_results = three_tier_retrieve(
                memory, ws_query, query_vector=query_vector,
            )
        except Exception as exc:
            logger.warning(
                "three_tier_retrieve failed for workspace %r: %s; "
                "continuing with the remaining workspaces.",
                ws_name, exc,
            )
            ws_results = []

        blocks: List[RetrievedBlock] = []
        for rank, mr in enumerate(ws_results, start=1):
            # Stamp source_workspace into the result's metadata so any
            # downstream consumer that holds just the MemoryResult can
            # still recover the origin.
            mr.metadata.setdefault("source_workspace", ws_name)
            blocks.append(
                RetrievedBlock(
                    source_workspace=ws_name,
                    result=mr,
                    estimated_tokens=_estimate_tokens(mr.text),
                    workspace_rank=rank,
                )
            )
        candidates_by_workspace[ws_name] = blocks

    # Allocate the budget.
    budgets = _allocate_budgets(
        seen,
        candidates_by_workspace,
        total_budget_tokens=total_budget_tokens,
        per_workspace_floor=per_workspace_floor,
    )

    # Apply per-workspace budget cap (greedy by score-descending rank).
    merged: List[RetrievedBlock] = []
    for ws_name in seen:
        remaining = budgets.get(ws_name, 0)
        for block in candidates_by_workspace.get(ws_name, []):
            cost = block.estimated_tokens
            if cost <= remaining:
                merged.append(block)
                remaining -= cost
            elif remaining > 0 and not merged_has_blocks_from(merged, ws_name):
                # Guarantee at least one block per workspace when the
                # workspace has any candidates and any budget — this
                # honours the floor in the worst case where a single
                # block is bigger than the floor itself.
                merged.append(block)
                remaining = 0
            # else: skip the block; we've exhausted this workspace's budget.

    return merged


def merged_has_blocks_from(merged: List[RetrievedBlock], workspace: str) -> bool:
    """Return True if ``merged`` already contains a block from ``workspace``."""
    return any(b.source_workspace == workspace for b in merged)
