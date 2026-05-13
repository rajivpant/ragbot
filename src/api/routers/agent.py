"""Agent-loop API endpoints.

REST surface for driving the synthesis_engine agent loop end-to-end from
the web UI and from external callers. The router is a thin adapter
around :class:`synthesis_engine.agent.AgentLoop`: every endpoint resolves
the process-wide loop (built lazily, similar to ``_require_client`` in
``mcp.py``), then asks the loop to do the work.

The agent loop is long-running by design — a single ``AgentLoop.run()``
call may invoke many LLM and tool calls in sequence. To keep the HTTP
request thread responsive, ``POST /run`` and ``POST /sessions/{id}/replay``
return immediately with a task id and schedule the loop work as an
``asyncio`` background task. Callers poll ``GET /sessions/{id}`` until the
state is terminal.

Endpoints:

    POST   /api/agent/run                              start a new task
    GET    /api/agent/sessions/{task_id}               latest state + checkpoint list
    POST   /api/agent/sessions/{task_id}/replay        resume from a checkpoint
    GET    /api/agent/sessions/{task_id}/checkpoints/{n}  one specific checkpoint

Permission-denied failures from the loop surface as HTTP 403 with a
structured error body so a UI can render the gate's reason without
parsing free-form text.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

# Add src/ to sys.path so synthesis_engine is importable when this
# module is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.agent import (
    AgentLoop,
    AgentState,
    FilesystemCheckpointStore,
    GraphState,
    PermissionRegistry,
)
from synthesis_engine.agent.checkpoints import CheckpointStore


logger = logging.getLogger("api.routers.agent")

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Process-singleton AgentLoop
# ---------------------------------------------------------------------------


_DEFAULT_LOOP: Optional[AgentLoop] = None


def get_default_loop() -> Optional[AgentLoop]:
    """Return the installed process-wide AgentLoop, or None."""
    return _DEFAULT_LOOP


def set_default_loop(loop: Optional[AgentLoop]) -> None:
    """Install (or clear, with ``None``) the process-wide AgentLoop.

    Tests use this to inject a fake-backed loop before issuing requests;
    production lifespan startup wires the production-backed loop the
    same way.
    """

    global _DEFAULT_LOOP
    _DEFAULT_LOOP = loop


def _require_loop() -> AgentLoop:
    """Resolve the installed AgentLoop or raise HTTP 503.

    Unlike ``mcp.py``'s ``_require_client``, the agent loop has no
    sensible disk-config fallback — the loop's behaviour depends on which
    LLM backend, MCP client, sandbox, etc. are wired into it. We refuse
    to operate without an explicit installation so a misconfigured
    deployment produces a clear error.
    """

    loop = get_default_loop()
    if loop is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent loop is not configured. Install one via "
                "api.routers.agent.set_default_loop(AgentLoop(...))."
            ),
        )
    return loop


# ---------------------------------------------------------------------------
# Background task tracking
# ---------------------------------------------------------------------------


# Per-task error context, captured when the loop raises a permission-
# denied error before any checkpoint can record it. The replay endpoints
# read this so callers see the structured error body even after the
# initial POST has returned.
_PERMISSION_ERRORS: Dict[str, Dict[str, Any]] = {}

# Background tasks by task_id. Held only to keep references alive so the
# asyncio loop does not garbage-collect the task before it finishes.
_RUNNING_TASKS: Dict[str, asyncio.Task] = {}


def _track_task(task_id: str, coro_task: asyncio.Task) -> None:
    """Remember the task so the event loop keeps it alive."""

    _RUNNING_TASKS[task_id] = coro_task

    def _drop(_t: asyncio.Task) -> None:
        _RUNNING_TASKS.pop(task_id, None)

    coro_task.add_done_callback(_drop)


def _record_permission_error(
    task_id: str, tool: str, reason: str
) -> None:
    """Cache the structured permission-denied payload for ``task_id``."""

    _PERMISSION_ERRORS[task_id] = {
        "error": "permission_denied",
        "tool": tool,
        "reason": reason,
        "task_id": task_id,
    }


def _peek_permission_error(task_id: str) -> Optional[Dict[str, Any]]:
    """Return the cached structured error for ``task_id`` if one exists.

    Read-only — polling clients see the same 403 on subsequent calls so
    they don't race the runtime cache. The cache is cleared by
    :func:`clear_runtime_state` (test hook) and on process restart.
    """

    return _PERMISSION_ERRORS.get(task_id)


def clear_runtime_state() -> None:
    """Reset the per-process runtime state (test hook).

    Drops cached permission errors and tracked background tasks. The
    installed AgentLoop singleton is untouched — call
    :func:`set_default_loop` with a fresh value if a test wants a fresh
    loop too.
    """

    _PERMISSION_ERRORS.clear()
    _RUNNING_TASKS.clear()


# ---------------------------------------------------------------------------
# Detecting permission-denied terminal states
# ---------------------------------------------------------------------------


def _classify_permission_failure(state: GraphState) -> Optional[Dict[str, Any]]:
    """Inspect a GraphState for a permission-denied terminal outcome.

    The loop records "Permission denied: <reason>" as the step error
    when a gate fires. A run that ends in ERROR because every replan
    re-hit the same denied tool surfaces here as a structured payload
    the caller can render directly.
    """

    if state.current_state != AgentState.ERROR:
        return None

    for step in state.plan:
        if step.error and "Permission denied" in step.error:
            reason = step.error.split("Permission denied:", 1)[-1].strip()
            return {
                "error": "permission_denied",
                "tool": _normalise_tool_name(step.target),
                "reason": reason or step.error,
                "task_id": state.task_id,
            }

    # The first run's plan may have been archived under replan_archive.
    for prior in state.metadata.get("replan_archive", []) or []:
        for raw in prior:
            err = raw.get("error") or ""
            if "Permission denied" in err:
                reason = err.split("Permission denied:", 1)[-1].strip()
                return {
                    "error": "permission_denied",
                    "tool": _normalise_tool_name(
                        raw.get("target") or "unknown"
                    ),
                    "reason": reason or err,
                    "task_id": state.task_id,
                }
    return None


def _normalise_tool_name(target: str) -> str:
    """Strip the optional ``server::`` prefix from a plan step's target.

    The agent loop's TOOL_CALL targets may be written as
    ``server_id::tool_name`` to disambiguate which MCP server the call
    goes to. The user-facing structured-error body surfaces the bare
    tool name — the gate registers against the bare name, so that is
    the right granularity to expose.
    """

    if "::" in target:
        return target.split("::", 1)[1]
    return target


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Body for POST /api/agent/run."""

    task: str = Field(min_length=1, description="Natural-language task.")
    max_iterations: int = Field(
        default=30,
        ge=1,
        le=1000,
        description="Maximum transitions before the loop forces ERROR.",
    )
    rubric: Optional[str] = Field(
        default=None,
        description="Optional rubric to drive the self-grading loop to DONE_GRADED.",
    )


