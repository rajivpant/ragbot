"""Substrate-level Pydantic models for synthesis-engineering runtimes.

These types are produced by code in this package (`workspaces`, future
discovery and indexing helpers). Runtimes are free to re-export them at
their own public API surface — Ragbot does so via `ragbot.WorkspaceInfo`,
which keeps existing external imports stable.

Runtime-specific API request/response shapes (chat requests, index requests,
config responses) do NOT belong here. They live in the runtime package
that owns the HTTP/CLI surface they describe.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class WorkspaceInfo(BaseModel):
    """Information about a workspace.

    Workspaces are AI-knowledge repositories discovered by the substrate's
    `workspaces.discover_*` helpers. Every runtime built on synthesis_engine
    consumes this shape.
    """

    name: str = Field(..., description="Display name")
    dir_name: str = Field(..., description="Directory name")
    description: Optional[str] = None
    status: str = Field("active", description="Workspace status")
    type: str = Field("project", description="Workspace type")
    inherits_from: List[str] = Field(default_factory=list)
    has_instructions: bool = False
    has_datasets: bool = False
    has_source: bool = False
    repo_path: Optional[str] = None


class WorkspaceList(BaseModel):
    """List of workspaces."""

    workspaces: List[WorkspaceInfo]
    count: int
