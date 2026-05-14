"""Background-task substrate for synthesis_engine.

This package is the canonical home for long-running asynchronous work
that detaches from a chat thread, a CLI invocation, or any HTTP request
cycle. Where :class:`synthesis_engine.agent.AgentLoop` ships its own
in-memory ``_RUNNING_TASKS`` dict and the memory consolidator carries a
batch-task pattern of its own, this substrate generalises the pattern
so any caller can launch a coroutine, hand the requester a task handle
+ status URL + webhook, and be confident the task will reach a
TERMINAL state record on disk even if the process crashes mid-flight.

Public surface
==============

* :class:`BackgroundTaskManager` — the substrate primitive. Starts
  coroutines, persists their state transitions to a JSONL file under
  ``~/.synthesis/tasks/{task_id}.jsonl``, exposes list/get/cancel, and
  surfaces ``recover_crashed_tasks`` so a fresh process marks
  running-at-startup records as ``crashed`` for observers.

* :class:`TaskHandle` — thin wrapper around the underlying asyncio
  task; exposes ``await_result`` and ``cancel`` without leaking
  ``asyncio.Task`` internals into callers.

* :class:`TaskRecord` — the immutable view of a task's current
  state. Constructed from the JSONL stream.

* :class:`TaskState` — enum of the canonical terminal vs non-terminal
  states. ``running`` is the only non-terminal state with a writer
  contract; every transition out of it must record a terminal value.

* Notification adapters live in :mod:`.notifications`. The scheduler
  lives in :mod:`.scheduler`. The cron-style schedule store ships
  alongside the scheduler so the operator's ``~/.synthesis/schedules.yaml``
  is read by exactly one piece of code.

This module intentionally does NOT import the API router or any
FastAPI bindings. The HTTP surface at :mod:`api.routers.tasks` is the
only place where the substrate touches the web layer, mirroring the
pattern set by ``synthesis_engine.mcp`` and ``synthesis_engine.agent``.
"""

from __future__ import annotations

from .manager import (
    BackgroundTaskManager,
    TaskHandle,
    TaskRecord,
    TaskState,
    TerminalStates,
    default_manager,
    get_default_manager,
    set_default_manager,
)
from .registry import (
    TaskFactoryRegistry,
    get_default_registry,
    register_default_task_factories,
    set_default_registry,
)

__all__ = [
    "BackgroundTaskManager",
    "TaskFactoryRegistry",
    "TaskHandle",
    "TaskRecord",
    "TaskState",
    "TerminalStates",
    "default_manager",
    "get_default_manager",
    "get_default_registry",
    "register_default_task_factories",
    "set_default_manager",
    "set_default_registry",
]
