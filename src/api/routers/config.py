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
    get_default_workspace,
    get_keystore,
    check_api_keys,
    ConfigResponse,
)

from ..dependencies import get_settings, check_rag_available, Settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(settings: Settings = Depends(get_settings)):
    """Get application configuration."""
    workspaces = discover_workspaces()
    keystore = get_keystore()

    return ConfigResponse(
        version=VERSION,
        ai_knowledge_root=settings.ai_knowledge_root,
        workspace_count=len(workspaces),
        rag_available=check_rag_available(),
        default_model=get_default_model(),
        default_workspace=get_default_workspace(),
        api_keys=check_api_keys(),
        workspaces_with_keys=keystore.list_workspaces_with_keys(),
    )
