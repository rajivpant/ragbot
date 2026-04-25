"""Configuration API endpoints."""

import os
import sys
from typing import Optional
from fastapi import APIRouter, Depends, Query

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
    get_key_status,
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

    # Surface vector backend status alongside other config so the web UI can
    # show which backend is active without a separate /health round-trip.
    backend_info: dict = {}
    try:
        from ragbot.vectorstore import get_vector_store

        vs = get_vector_store()
        if vs is not None:
            backend_info = vs.healthcheck()
    except Exception as exc:  # pragma: no cover - defensive
        backend_info = {"backend": "unknown", "ok": False, "reason": str(exc)}

    from ragbot.demo import is_demo_mode, DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME

    demo_active = is_demo_mode()

    # Same demo-mode count override as in /health.
    if demo_active:
        try:
            from ragbot.vectorstore import get_vector_store as _vs

            v = _vs()
            allowed = {DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME}
            if v is not None:
                visible = sum(1 for c in v.list_collections() if c in allowed)
                if isinstance(backend_info, dict):
                    backend_info = dict(backend_info)
                    backend_info["workspaces"] = visible
        except Exception:
            pass
    # In demo mode the only valid default_workspace is the bundled demo
    # one; the user's real default_workspace would point at a workspace
    # that's hidden by the demo discovery isolation.
    default_workspace = (
        DEMO_WORKSPACE_NAME if demo_active else get_default_workspace()
    )

    return ConfigResponse(
        version=VERSION,
        ai_knowledge_root=settings.ai_knowledge_root,
        workspace_count=len(workspaces),
        rag_available=check_rag_available(),
        default_model=get_default_model(),
        default_workspace=default_workspace,
        api_keys=check_api_keys(),
        workspaces_with_keys=keystore.list_workspaces_with_keys(),
        vector_backend=backend_info,
        demo_mode=demo_active,
    )


@router.get("/keys")
async def get_keys_status(workspace: Optional[str] = Query(None, description="Workspace name")):
    """
    Get detailed API key status per provider for a workspace.

    Returns for each provider:
    - has_key: whether any key is available (workspace or default)
    - source: 'workspace', 'default', or null
    - has_workspace_key: whether workspace has its own key
    - has_default_key: whether a default key exists

    This helps the UI show exactly which key will be used and allow overrides.
    """
    return get_key_status(workspace)
