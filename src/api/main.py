"""FastAPI application for Ragbot.

Provides REST API endpoints for chat, workspaces, models, and configuration.
Supports SSE streaming for chat responses.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import VERSION, HealthResponse

from .dependencies import get_settings, check_rag_available
from .routers import agent, chat, workspaces, models, config, preferences, memory, mcp, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Ragbot API v{VERSION} starting...")
    print(f"AI Knowledge root: {settings.ai_knowledge_root}")
    print(f"RAG available: {check_rag_available()}")
    yield
    # Shutdown
    print("Ragbot API shutting down...")


app = FastAPI(
    title="Ragbot API",
    description="REST API for Ragbot - AI Knowledge Assistant",
    version=VERSION,
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(workspaces.router)
app.include_router(models.router)
app.include_router(config.router)
app.include_router(preferences.router)
app.include_router(memory.router)
app.include_router(mcp.router)
app.include_router(metrics.router)
app.include_router(agent.router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint.

    Reports overall status, RAG availability, and the active vector backend's
    health (pgvector reachability, qdrant client status).
    """
    backend_health = {}
    try:
        from synthesis_engine.vectorstore import get_vector_store

        vs = get_vector_store()
        if vs is not None:
            backend_health = vs.healthcheck()
    except Exception as exc:  # pragma: no cover - defensive
        backend_health = {"backend": "unknown", "ok": False, "reason": str(exc)}

    from ragbot.demo import is_demo_mode, DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME

    # In demo mode, the host's true workspaces count would leak through
    # the healthcheck metadata. Override with the count of demo-visible
    # collections so screenshots cannot reveal that other workspaces
    # exist on the same vector store.
    if is_demo_mode():
        try:
            from synthesis_engine.vectorstore import get_vector_store as _vs

            v = _vs()
            allowed = {DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME}
            if v is not None:
                visible = sum(1 for c in v.list_collections() if c in allowed)
                if isinstance(backend_health, dict):
                    backend_health = dict(backend_health)
                    backend_health["workspaces"] = visible
        except Exception:
            pass

    return HealthResponse(
        status="ok",
        version=VERSION,
        rag_available=check_rag_available(),
        vector_backend=backend_health,
        demo_mode=is_demo_mode(),
    )


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Ragbot API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
