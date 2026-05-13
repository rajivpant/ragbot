"""Memory API endpoints.

REST surface for the three-tier memory architecture:

    GET  /api/memory/entities                    list entities (by workspace, type)
    GET  /api/memory/entities/{id}               full entity (with relations)
    POST /api/memory/entities                    upsert an entity
    GET  /api/memory/query                       three-tier retrieval
    GET  /api/memory/session/{session_id}        read session memory
    PUT  /api/memory/session/{session_id}        write session memory

Used by the agent loop (sub-phase 1.3), tests, and the consolidation
job. The endpoints are deliberately admin-shaped: the data they read
and write is workspace-scoped, so callers must supply ``workspace``
explicitly. Authentication is intentionally not implemented here —
ragbot has a single-user threat model today; multi-user auth is a
separate v3.5 concern.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

# Add src/ to sys.path so synthesis_engine is importable when this
# module is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.memory import (
    Entity,
    Memory,
    MemoryQuery,
    MemoryResult,
    Relation,
    SessionMemory,
    get_memory,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_memory() -> Memory:
    """Resolve the configured backend or raise a 503.

    Returns the cached singleton from ``get_memory()``. When pgvector is
    unreachable the singleton resolves to None; we surface that as a
    503 so the agent loop and the UI can degrade gracefully without
    swallowing the failure mode.
    """

    backend = get_memory()
    if backend is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Memory backend unavailable. Set RAGBOT_DATABASE_URL "
                "and ensure pgvector is reachable."
            ),
        )
    return backend


class EntityWithRelations(BaseModel):
    """Detailed entity payload returned by GET /entities/{id}."""

    entity: Entity
    incoming_relations: List[Relation] = Field(default_factory=list)
    outgoing_relations: List[Relation] = Field(default_factory=list)


class MemoryQueryResponse(BaseModel):
    """Envelope for GET /query results."""

    workspace: str
    query: str
    results: List[MemoryResult]


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


@router.get("/entities", response_model=List[Entity])
def list_entities(
    workspace: str = Query(..., description="Workspace to scope entities to."),
    type: Optional[str] = Query(default=None, description="Optional entity type filter."),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> List[Entity]:
    memory = _require_memory()
    return memory.list_entities(workspace, type=type, limit=limit, offset=offset)


@router.get("/entities/{entity_id}", response_model=EntityWithRelations)
def get_entity(entity_id: UUID) -> EntityWithRelations:
    memory = _require_memory()
    entity = memory.get_entity(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    # Pull every relation touching this entity in the workspace. Two
    # short queries (incoming, outgoing) so the API caller can render
    # them in two columns.
    relations = memory.query_graph(
        entity.workspace,
        seed_entity_ids=[entity.id] if entity.id else [],
        depth=1,
    )
    incoming = [r for r in relations if str(r.to_entity) == str(entity.id)]
    outgoing = [r for r in relations if str(r.from_entity) == str(entity.id)]
    return EntityWithRelations(
        entity=entity,
        incoming_relations=incoming,
        outgoing_relations=outgoing,
    )


@router.post("/entities", response_model=Entity)
def upsert_entity(entity: Entity = Body(...)) -> Entity:
    memory = _require_memory()
    return memory.upsert_entity(entity)


# ---------------------------------------------------------------------------
# Three-tier query
# ---------------------------------------------------------------------------


@router.get("/query", response_model=MemoryQueryResponse)
def query_memory(
    q: str = Query(..., min_length=1, description="The natural-language query text."),
    workspace: str = Query(..., description="Workspace to scope retrieval to."),
    user_id: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    vector_k: int = Query(default=10, ge=0, le=200),
    graph_depth: int = Query(default=2, ge=0, le=5),
    include_session: bool = Query(default=True),
    include_user: bool = Query(default=True),
) -> MemoryQueryResponse:
    memory = _require_memory()
    query = MemoryQuery(
        text=q,
        workspace=workspace,
        user_id=user_id,
        session_id=session_id,
        vector_k=vector_k,
        graph_depth=graph_depth,
        include_session=include_session,
        include_user=include_user,
    )
    # query_vector left as None; the API surface does not compute
    # embeddings here. Callers that want the vector tier wired in
    # should call the lower-level memory API directly with an
    # embedded query. The graph/session/user tiers still produce
    # results so the endpoint remains useful.
    results = memory.search_three_tier(query)
    return MemoryQueryResponse(workspace=workspace, query=q, results=results)


# ---------------------------------------------------------------------------
# Session memory
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}", response_model=SessionMemory)
def get_session(session_id: str) -> SessionMemory:
    memory = _require_memory()
    session = memory.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.put("/session/{session_id}", response_model=SessionMemory)
def put_session(
    session_id: str,
    body: SessionMemory = Body(...),
) -> SessionMemory:
    if body.session_id and body.session_id != session_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Body session_id={body.session_id!r} does not match path "
                f"session_id={session_id!r}."
            ),
        )
    body.session_id = session_id
    memory = _require_memory()
    return memory.set_session(body)
