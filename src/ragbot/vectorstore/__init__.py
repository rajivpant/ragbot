"""Vector store abstraction for Ragbot.

Two backends are available:

    - QdrantBackend  — embedded local-file Qdrant. Legacy / back-compat.
    - PgvectorBackend — PostgreSQL with pgvector extension. Preferred.

Selection is driven by the RAGBOT_VECTOR_BACKEND env var (``pgvector`` by default,
fallback ``qdrant``). The ``RAGBOT_DATABASE_URL`` env var configures the
pgvector connection string.

Both backends conform to the :class:`VectorStore` ABC defined here and exchange
the lightweight :class:`Point` and :class:`SearchHit` dataclasses, so callers
in ``rag.py`` are oblivious to the underlying technology.
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

    ``score`` is store-specific (cosine similarity for pgvector and Qdrant;
    BM25-style rank for keyword hits). The caller is responsible for any
    cross-store comparison or rerank.
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
        """Keyword/FTS search. Used for the BM25 leg of hybrid retrieval.

        For backends without native FTS (e.g., Qdrant), implementations may
        return an empty list and signal the caller to fall back to the
        in-process BM25 over scrolled chunks.
        """

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
# Backend selection
# ---------------------------------------------------------------------------


_BACKEND: Optional[VectorStore] = None


def _resolve_backend_name() -> str:
    name = os.environ.get("RAGBOT_VECTOR_BACKEND", "pgvector").strip().lower()
    if name not in ("pgvector", "qdrant"):
        logger.warning(
            "Unknown RAGBOT_VECTOR_BACKEND=%r, defaulting to pgvector",
            name,
        )
        return "pgvector"
    return name


def get_vector_store(refresh: bool = False) -> Optional[VectorStore]:
    """Return the configured backend (cached). None if the backend cannot
    initialize (e.g., pgvector chosen but Postgres unreachable and no
    fallback configured)."""

    global _BACKEND
    if _BACKEND is not None and not refresh:
        return _BACKEND

    name = _resolve_backend_name()
    backend: Optional[VectorStore] = None

    if name == "pgvector":
        try:
            from .pgvector_backend import PgvectorBackend  # noqa: WPS433
            backend = PgvectorBackend.from_env()
        except Exception as exc:  # pragma: no cover - construction failure path
            logger.warning(
                "Pgvector backend unavailable (%s); falling back to qdrant.",
                exc,
            )
            name = "qdrant"

    if name == "qdrant":
        from .qdrant_backend import QdrantBackend  # noqa: WPS433
        backend = QdrantBackend()

    _BACKEND = backend
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
