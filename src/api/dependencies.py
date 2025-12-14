"""Dependency injection for FastAPI.

Provides shared dependencies for API endpoints.
"""

import os
import sys
from typing import Optional
from functools import lru_cache

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import (
    discover_workspaces,
    find_ai_knowledge_root,
    get_workspace,
    VERSION,
)


class Settings:
    """Application settings."""

    def __init__(self):
        self.version = VERSION
        self.ai_knowledge_root = find_ai_knowledge_root()
        self.debug = os.environ.get("DEBUG", "false").lower() == "true"
        self.cors_origins = os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:8501"
        ).split(",")


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


def get_ai_knowledge_root() -> Optional[str]:
    """Get the ai-knowledge root directory."""
    return get_settings().ai_knowledge_root


def check_rag_available() -> bool:
    """Check if RAG is available."""
    try:
        from rag import is_rag_available
        return is_rag_available()
    except ImportError:
        return False
