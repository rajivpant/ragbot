"""Workspace API endpoints."""

import os
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import (
    discover_workspaces,
    get_workspace,
    get_workspace_info,
    list_workspace_info,
    WorkspaceInfo,
    WorkspaceList,
    WorkspaceNotFoundError,
    IndexStatus,
    IndexRequest,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceList)
async def list_workspaces():
    """List all available workspaces."""
    workspaces = list_workspace_info()
    return WorkspaceList(
        workspaces=workspaces,
        count=len(workspaces)
    )


@router.get("/{name}", response_model=WorkspaceInfo)
async def get_workspace_detail(name: str):
    """Get details about a specific workspace."""
    workspaces = discover_workspaces()
    for ws in workspaces:
        if ws['name'] == name or ws['dir_name'] == name:
            return get_workspace_info(ws)

    raise HTTPException(status_code=404, detail=f"Workspace not found: {name}")


@router.get("/{name}/index", response_model=IndexStatus)
async def get_index_status(name: str):
    """Get RAG index status for a workspace."""
    try:
        # Check if workspace exists
        workspaces = discover_workspaces()
        workspace = None
        for ws in workspaces:
            if ws['name'] == name or ws['dir_name'] == name:
                workspace = ws
                break

        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace not found: {name}")

        # Check index status
        try:
            from rag import is_rag_available, get_index_status as rag_get_index_status
            if is_rag_available():
                indexed, doc_count = rag_get_index_status(workspace['dir_name'])
                return IndexStatus(
                    workspace=workspace['dir_name'],
                    indexed=indexed,
                    document_count=doc_count,
                )
        except ImportError:
            pass

        return IndexStatus(
            workspace=workspace['dir_name'],
            indexed=False,
            document_count=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/index", response_model=IndexStatus)
async def index_workspace(name: str, request: IndexRequest = None):
    """Trigger RAG indexing for a workspace."""
    try:
        # Check if workspace exists
        workspaces = discover_workspaces()
        workspace = None
        for ws in workspaces:
            if ws['name'] == name or ws['dir_name'] == name:
                workspace = ws
                break

        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace not found: {name}")

        # Perform indexing
        try:
            from rag import is_rag_available, index_workspace_by_name
            if not is_rag_available():
                raise HTTPException(status_code=503, detail="RAG not available")

            force = request.force if request else False
            doc_count = index_workspace_by_name(workspace['dir_name'], force=force)

            return IndexStatus(
                workspace=workspace['dir_name'],
                indexed=True,
                document_count=doc_count,
            )
        except ImportError:
            raise HTTPException(status_code=503, detail="RAG not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
