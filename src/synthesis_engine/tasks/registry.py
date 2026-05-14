"""Task-factory registry: name → callable resolution for scheduled work.

The cron-style scheduler reads ``~/.synthesis/schedules.yaml`` and
references tasks by short string names (e.g.,
``memory.consolidate_recent_idle``). The registry maps those names to
real Python callables that return a coroutine. The split keeps the
YAML config free of import-path strings while letting the scheduler
spawn the right work at the right time.

The default registry is populated lazily so importing
``synthesis_engine.tasks`` does NOT eagerly import every consumer
(memory, agent, observability) — that would create a circular import
hazard. Callers register their factories explicitly via
:func:`register_default_task_factories` (typically in lifespan startup)
or pass a hand-rolled registry to the scheduler.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("synthesis_engine.tasks.registry")


TaskFactory = Callable[[Dict[str, Any]], Awaitable[Any]]
"""Signature for a registered task factory.

The factory receives the ``args:`` dict from the YAML schedule (or
``{}`` if absent) and returns an awaitable. The awaitable is what
:class:`BackgroundTaskManager` drives to terminal.
"""


class UnknownTaskFactory(KeyError):
    """Raised when a schedule references a task name with no registered factory."""


class TaskFactoryRegistry:
    """Map task names → coroutine factories.

    The registry is intentionally a plain dict with light validation —
    callers wire the substrate by registering each task at process
    startup. A second registration of the same name replaces the
    previous entry; we log a warning so accidental shadowing is
    visible.
    """

    def __init__(self) -> None:
        self._factories: Dict[str, TaskFactory] = {}

    def register(self, name: str, factory: TaskFactory) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("Task factory name must be a non-empty string.")
        if name in self._factories:
            logger.info(
                "Replacing existing task-factory registration for %s.", name,
            )
        self._factories[name] = factory

    def get(self, name: str) -> TaskFactory:
        if name not in self._factories:
            raise UnknownTaskFactory(
                f"No registered task factory named {name!r}. "
                f"Registered factories: {sorted(self._factories)}"
            )
        return self._factories[name]

    def has(self, name: str) -> bool:
        return name in self._factories

    def names(self) -> List[str]:
        return sorted(self._factories)


# ---------------------------------------------------------------------------
# Process-singleton
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY: Optional[TaskFactoryRegistry] = None


def get_default_registry() -> TaskFactoryRegistry:
    """Resolve the process-wide registry, building one on first use."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = TaskFactoryRegistry()
    return _DEFAULT_REGISTRY


def set_default_registry(registry: Optional[TaskFactoryRegistry]) -> None:
    """Install (or clear) the process-wide :class:`TaskFactoryRegistry`."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = registry


# ---------------------------------------------------------------------------
# Built-in factories
# ---------------------------------------------------------------------------


async def _heartbeat_factory(_args: Dict[str, Any]) -> Dict[str, Any]:
    """Sanity-check factory: writes a heartbeat line and exits.

    Useful for verifying that the scheduler is alive and the JSONL
    state-dir is writable, without exercising any of the heavier
    consumers (memory, MCP, etc.).
    """
    from datetime import datetime, timezone

    return {"heartbeat_iso": datetime.now(timezone.utc).isoformat()}


def register_default_task_factories(
    registry: Optional[TaskFactoryRegistry] = None,
    *,
    include_memory_consolidation: bool = True,
) -> TaskFactoryRegistry:
    """Register the built-in factories on ``registry`` (default: singleton).

    The function is opt-in so test runs that do not touch the memory
    consolidator can skip the (small) import cost of pulling it in.
    """
    target = registry or get_default_registry()
    target.register("tasks.heartbeat", _heartbeat_factory)

    if include_memory_consolidation:
        target.register(
            "memory.consolidate_recent_idle", _consolidate_recent_idle_factory,
        )

    return target


async def _consolidate_recent_idle_factory(args: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap :meth:`MemoryConsolidator.consolidate_recent_idle` as a task.

    The factory pulls the active consolidator from the agent loop's
    process singleton when one is wired; otherwise it raises a clear
    error so the scheduler records ``failed`` with a debuggable
    summary rather than silently no-op'ing.
    """
    # Local imports to dodge a circular import: the memory package
    # depends on policy.audit, which depends on the YAML config;
    # pulling that in at package import time would cascade through
    # synthesis_engine's whole graph just because the scheduler is
    # installed.
    try:
        from ..agent import get_default_loop  # type: ignore[import-not-found]

        loop = get_default_loop()
    except Exception:  # noqa: BLE001 — agent loop may be absent
        loop = None

    consolidator = getattr(loop, "memory_consolidator", None) if loop else None
    if consolidator is None:
        # Fall back to constructing a fresh consolidator from environment.
        # The substrate has no opinion about which Memory backend should
        # be used by the scheduler — that wiring lives in the API
        # lifespan handler. If nothing is wired, we surface a clear error.
        raise RuntimeError(
            "memory.consolidate_recent_idle was scheduled, but no "
            "MemoryConsolidator is wired to the agent loop. Install one "
            "via the lifespan handler before enabling this schedule."
        )

    idle_hours = float(args.get("idle_threshold_hours", 4.0))
    model_id = args.get("model_id")
    workspace = args.get("workspace")
    dry_run = bool(args.get("dry_run", False))

    report = await consolidator.consolidate_recent_idle(
        idle_threshold_hours=idle_hours,
        model_id=model_id,
        workspace=workspace,
        dry_run=dry_run,
    )
    return report.to_dict() if hasattr(report, "to_dict") else report


__all__ = [
    "TaskFactory",
    "TaskFactoryRegistry",
    "UnknownTaskFactory",
    "get_default_registry",
    "register_default_task_factories",
    "set_default_registry",
]
