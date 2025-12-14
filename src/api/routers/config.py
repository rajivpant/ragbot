"""Configuration API endpoints."""

import os
import sys
from fastapi import APIRouter, Depends

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import (
    VERSION,
    discover_workspaces,
    find_ai_knowledge_root,
    get_default_model,
    ConfigResponse,
)

from ..dependencies import get_settings, check_rag_available, Settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(settings: Settings = Depends(get_settings)):
    """Get application configuration."""
    workspaces = discover_workspaces()

    return ConfigResponse(
        version=VERSION,
        ai_knowledge_root=settings.ai_knowledge_root,
        workspace_count=len(workspaces),
        rag_available=check_rag_available(),
        default_model=get_default_model(),
    )