class ReplayRequest(BaseModel):
    """Body for POST /api/agent/sessions/{task_id}/replay."""

    from_checkpoint: int = Field(
        ge=0,
        description="Checkpoint index to resume from. 0 is the first transition.",
    )


class RunResponse(BaseModel):
    """Body returned by POST /run and POST /replay.

    ``status`` is always ``"running"`` on creation; callers poll the
    session endpoint to observe the transition into a terminal state.
    """

    task_id: str
    status: str = "running"


# ---------------------------------------------------------------------------
# Background driver
# ---------------------------------------------------------------------------


async def _run_loop_in_background(
    *,
    loop: AgentLoop,
    state: GraphState,
    rubric: Optional[str],
    is_replay: bool,
) -> None:
    """Drive a pre-built state to terminal, surfacing permission errors.

    The driver wraps the loop's terminal path so any structured error
    (permission-denied today; other classes later) lands in
    :func:`_record_permission_error` and is observable via the session
    endpoint even if no further checkpoint was written.
    """

    try:
        if rubric is not None and not is_replay:
            # ``AgentLoop.run`` handles rubric wiring + initial checkpoint
            # for fresh runs; here we just call it. The state we built
            # is discarded and the loop builds its own — this branch
            # only runs for ``POST /run``.
            await loop.run(state.original_task, rubric=rubric)
        else:
            await loop.drive_to_terminal(state)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Agent loop raised an unhandled exception for task %s",
            state.task_id,
        )
        # Best-effort record so the session endpoint can surface it.
        _record_permission_error(
            state.task_id,
            tool="unknown",
            reason=f"loop dispatch failed: {exc!r}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", response_model=RunResponse)
async def post_run(body: RunRequest = Body(...)) -> RunResponse:
    """Start a new agent task. Returns immediately with the task id.

    The task drives in a FastAPI ``BackgroundTask`` (via
    ``asyncio.create_task``) so the request thread does not block on the
    loop's LLM / tool / sandbox calls. Callers poll
    ``GET /sessions/{task_id}`` to watch the FSM transition into DONE,
    DONE_GRADED, or ERROR.
    """

    loop = _require_loop()

    # Build the initial state ourselves so we can return its task_id
    # immediately. The loop's ``run()`` builds its own state internally,
    # so we route through ``drive_to_terminal()`` which accepts a
    # pre-built state — except when a rubric is wired, in which case
    # ``run()`` has rubric-aware setup we don't want to duplicate here.
    if body.rubric is None:
        state = GraphState.new(body.task, max_iterations=body.max_iterations)
        state.add_turn(state.current_state, "Initial state.")
        await loop.checkpoint_store.save(state)
        task_id = state.task_id
        coro = _run_loop_in_background(
            loop=loop, state=state, rubric=None, is_replay=False,
        )
    else:
        # Rubric path: pre-mint a task_id by saving an initial state.
        # We can't reuse it directly because ``loop.run()`` mints its
        # own — instead we expose the loop's run() directly and
        # populate task_id from the run's first checkpoint after the
        # fact. Callers see the task id in the response.
        state = GraphState.new(body.task, max_iterations=body.max_iterations)
        state.metadata["rubric_pending"] = True
        await loop.checkpoint_store.save(state)
        task_id = state.task_id

        async def _run_with_rubric() -> None:
            # Drive run() but seed the task_id we already returned to
            # the caller by injecting a custom initial state through
            # drive_to_terminal. The rubric still needs the grader
            # wiring, which run() does — so we replicate that wiring
            # here.
            state.metadata["rubric"] = body.rubric
            state.metadata["pending_grade"] = True
            state.metadata["grading_rounds"] = 0
            state.metadata.pop("rubric_pending", None)
            if loop.grader is None:
                _record_permission_error(
                    task_id,
                    tool="grader",
                    reason=(
                        "AgentLoop was given a rubric but no SelfGrader "
                        "was wired. Pass grader=SelfGrader(...) to the "
                        "loop."
                    ),
                )
                state.current_state = AgentState.ERROR
                state.error_message = (
                    "Rubric was requested but no SelfGrader is wired."
                )
                await loop.checkpoint_store.save(state)
                return
            await loop.checkpoint_store.save(state)
            await loop.drive_to_terminal(state)

        coro = _run_with_rubric()

    task = asyncio.create_task(coro)
    _track_task(task_id, task)
    return RunResponse(task_id=task_id, status="running")


