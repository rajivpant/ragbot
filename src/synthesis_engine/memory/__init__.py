"""Three-tier memory architecture for synthesis-engineering runtimes.

The memory layer goes beyond pure vector RAG. Three tiers compose:

    Tier 1 — vector RAG over indexed chunks (delegated to the existing
             ``synthesis_engine.vectorstore`` backend).
    Tier 2 — entity-graph memory with bi-temporal, immutable relations.
             Every fact carries provenance (source, agent_run_id,
             message_id, confidence) and a validity window
             (validity_start, validity_end). Supersession is recorded as
             new rows; the prior fact's row is preserved with its
             validity_end set.
    Tier 3 — per-session and per-user persistent memory.

The default implementation against pgvector ships in
:mod:`.pgvector_memory`. The :class:`Memory` ABC lets alternate
implementations (Mem0, Letta, Zep/Graphiti) slot in without changes to
:func:`.retrieval.three_tier_retrieve` or the API router.

Public exports:

    Memory                — abstract backend interface
    PgvectorMemory        — default implementation
    get_memory            — cached backend singleton resolver
    three_tier_retrieve   — merged ranked retrieval across all tiers
    consolidate_session   — between-session "dreaming" consolidation
    Entity, Relation, ... — Pydantic models exchanged at the boundary
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .base import Memory, require_provenance
from .consolidation import consolidate_session, render_session_transcript
from .models import (
    AttributeValue,
    Entity,
    MemoryQuery,
    MemoryResult,
    MemoryTier,
    Provenance,
    Relation,
    SessionMemory,
    UserMemory,
)
from .retrieval import three_tier_retrieve

logger = logging.getLogger(__name__)


_MEMORY: Optional[Memory] = None


def get_memory(refresh: bool = False) -> Optional[Memory]:
    """Return the configured memory backend (cached singleton).

    Defaults to the pgvector backend (matching the vector store default).
    When pgvector is unavailable, returns None — callers should treat
    None as "memory features disabled" and degrade gracefully.

    When ``refresh`` is True, the cache is dropped and the backend is
    rebuilt. Useful for tests that swap env vars.
    """

    global _MEMORY
    if _MEMORY is not None and not refresh:
        return _MEMORY

    name = os.environ.get("RAGBOT_MEMORY_BACKEND", "pgvector").strip().lower()
    if name in {"pgvector", "auto"}:
        try:
            from .pgvector_memory import PgvectorMemory  # noqa: WPS433

            _MEMORY = PgvectorMemory.from_env()
            return _MEMORY
        except Exception as exc:  # pragma: no cover - construction failure path
            logger.warning("PgvectorMemory unavailable (%s); memory disabled.", exc)
            _MEMORY = None
            return None

    logger.warning("Unknown RAGBOT_MEMORY_BACKEND=%r; memory disabled.", name)
    _MEMORY = None
    return None


def reset_memory() -> None:
    """Drop the cached memory backend (test hook)."""

    global _MEMORY
    _MEMORY = None


__all__ = [
    "AttributeValue",
    "Entity",
    "Memory",
    "MemoryQuery",
    "MemoryResult",
    "MemoryTier",
    "Provenance",
    "Relation",
    "SessionMemory",
    "UserMemory",
    "consolidate_session",
    "get_memory",
    "render_session_transcript",
    "require_provenance",
    "reset_memory",
    "three_tier_retrieve",
]
