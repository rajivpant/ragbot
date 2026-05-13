"""Agent Skills API endpoints.

REST surface for the workspace-scoped skill catalog and skill runner. The
router is a thin adapter around :mod:`synthesis_engine.skills`: discovery
and the workspace-inheritance filter live in the substrate, the router
only translates between HTTP-shape and substrate-shape and wires in
permission-gated dispatch when a skill is asked to run.

Endpoints:

    GET    /api/skills                   list skills (optional ?workspace=)
    GET    /api/skills/{name}            full skill body and tool list
    POST   /api/skills/{name}/run        activate and dispatch the first tool

The workspace filter mirrors the CLI's ``ragbot skills list --workspace W``
contract: when ``workspace`` is supplied, :func:`get_skills_for_workspace`
applies the inheritance chain so the workspace sees its own scoped skills
plus any universal ones plus any inherited from ancestors. Without
``workspace``, every discovered skill is returned with its scope tag so a
caller can pivot between "what's available here" and "the whole catalog"
without parsing two payloads.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

# Add src/ to sys.path so synthesis_engine is importable when this module
# is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.skills import (
    Skill,
    discover_skills,
    get_skills_for_workspace,
)
from synthesis_engine.skills.loader import (
    ActivatedSkill,
    ScriptNotFoundError,
    ScriptPathError,
    SkillLoader,
    SkillNotFoundError,
)
from synthesis_engine.skills.model import SkillScope, SkillTool


logger = logging.getLogger("api.routers.skills")

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ---------------------------------------------------------------------------
# Background dispatch tracking
# ---------------------------------------------------------------------------


# In-process task table for POST /run. A real runtime would wire this
# through Agent B's SkillRuntime when it lands; this router supplies a
# correct fallback so the UI works today. The task table is keyed by
# task_id and stores the running coroutine task plus its terminal result.
_TASKS: Dict[str, "_SkillRunRecord"] = {}


class _SkillRunRecord:
    """State for one /api/skills/{name}/run invocation."""

    def __init__(self, task_id: str, skill_name: str, workspace: Optional[str]) -> None:
        self.task_id = task_id
        self.skill_name = skill_name
        self.workspace = workspace
        self.status: str = "running"
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.task: Optional[asyncio.Task] = None


def clear_runtime_state() -> None:
    """Drop the in-process task table (test hook).

    Mirrors ``api.routers.agent.clear_runtime_state`` so tests that share
    the FastAPI app between cases can start each one with a clean slate.
    """
    _TASKS.clear()


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_scope(scope: SkillScope) -> Dict[str, Any]:
    """Render a SkillScope as a JSON object.

    The shape (``{"universal": bool, "workspaces": [...]}``) is stable
    across the API surface so the UI can pattern-match on it directly.
    """
    return {
        "universal": scope.universal,
        "workspaces": list(scope.workspaces),
    }


def _serialise_tool(tool: SkillTool) -> Dict[str, Any]:
    """Render a SkillTool as a JSON object."""
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.parameters),
        "script": tool.script,
    }


def _serialise_skill_summary(skill: Skill) -> Dict[str, Any]:
    """Compact view used by GET /api/skills (list endpoint)."""
    return {
        "name": skill.name,
        "description": skill.description,
        "scope": _serialise_scope(skill.scope),
        "source_path": skill.path,
        "version": skill.version,
        "tools": [_serialise_tool(t) for t in skill.tools],
        "tool_count": len(skill.tools),
        "reference_count": len(skill.references),
        "script_count": len(skill.scripts),
    }


def _serialise_skill_detail(skill: Skill) -> Dict[str, Any]:
    """Full view used by GET /api/skills/{name}.

    Includes the SKILL.md body and the list of reference markdown files
    so the UI can render an inline preview without a second round-trip
    per skill.
    """
    detail = _serialise_skill_summary(skill)
    detail["body"] = skill.body
    detail["frontmatter"] = dict(skill.frontmatter)
    detail["tool_permissions"] = dict(skill.tool_permissions)
    detail["files"] = [
        {
            "relative_path": f.relative_path,
            "kind": f.kind.value,
            "is_text": f.is_text,
            "char_count": len(f.content) if f.is_text else 0,
        }
        for f in skill.files
    ]
    return detail


# ---------------------------------------------------------------------------
# Resolver helpers
# ---------------------------------------------------------------------------


def _resolve_skills(workspace: Optional[str]) -> List[Skill]:
    """Return the discovered skill set, filtered by workspace when supplied.

    ``workspace`` is the URL query parameter, possibly None. None means
    "return the full catalog" — the contract documented on the list
    endpoint.
    """
    if workspace is None:
        return discover_skills()
    return get_skills_for_workspace(workspace)


def _find_skill_or_404(
    name: str, workspace: Optional[str]
) -> Skill:
    """Resolve a skill by name within the workspace's visible set.

    Returns the matching Skill on success. Raises 404 when the name is
    unknown, 403 when the skill exists in the global catalog but is
    invisible from the supplied workspace — the distinction matters for
    UI affordances (a 404 is "no such skill anywhere," a 403 is "you
    are looking in the wrong workspace").
    """
    if workspace is not None:
        visible = get_skills_for_workspace(workspace)
        match = next((s for s in visible if s.name == name), None)
        if match is not None:
            return match
        # Fall back to the global catalog to distinguish "not visible
        # here" from "doesn't exist."
        every = discover_skills()
        if any(s.name == name for s in every):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "skill_not_visible",
                    "skill": name,
                    "workspace": workspace,
                    "message": (
                        f"Skill {name!r} exists but is not visible from "
                        f"workspace {workspace!r}."
                    ),
                },
            )
        raise HTTPException(
            status_code=404,
            detail=f"Skill not found: {name}",
        )

    # No workspace filter: just look in the global catalog.
    every = discover_skills()
    match = next((s for s in every if s.name == name), None)
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skill not found: {name}",
        )
    return match


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class SkillRunRequest(BaseModel):
    """Body for POST /api/skills/{name}/run.

    ``workspace`` is required so callers cannot accidentally invoke a
    skill outside its declared scope. ``input`` is the dict the skill's
    tool consumes; the shape is the skill's responsibility, not the
    API's. ``file`` is an optional UTF-8 payload bound to the ``"file"``
    input key — a convenience for skills that take a single document
    body and don't want callers to base64-stuff it into ``input``.
    """

    workspace: str = Field(min_length=1, description="Workspace scope for the dispatch.")
    input: Dict[str, Any] = Field(default_factory=dict)
    file: Optional[str] = None
    model: Optional[str] = Field(
        default=None,
        description=(
            "Optional LLM model id override. Defaults to the engines.yaml "
            "default."
        ),
    )


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------


async def _run_skill_background(
    record: _SkillRunRecord,
    activated: ActivatedSkill,
    inputs: Dict[str, Any],
    model_override: Optional[str],
) -> None:
    """Drive a skill to completion, recording the outcome on ``record``.

    Mirrors the CLI dispatcher's first-tool semantics: when the skill
    declares tools, dispatch through the agent loop. When it does not,
    send the body as a single LLM prompt. Either way, the result lands
    on the record as ``status="done"`` and ``result=<text>`` or
    ``status="error"`` and ``error=<reason>``.
    """
    try:
        skill = activated.skill
        tools = activated.tools

        if tools:
            target_tool = tools[0]
            task = (
                f"Use the '{target_tool.name}' tool from skill "
                f"'{skill.name}' with the supplied inputs.\n\n"
                f"Tool description: {target_tool.description or '(none)'}\n"
                f"Inputs: {inputs}\n\n"
                f"Skill body:\n{activated.body_markdown}"
            )
            answer = await _dispatch_via_agent_loop(task)
        else:
            body = activated.body_markdown or skill.description or skill.name
            prompt = (
                f"{body}\n\n---\n\nInputs: {inputs}"
                if inputs else body
            )
            answer = await _dispatch_via_llm(prompt, model_override)

        record.result = answer
        record.status = "done"
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Skill run %s failed for %s", record.task_id, record.skill_name,
        )
        record.error = f"{type(exc).__name__}: {exc}"
        record.status = "error"


async def _dispatch_via_agent_loop(task: str) -> str:
    """Drive the agent loop and return its final answer.

    A fresh loop is constructed per dispatch so the runtime state is
    isolated. The permission registry is permissive by default — Ragbot
    is single-user and the operator already vetted the skill when they
    installed it. Multi-user deployments wire a stricter registry into
    the application factory.
    """
    from synthesis_engine.agent import (
        AgentLoop,
        FilesystemCheckpointStore,
        PermissionRegistry,
        PermissionResult,
    )
    from synthesis_engine.llm import get_llm_backend

    backend = get_llm_backend()
    registry = PermissionRegistry()
    registry.register(
        "*", lambda _ctx: PermissionResult.allow("api-permissive-skills-run"),
    )
    checkpoint_root = os.path.expanduser(
        "~/.ragbot/skill_run_checkpoints"
    )
    loop = AgentLoop(
        llm_backend=backend,
        mcp_client=None,
        permission_registry=registry,
        checkpoint_store=FilesystemCheckpointStore(base_dir=checkpoint_root),
        default_mcp_server="local",
    )
    final_state = await loop.run(task)
    return final_state.final_answer or "(no final answer produced)"


async def _dispatch_via_llm(prompt: str, model_override: Optional[str]) -> str:
    """Send a single prompt through the configured LLM backend."""
    from synthesis_engine.config import get_default_model
    from synthesis_engine.llm import LLMRequest, get_llm_backend

    backend = get_llm_backend()
    model = model_override or get_default_model()
    request = LLMRequest(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    # The backends are sync; run them in a thread so the FastAPI event
    # loop stays responsive while the LLM is generating.
    response = await asyncio.to_thread(backend.complete, request)
    return response.text


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_skills(
    workspace: Optional[str] = Query(
        default=None,
        description="Filter to skills visible from this workspace.",
    ),
) -> Dict[str, Any]:
    """List discovered skills.

    Without ``workspace``: returns every discovered skill across every
    discovery root. With ``workspace``: returns only the skills visible
    from that workspace via the inheritance chain. Response shape is
    identical in either case so the UI can pivot between the two views
    without parsing two payloads.
    """
    skills = _resolve_skills(workspace)
    return {
        "skills": [_serialise_skill_summary(s) for s in skills],
        "workspace": workspace,
        "total": len(skills),
    }


@router.get("/{name}")
async def get_skill(
    name: str,
    workspace: Optional[str] = Query(
        default=None,
        description="Resolve through this workspace's inheritance chain.",
    ),
) -> Dict[str, Any]:
    """Return the full SKILL.md body, frontmatter, and file list for one skill.

    The detail endpoint is the UI's pivot when the user expands a row in
    the skills panel. Returning the full body and reference markdown in
    one call avoids a chatty N+1 query pattern over the list.
    """
    skill = _find_skill_or_404(name, workspace)
    return _serialise_skill_detail(skill)


@router.post("/{name}/run")
async def run_skill(
    name: str,
    body: SkillRunRequest = Body(...),
) -> Dict[str, Any]:
    """Activate a skill and dispatch its first tool (or body prompt).

    The request body's ``workspace`` is enforced as the visibility
    check. A 403 is returned when the skill exists but is not visible
    from the supplied workspace — the same contract the CLI applies. On
    success the response is ``{"task_id": <uuid>, "status": "running"}``
    and the caller polls ``GET /api/skills/runs/{task_id}`` (or watches
    the in-process record via the test hook) for the final answer.
    """
    workspace = body.workspace
    skill = _find_skill_or_404(name, workspace)

    visible = get_skills_for_workspace(workspace)
    loader = SkillLoader(visible)
    try:
        activated = loader.activate(skill.name)
    except SkillNotFoundError as exc:
        # Defensive: the visibility check above already guards this, but
        # surface a 403 here rather than a 500 if the loader disagrees.
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    inputs = dict(body.input)
    if body.file is not None:
        inputs["file"] = body.file

    task_id = str(uuid.uuid4())
    record = _SkillRunRecord(task_id, skill.name, workspace)
    _TASKS[task_id] = record

    coro = _run_skill_background(record, activated, inputs, body.model)
    record.task = asyncio.create_task(coro)
    return {"task_id": task_id, "status": "running", "skill": skill.name}


@router.get("/runs/{task_id}")
async def get_run(task_id: str) -> Dict[str, Any]:
    """Return the current state of a skill-run task.

    Response shape: ``{"task_id", "skill", "workspace", "status",
    "result"?, "error"?}``. ``status`` is one of ``running``, ``done``,
    ``error``. A 404 is returned when the task id is unknown.
    """
    record = _TASKS.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    payload: Dict[str, Any] = {
        "task_id": record.task_id,
        "skill": record.skill_name,
        "workspace": record.workspace,
        "status": record.status,
    }
    if record.result is not None:
        payload["result"] = record.result
    if record.error is not None:
        payload["error"] = record.error
    return payload


__all__ = [
    "clear_runtime_state",
    "router",
]
