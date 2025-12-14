"""FastAPI application for Ragbot.

This package provides a REST API for Ragbot, enabling:
- Chat with streaming (SSE)
- Workspace management
- Model configuration
"""

from .main import app

__all__ = ["app"]
