"""REST surface for the background-task substrate.

The router is a thin adapter over :class:`BackgroundTaskManager` and
:class:`SchedulerLoop`. Endpoints follow the same conventions as the
existing routers (``mcp.py``, ``agent.py``): a process-singleton
manager resolved via ``_require_manager``, HTTP 503 when nothing is
wired, structured error bodies on permission-like denials.

Endpoints:

    GET    /api/tasks                              list tasks
    GET    /api/tasks/{task_id}                    one task + history
    POST   /api/tasks/{task_id}/cancel             request cancellation
    GET    /api/tasks/schedules                    list configured schedules
    POST   /api/tasks/schedules/{schedule_id}/enable
    POST   /api/tasks/schedules/{schedule_id}/disable
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Add src/ to sys.path so synthesis_engine is importable when this
# module is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.tasks import (
    BackgroundTaskManager,
    TaskRecord,
    TaskState,
    default_manager,
    get_default_manager,
    set_default_manager,
)
from synthesis_engine.tasks.scheduler import (
    Schedule,
    ScheduleStore,
    SchedulerLoop,
)

logger = logging.getLogger("api.routers.tasks")

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Process-singleton wiring
# ---------------------------------------------------------------------------


_SCHEDULE_STORE: Optional[ScheduleStore] = None
_SCHEDULER_LOOP: Optional[SchedulerLoop] = None


def set_schedule_store(store: Optional[ScheduleStore]) -> None:
    """Install (or clear, with ``None``) the process-wide ScheduleStore.

    The router uses the store to expose schedules and to flip their
    enabled flag on disk. Tests inject a store backed by ``tmp_path``;
    production lifespan wires one backed by ``~/.synthesis/schedules.yaml``.
    """
    global _SCHEDULE_STORE
    _SCHEDULE_STORE = store


def get_schedule_store() -> Optional[ScheduleStore]:
    return _SCHEDULE_STORE


def set_scheduler_loop(loop: Optional[SchedulerLoop]) -> None:
    """Install (or clear) the process-wide :class:`SchedulerLoop`."""
    global _SCHEDULER_LOOP
    _SCHEDULER_LOOP = loop


def get_scheduler_loop() -> Optional[SchedulerLoop]:
    return _SCHEDULER_LOOP


def _require_manager() -> BackgroundTaskManager:
    """Resolve the installed manager, building one on first use.

    Unlike ``agent.py``'s ``_require_loop``, the task substrate has a
    sensible default (filesystem-backed JSONL under
    ``~/.synthesis/tasks``), so we lazy-construct one when nothing is
    explicitly wired. Tests still get isolation by calling
    :func:`set_default_manager` before issuing requests.
    """
    manager = get_default_manager()
    if manager is None:
        manager = default_manager()
        set_default_manager(manager)
    return manager


def _require_schedule_store() -> ScheduleStore:
    store = get_schedule_store()
    if store is None:
        # Lazy fallback to the default path so a curl against the
        # endpoint on an unprepared install still returns a sensible
        # error or an empty list.
        store = ScheduleStore()
        set_schedule_store(store)
    return store


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TaskRecordResponse(BaseModel):
    id: str
    name: str
    state: str
    created_at_iso: str
    started_at_iso: Optional[str] = None
    finished_at_iso: Optional[str] = None
    result_summary: Optional[str] = None
    error_summary: Optional[str] = None
    webhook_url: Optional[str] = None
    cancellation_requested: bool = False
    timeout_seconds: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskHistoryResponse(BaseModel):
    record: TaskRecordResponse
    history: List[Dict[str, Any]]


class TaskListResponse(BaseModel):
    tasks: List[TaskRecordResponse]


class CancelTaskResponse(BaseModel):
    task_id: str
    accepted: bool
    state: str


class ScheduleResponse(BaseModel):
    id: str
    name: str
    cron: str
    task: str
    args: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    timeout_seconds: Optional[int] = None
    webhook_url: Optional[str] = None


class ScheduleListResponse(BaseModel):
    schedules: List[ScheduleResponse]


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _serialize_task(record: TaskRecord) -> TaskRecordResponse:
    return TaskRecordResponse(**record.to_dict())


def _serialize_schedule(sched: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=sched.id,
        name=sched.name or sched.id,
        cron=sched.cron,
        task=sched.task,
        args=dict(sched.args),
        enabled=sched.enabled,
        timeout_seconds=sched.timeout_seconds,
        webhook_url=sched.webhook_url,
    )


# ---------------------------------------------------------------------------
# Endpoints — tasks
# ---------------------------------------------------------------------------


@router.get("", response_model=TaskListResponse)
async def list_tasks_endpoint(
    state: Optional[str] = Query(
        default=None,
        description=(
            "Filter by state. One of queued, running, succeeded, failed, "
            "cancelled, timed_out, crashed."
        ),
    ),
    limit: int = Query(default=100, ge=1, le=1000),
) -> TaskListResponse:
    """List known tasks, newest first."""
    manager = _require_manager()
    if state is not None and state not in TaskState.ALL:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown state filter {state!r}. Valid states: {list(TaskState.ALL)}",
        )
    records = manager.list_tasks(state_filter=state, limit=limit)
    return TaskListResponse(tasks=[_serialize_task(r) for r in records])


@router.get("/schedules", response_model=ScheduleListResponse)
async def list_schedules_endpoint() -> ScheduleListResponse:
    """List configured schedules from the YAML store."""
    store = _require_schedule_store()
    try:
        schedules = store.load()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ScheduleListResponse(
        schedules=[_serialize_schedule(s) for s in schedules],
    )


@router.post(
    "/schedules/{schedule_id}/enable", response_model=ScheduleResponse,
)
async def enable_schedule_endpoint(schedule_id: str) -> ScheduleResponse:
    store = _require_schedule_store()
    updated = store.set_enabled(schedule_id, True)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule with id {schedule_id!r}.",
        )
    return _serialize_schedule(updated)


@router.post(
    "/schedules/{schedule_id}/disable", response_model=ScheduleResponse,
)
async def disable_schedule_endpoint(schedule_id: str) -> ScheduleResponse:
    store = _require_schedule_store()
    updated = store.set_enabled(schedule_id, False)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule with id {schedule_id!r}.",
        )
    return _serialize_schedule(updated)


@router.get("/{task_id}", response_model=TaskHistoryResponse)
async def get_task_endpoint(task_id: str) -> TaskHistoryResponse:
    """Fetch one task plus its JSONL transition history."""
    manager = _require_manager()
    record = manager.get_task(task_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown task {task_id!r}.",
        )
    return TaskHistoryResponse(
        record=_serialize_task(record),
        history=manager.get_history(task_id),
    )


@router.post("/{task_id}/cancel", response_model=CancelTaskResponse)
async def cancel_task_endpoint(task_id: str) -> CancelTaskResponse:
    """Request cooperative cancellation. Returns the resulting state."""
    manager = _require_manager()
    accepted = manager.cancel_task(task_id)
    record = manager.get_task(task_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown task {task_id!r}.",
        )
    return CancelTaskResponse(
        task_id=task_id, accepted=accepted, state=record.state,
    )


# ---------------------------------------------------------------------------
# Test hooks
# ---------------------------------------------------------------------------


def clear_runtime_state() -> None:
    """Reset router-level singletons (test hook)."""
    set_default_manager(None)
    set_schedule_store(None)
    set_scheduler_loop(None)


__all__ = [
    "clear_runtime_state",
    "get_schedule_store",
    "get_scheduler_loop",
    "router",
    "set_default_manager",
    "set_schedule_store",
    "set_scheduler_loop",
]
