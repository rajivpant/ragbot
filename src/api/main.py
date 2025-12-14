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
from .routers import chat, workspaces, models, config


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


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        rag_available=check_rag_available(),
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