@router.get("/sessions/{task_id}")
async def get_session(task_id: str) -> Dict[str, Any]:
    """Return the latest checkpointed state plus the checkpoint index list.

    A 404 is returned when no checkpoints exist for ``task_id`` — usually
    because the id is wrong or the task was never started on this
    process. The response body for a live task is::

        {
          "task_id": "...",
          "status": "running" | "done" | "done_graded" | "error",
          "state": { ... GraphState.to_dict() ... },
          "checkpoints": [0, 1, 2, ...]
        }

    Permission-denied terminations surface a 403 with the structured
    error body so callers can render the gate's reason without parsing
    free-form prose.
    """

    loop = _require_loop()
    store = loop.checkpoint_store

    state = await _load_latest_or_404(store, task_id)
    # Any cached permission error overrides the state status.
    cached = _peek_permission_error(task_id)
    if cached is not None:
        raise HTTPException(status_code=403, detail=cached)

    permission_payload = _classify_permission_failure(state)
    if permission_payload is not None:
        raise HTTPException(status_code=403, detail=permission_payload)

    checkpoints = await store.list_checkpoints(task_id)
    return {
        "task_id": task_id,
        "status": _status_label(state),
        "state": state.to_dict(),
        "checkpoints": list(checkpoints),
    }


@router.post(
    "/sessions/{task_id}/replay", response_model=RunResponse,
)
async def post_replay(
    task_id: str, body: ReplayRequest = Body(...),
) -> RunResponse:
    """Resume the task from ``body.from_checkpoint`` as a new task id.

    The original task is preserved. The replay loads the checkpoint,
    rebinds its task_id to a fresh value (so the new run's checkpoints
    do not collide with the original on disk), and drives the rebound
    state to a terminal state in the background.
    """

    loop = _require_loop()
    store = loop.checkpoint_store

    # Ensure the source checkpoint exists.
    try:
        source_state = await store.load(task_id, body.from_checkpoint)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Mint a fresh id so the replay's checkpoint stream is isolated from
    # the original. We retain the original id in metadata for audit.
    import uuid

    new_task_id = str(uuid.uuid4())
    replayed = GraphState.from_dict(source_state.to_dict())
    replayed.task_id = new_task_id
    replayed.metadata["replayed_from"] = {
        "task_id": task_id,
        "checkpoint": body.from_checkpoint,
    }
    replayed.add_turn(
        replayed.current_state,
        f"Replay seeded from {task_id}/{body.from_checkpoint:04d}.",
    )
    await store.save(replayed)

    coro = _run_loop_in_background(
        loop=loop, state=replayed, rubric=None, is_replay=True,
    )
    task = asyncio.create_task(coro)
    _track_task(new_task_id, task)
    return RunResponse(task_id=new_task_id, status="running")


@router.get("/sessions/{task_id}/checkpoints/{n}")
async def get_checkpoint(task_id: str, n: int) -> Dict[str, Any]:
    """Return the Nth checkpoint of ``task_id`` as a serialised GraphState."""

    loop = _require_loop()
    store = loop.checkpoint_store
    try:
        state = await store.load(task_id, n)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "task_id": task_id,
        "checkpoint": n,
        "state": state.to_dict(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_latest_or_404(
    store: CheckpointStore, task_id: str
) -> GraphState:
    """Load the most-recent checkpoint or raise 404 if there are none."""

    indices = await store.list_checkpoints(task_id)
    if not indices:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoints found for task {task_id}",
        )
    latest = indices[-1]
    return await store.load(task_id, latest)


def _status_label(state: GraphState) -> str:
    """Reduce the FSM state enum to the four labels the API surfaces."""

    if state.current_state == AgentState.ERROR:
        return "error"
    if state.current_state == AgentState.DONE_GRADED:
        return "done_graded"
    if state.current_state == AgentState.DONE and not state.metadata.get(
        "pending_grade"
    ):
        return "done"
    return "running"


__all__ = [
    "clear_runtime_state",
    "get_default_loop",
    "router",
    "set_default_loop",
]
