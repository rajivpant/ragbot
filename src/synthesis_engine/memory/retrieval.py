"""Three-tier retrieval merge across the memory tiers.

Public entry point:

    >>> three_tier_retrieve(memory, query)
    [MemoryResult(tier='vector', ...), MemoryResult(tier='graph', ...), ...]

The function pulls results from each enabled tier and merges them into a
single ranked list with deduplication. Provenance is preserved per entry
so the agent loop can cite the source of every fact it surfaces.

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
from typing import Dict, List, Optional, TYPE_CHECKING
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
