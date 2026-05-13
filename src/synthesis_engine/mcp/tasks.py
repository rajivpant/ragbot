"""MCP Tasks support (2025-11-25 spec, SEP-1686).

Any MCP request can be promoted to a *task* — a durable handle the
client polls for status, fetches the payload from when complete, and
cancels if it changes its mind. This module wraps the SDK's
``experimental.tasks`` surface so the substrate offers task semantics
without forcing callers to reach into experimental namespaces.

JSON-RPC methods covered:

* ``tools/call`` with task metadata — promote a tool call to a task
  (the SDK helper :meth:`ExperimentalClientFeatures.call_tool_as_task`).
* ``tasks/get`` — current status of a task.
* ``tasks/result`` — payload when the task has reached the
  ``completed`` state.
* ``tasks/cancel`` — request cancellation; the server moves the task
  to ``cancelled`` (or leaves it terminal if it has already finished).
* ``tasks/list`` — enumerate the server's tasks.
* ``notifications/tasks/status`` — server-to-client status pushes; the
  SDK delivers them through the session's notification stream. Callers
  who want to react in real time pass a callback to :func:`subscribe`.

The Tasks API is independent of the primitive being promoted: a server
that advertises Tasks support can promote any other request to a task.
The wrappers here cover the common case of a tool call; promoting a
sampling or resources/read request follows the same shape.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Dict, Optional, TypeVar

from mcp import ClientSession
from mcp.client.experimental.tasks import (
    ExperimentalClientFeatures,
    poll_until_terminal,
)
from mcp.types import (
    CallToolResult,
    CancelTaskResult,
    CreateTaskResult,
    GetTaskResult,
    ListTasksResult,
)


T = TypeVar("T")


TaskStatus = str  # "submitted" | "working" | "input_required" | "completed" | "failed" | "cancelled"
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


def features(session: ClientSession) -> ExperimentalClientFeatures:
    """Return the experimental-features helper bound to ``session``.

    Calling ``session.experimental`` directly is equivalent; this wrapper
    exists so substrate callers go through one stable name even if the
    SDK re-organises the surface across versions.
    """
    return session.experimental()


async def call_tool_as_task(
    session: ClientSession,
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    ttl_ms: int = 60_000,
    meta: Optional[Dict[str, Any]] = None,
) -> CreateTaskResult:
    """Promote a tool call to a task.

    Returns a :class:`CreateTaskResult` whose ``task`` field carries the
    task id (and the rest of the task envelope). Use :func:`get_status`,
    :func:`get_result`, and :func:`cancel` to manage the lifetime, or
    :func:`poll_until_done` for the common "wait for the result" path.
    """
    return await features(session).call_tool_as_task(
        name=name, arguments=arguments or {}, ttl=ttl_ms, meta=meta
    )


async def get_status(session: ClientSession, task_id: str) -> GetTaskResult:
    """Return the current status envelope for ``task_id``."""
    return await features(session).get_task(task_id)


async def get_result(
    session: ClientSession,
    task_id: str,
    result_type: type[T] = CallToolResult,  # type: ignore[assignment]
) -> T:
    """Fetch the payload for a completed task.

    ``result_type`` is the pydantic model the payload deserialises into
    — :class:`CallToolResult` for tool-promoted tasks, the appropriate
    result type for other primitives. The default is :class:`CallToolResult`
    because tool promotion is by far the most common path.
    """
    return await features(session).get_task_result(task_id, result_type)


async def cancel(session: ClientSession, task_id: str) -> CancelTaskResult:
    """Request cancellation of ``task_id``."""
    return await features(session).cancel_task(task_id)


async def list_tasks(
    session: ClientSession,
    *,
    cursor: Optional[str] = None,
) -> ListTasksResult:
    """Return one page of tasks (the cursor lets you walk further)."""
    return await features(session).list_tasks(cursor=cursor)


async def poll_until_done(
    session: ClientSession,
    task_id: str,
    *,
    on_status: Optional[Callable[[GetTaskResult], Awaitable[None]]] = None,
) -> GetTaskResult:
    """Poll ``task_id`` until it reaches a terminal state.

    Honors the server-provided ``pollInterval`` on each status response;
    falls back to 500 ms when the server doesn't suggest one. The
    optional ``on_status`` callback fires for every intermediate status,
    suitable for streaming progress updates to a UI.
    """
    last: Optional[GetTaskResult] = None

    async def _get(tid: str) -> GetTaskResult:
        return await get_status(session, tid)

    async for status in poll_until_terminal(_get, task_id):
        last = status
        if on_status is not None:
            await on_status(status)
        if status.status in TERMINAL_STATES:
            return status
    # poll_until_terminal yields the terminal state as its last value,
    # so we always return something here. The assert is defensive.
    assert last is not None, "poll_until_terminal yielded no statuses"
    return last


async def subscribe(
    session: ClientSession,
    task_id: str,
    *,
    on_status: Callable[[GetTaskResult], Awaitable[None]],
) -> AsyncIterator[GetTaskResult]:
    """Async iterator over status updates for ``task_id``.

    A thin convenience around :func:`poll_until_done` for callers that
    want the iterator shape (e.g., to ``async for`` over progress in a
    UI handler).
    """
    async def _get(tid: str) -> GetTaskResult:
        return await get_status(session, tid)

    async for status in poll_until_terminal(_get, task_id):
        await on_status(status)
        yield status
        if status.status in TERMINAL_STATES:
            return


__all__ = [
    "TaskStatus",
    "TERMINAL_STATES",
    "call_tool_as_task",
    "cancel",
    "features",
    "get_result",
    "get_status",
    "list_tasks",
    "poll_until_done",
    "subscribe",
]
