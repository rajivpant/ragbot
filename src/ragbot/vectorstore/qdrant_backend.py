"""Qdrant backend (legacy / back-compat).

Wraps the embedded local-file Qdrant client behind the :class:`VectorStore`
interface. Behavior-preserving: every operation matches what ``rag.py``
previously called directly. Kept available so users on an existing Qdrant
data volume can roll back via ``RAGBOT_VECTOR_BACKEND=qdrant``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from . import Point, SearchHit, VectorStore

logger = logging.getLogger(__name__)


def _safe_collection_name(workspace: str) -> str:
    """Match the original collection naming in rag.py (no surprises)."""

    safe = workspace.lower().replace(" ", "_").replace("-", "_")
    return f"ragbot_{safe}"


def _coerce_qdrant_id(chunk_uid: str):
    """Qdrant only accepts unsigned ints or UUIDs as point ids.

    The cross-backend ``chunk_uid`` is a string for portability. Convert it
    back to an int when it is numeric (the typical case for the existing
    chunker). For non-numeric ids, derive a deterministic UUIDv5 so Qdrant
    accepts the value while preserving idempotent upsert semantics.
    """

    try:
        return int(chunk_uid)
    except (TypeError, ValueError):
        pass
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_uid))


class QdrantBackend(VectorStore):
    backend_name = "qdrant"

    def __init__(self) -> None:
        self._client = None

    # ------------------------------------------------------------------
    # client init
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except ImportError:
            logger.warning("qdrant-client not installed; QdrantBackend disabled.")
            return None

        url = os.environ.get("QDRANT_URL")
        if url:
            self._client = QdrantClient(url=url)
            logger.info("QdrantBackend connected to %s", url)
        else:
            path = os.environ.get("QDRANT_PATH", "/app/qdrant_data")
            os.makedirs(path, exist_ok=True)
            self._client = QdrantClient(path=path)
            logger.info("QdrantBackend using local storage at %s", path)
        return self._client

    # ------------------------------------------------------------------
    # interface implementations
    # ------------------------------------------------------------------

    def init_collection(self, workspace: str, vector_size: int = 384) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            collection_name = _safe_collection_name(workspace)
            existing = {c.name for c in client.get_collections().collections}
            if collection_name not in existing:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
            return True
        except Exception as exc:
            logger.error("QdrantBackend.init_collection failed: %s", exc)
            return False

    def upsert_points(self, workspace: str, points: List[Point]) -> int:
        if not points:
            return 0
        client = self._get_client()
        if client is None:
            return 0
        try:
            from qdrant_client.models import PointStruct  # type: ignore

            collection_name = _safe_collection_name(workspace)
            qdrant_points = [
                PointStruct(
                    id=_coerce_qdrant_id(p.chunk_uid),
                    vector=p.vector,
                    payload={
                        "text": p.text,
                        "chunk_index": p.chunk_index,
                        "char_start": p.char_start,
                        "char_end": p.char_end,
                        "filename": p.filename,
                        "title": p.title,
                        "content_type": p.content_type,
                        "source_file": p.source_path,
                        "embedding_model": p.embedding_model,
                        **p.metadata,
                    },
                )
                for p in points
            ]
            written = 0
            batch_size = 100
            for i in range(0, len(qdrant_points), batch_size):
                batch = qdrant_points[i : i + batch_size]
                client.upsert(collection_name=collection_name, points=batch)
                written += len(batch)
            return written
        except Exception as exc:
            logger.error("QdrantBackend.upsert_points failed: %s", exc)
            return 0

    def search(
        self,
        workspace: str,
        query_vector: List[float],
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        client = self._get_client()
        if client is None:
            return []
        try:
            collection_name = _safe_collection_name(workspace)
            existing = {c.name for c in client.get_collections().collections}
            if collection_name not in existing:
                return []

            query_filter = None
            if content_type:
                from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

                query_filter = Filter(
                    must=[FieldCondition(key="content_type", match=MatchValue(value=content_type))]
                )

            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
            )
            return [
                SearchHit(
                    text=p.payload.get("text", "") if p.payload else "",
                    score=float(p.score),
                    metadata=dict(p.payload or {}),
                )
                for p in response.points
            ]
        except Exception as exc:
            logger.error("QdrantBackend.search failed: %s", exc)
            return []

    def keyword_search(
        self,
        workspace: str,
        query: str,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        # Qdrant does not provide native FTS in the embedded client. Returning
        # an empty list signals callers to use the in-process BM25 fallback
        # (which scrolls and tokenises in Python — same behavior as the
        # pre-Phase-2 implementation).
        return []

    def scroll_documents(
        self,
        workspace: str,
        limit: int = 1000,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        client = self._get_client()
        if client is None:
            return []
        try:
            collection_name = _safe_collection_name(workspace)
            existing = {c.name for c in client.get_collections().collections}
            if collection_name not in existing:
                return []

            scroll_filter = None
            if content_type:
                from qdrant_client.models import FieldCondition, Filter, MatchValue  # type: ignore

                scroll_filter = Filter(
                    must=[FieldCondition(key="content_type", match=MatchValue(value=content_type))]
                )

            points, _ = client.scroll(
                collection_name=collection_name,
                limit=limit,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
            )
            return [
                SearchHit(
                    text=(p.payload.get("text", "") if p.payload else ""),
                    score=0.0,
                    metadata=dict(p.payload or {}),
                )
                for p in points
            ]
        except Exception as exc:
            logger.error("QdrantBackend.scroll_documents failed: %s", exc)
            return []

    def delete_collection(self, workspace: str) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.delete_collection(_safe_collection_name(workspace))
            return True
        except Exception as exc:
            logger.error("QdrantBackend.delete_collection failed: %s", exc)
            return False

    def list_collections(self) -> List[str]:
        client = self._get_client()
        if client is None:
            return []
        try:
            return [c.name for c in client.get_collections().collections]
        except Exception as exc:
            logger.error("QdrantBackend.list_collections failed: %s", exc)
            return []

    def get_collection_info(self, workspace: str) -> Optional[Dict[str, Any]]:
        client = self._get_client()
        if client is None:
            return None
        try:
            collection_name = _safe_collection_name(workspace)
            existing = {c.name for c in client.get_collections().collections}
            if collection_name not in existing:
                return None
            # The embedded Qdrant client returns points_count=None for local
            # storage; use the count API for a reliable number.
            count_result = client.count(collection_name=collection_name, exact=True)
            count = int(getattr(count_result, "count", 0) or 0)
            info = client.get_collection(collection_name)
            return {
                "backend": self.backend_name,
                "collection": collection_name,
                "count": count,
                "vectors_count": getattr(info, "vectors_count", None),
                "status": str(getattr(info, "status", "")) or None,
            }
        except Exception as exc:
            logger.error("QdrantBackend.get_collection_info failed: %s", exc)
            return None

    def healthcheck(self) -> Dict[str, Any]:
        client = self._get_client()
        if client is None:
            return {"backend": self.backend_name, "ok": False, "reason": "qdrant-client unavailable"}
        try:
            client.get_collections()
            return {"backend": self.backend_name, "ok": True}
        except Exception as exc:
            return {"backend": self.backend_name, "ok": False, "reason": str(exc)}
