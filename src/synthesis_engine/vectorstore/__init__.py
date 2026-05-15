"""Vector store abstraction for Ragbot.

The single supported backend is PgvectorBackend — PostgreSQL with the
pgvector extension. The :class:`VectorStore` ABC is retained because
other synthesis-engine consumers (Ragenie, synthesis-console, embedders
in user-built tools) may plug their own backends in behind the same
contract, but Ragbot itself ships pgvector-only as of v3.5.

Configuration is via :envvar:`RAGBOT_DATABASE_URL`. When the database
is unreachable, :func:`get_vector_store` returns ``None`` — callers in
``rag.py`` degrade gracefully (chat-only without RAG) rather than
silently swapping in a different store.

The :class:`Point` and :class:`SearchHit` dataclasses are the wire
format. They stay stable across backends so a future swap-in is a
one-file change, not a chat-path refactor.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass
class Point:
    """A single chunk to be inserted into the vector store.

    Attributes mirror what the chunker produces. ``vector`` is the embedding
    of the chunk's effective text (filename + title + chunk text combined,
    per the existing rag.py convention).
    """

    chunk_uid: str                       # deterministic chunk identifier
    vector: List[float]                  # embedding (length matches embedding_model)
    text: str                            # original chunk text (NOT the embedded form)
    chunk_index: int = 0
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    filename: Optional[str] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    source_path: Optional[str] = None
    embedding_model: str = "all-MiniLM-L6-v2"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    """A single result from a vector / keyword search.

    ``score`` is store-specific (cosine similarity for vector search,
    ts_rank for native FTS). The caller is responsible for any
    cross-tier comparison or rerank.
    """

    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class VectorStore(ABC):
    """The contract every backend implements."""

    backend_name: str = "abstract"

    @abstractmethod
    def init_collection(self, workspace: str, vector_size: int = 384) -> bool:
        """Ensure the workspace's storage exists. Idempotent."""

    @abstractmethod
    def upsert_points(self, workspace: str, points: List[Point]) -> int:
        """Insert/update chunks. Returns the count written."""

    @abstractmethod
    def search(
        self,
        workspace: str,
        query_vector: List[float],
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Vector ANN search. Filters by ``content_type`` when provided."""

    @abstractmethod
    def keyword_search(
        self,
        workspace: str,
        query: str,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Keyword / FTS search. Used for the BM25-equivalent leg of hybrid
        retrieval. Implementations without native FTS may return an empty
        list; the caller in ``rag.py`` then falls back to in-process BM25
        over scrolled chunks. Pgvector implements this via PostgreSQL's
        tsvector / ts_rank machinery, so the fallback never fires in
        practice on Ragbot's bundled stack."""

    @abstractmethod
    def scroll_documents(
        self,
        workspace: str,
        limit: int = 1000,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Iterate stored chunks (paginated). Used by find_full_document
        and the in-process BM25 fallback."""

    @abstractmethod
    def delete_collection(self, workspace: str) -> bool:
        """Remove all chunks (and documents) for a workspace."""

    @abstractmethod
    def list_collections(self) -> List[str]:
        """Return all workspace names that have any chunks stored."""

    @abstractmethod
    def get_collection_info(self, workspace: str) -> Optional[Dict[str, Any]]:
        """Return ``{count, ...}`` or None if the workspace has no data."""

    @abstractmethod
    def healthcheck(self) -> Dict[str, Any]:
        """Return ``{backend, ok: bool, ...detail}``. Used by /health endpoint."""


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------


_BACKEND: Optional[VectorStore] = None


def get_vector_store(refresh: bool = False) -> Optional[VectorStore]:
    """Return the pgvector backend (cached).

    Returns ``None`` when the database is unreachable or the pgvector
    Python extras are not installed. Callers in ``rag.py`` interpret
    ``None`` as "RAG is unavailable; chat path stays text-only" rather
    than swapping in a different store.
    """

    global _BACKEND
    if _BACKEND is not None and not refresh:
        return _BACKEND

    try:
        from .pgvector_backend import PgvectorBackend  # noqa: WPS433
        _BACKEND = PgvectorBackend.from_env()
    except Exception as exc:  # pragma: no cover - construction failure path
        logger.warning(
            "Pgvector backend unavailable (%s); RAG features disabled.",
            exc,
        )
        _BACKEND = None

    return _BACKEND


def reset_vector_store() -> None:
    """Drop the cached backend (test hook)."""

    global _BACKEND
    _BACKEND = None


__all__ = [
    "Point",
    "SearchHit",
    "VectorStore",
    "get_vector_store",
    "reset_vector_store",
]
