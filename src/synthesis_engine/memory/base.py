"""Abstract Memory interface.

Every memory backend conforms to :class:`Memory`. The default
implementation (``pgvector_memory.PgvectorMemory``) ships with
synthesis_engine; alternative implementations against Mem0, Letta,
Zep/Graphiti, or other backends slot in behind the same interface
without changes to retrieval or the API router.

The interface deliberately stays storage-agnostic:

    * Methods exchange Pydantic ``models.*`` types (Entity, Relation,
      SessionMemory, UserMemory, MemoryQuery, MemoryResult).
    * Vector search returns the substrate's existing ``SearchHit`` from
      ``synthesis_engine.vectorstore`` so the three-tier retriever can
      reuse the same shape regardless of which memory backend is active.
    * ``search_three_tier`` is on the interface because every memory
      backend has *some* opinion about how to merge tiers — pgvector
      merges in Python after pulling from postgres; Mem0 merges in its
      managed service. The merge is the backend's responsibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from .models import (
    Entity,
    MemoryQuery,
    MemoryResult,
    Provenance,
    Relation,
    SessionMemory,
    UserMemory,
)

# Use the substrate's existing search-hit shape for the vector tier so
# callers don't see a third dataclass for "a chunk." This keeps the seam
# between memory and the underlying vector store thin.
from ..vectorstore import SearchHit


class Memory(ABC):
    """Three-tier memory contract every backend implements."""

    backend_name: str = "abstract"

    # ------------------------------------------------------------------
    # Tier 2 — entities
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_entity(self, entity: Entity) -> Entity:
        """Insert or update an entity, returning the persisted shape.

        Identity is by ``(workspace, type, name)``. On conflict the
        attributes are merged: attributes present in the incoming entity
        replace those in the existing row (with their own per-attribute
        provenance); attributes absent in the incoming entity are
        preserved.
        """

    @abstractmethod
    def get_entity(
        self,
        entity_id: Optional[UUID] = None,
        *,
        workspace: Optional[str] = None,
        type: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[Entity]:
        """Fetch a single entity by id or by ``(workspace, type, name)``."""

    @abstractmethod
    def list_entities(
        self,
        workspace: str,
        *,
        type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        """List entities in a workspace, optionally filtered by type."""

    # ------------------------------------------------------------------
    # Tier 2 — relations (bi-temporal)
    # ------------------------------------------------------------------

    @abstractmethod
    def upsert_relation(
        self,
        relation: Relation,
        *,
        supersedes: Optional[UUID] = None,
    ) -> Relation:
        """Insert a new relation row.

        If ``supersedes`` is provided, the backend executes both writes —
        setting the prior row's ``validity_end`` and inserting the new
        row — inside one transaction so external observers never see a
        half-superseded state. A ``supersedes`` audit relation is also
        recorded.

        Provenance on the incoming relation is REQUIRED.
        """

    @abstractmethod
    def get_relation(self, relation_id: UUID) -> Optional[Relation]:
        """Fetch a single relation by id (includes superseded rows)."""

    @abstractmethod
    def query_graph(
        self,
        workspace: str,
        *,
        seed_entity_ids: List[UUID],
        depth: int = 2,
        validity_at: Optional[Any] = None,
        relation_types: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Relation]:
        """Traverse the entity graph up to ``depth`` hops from the seeds.

        When ``validity_at`` is set, returns the facts that were current
        at that timestamp (bi-temporal as-of). When None, returns only
        currently-valid facts (``validity_end IS NULL``).
        """

    # ------------------------------------------------------------------
    # Tier 3a — session memory
    # ------------------------------------------------------------------

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Fetch session memory by session id."""

    @abstractmethod
    def set_session(self, session: SessionMemory) -> SessionMemory:
        """Insert or update session memory."""

    # ------------------------------------------------------------------
    # Tier 3b — user memory
    # ------------------------------------------------------------------

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[UserMemory]:
        """Fetch user-scoped persistent memory."""

    @abstractmethod
    def set_user(self, user: UserMemory) -> UserMemory:
        """Insert or update user memory."""

    # ------------------------------------------------------------------
    # Tier 1 — vector search delegated to the substrate's vector store
    # ------------------------------------------------------------------

    @abstractmethod
    def search_vector(
        self,
        workspace: str,
        query_vector: List[float],
        *,
        limit: int = 10,
        content_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Tier-1 vector search over the workspace's chunks."""

    # ------------------------------------------------------------------
    # Three-tier merged retrieval
    # ------------------------------------------------------------------

    @abstractmethod
    def search_three_tier(
        self,
        query: MemoryQuery,
        *,
        query_vector: Optional[List[float]] = None,
    ) -> List[MemoryResult]:
        """Merged ranked retrieval across tiers.

        Implementations must dedupe and tag every entry with its
        ``tier`` of origin and the contributing provenance so the agent
        loop can cite back to source.

        ``query_vector`` is optional: when omitted, implementations that
        need a vector either compute one (using their embedding hook) or
        skip the vector tier and fall back to keyword search on the
        underlying vector store.
        """


def require_provenance(provenance: Optional[Provenance]) -> Dict[str, Any]:
    """Module-level helper used by Memory implementations.

    Validates that provenance is present and returns the jsonb-shaped
    dict to store. Centralised here so every backend enforces the same
    contract.
    """

    if provenance is None:
        raise ValueError(
            "Provenance is required on every relation. Supply "
            "Provenance(source=..., agent_run_id=..., message_id=..., "
            "confidence=...) on the upsert."
        )
    return provenance.model_dump(mode="json")
