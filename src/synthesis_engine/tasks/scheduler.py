"""Cron-style scheduler for background tasks.

Reads ``~/.synthesis/schedules.yaml`` and registers each enabled
schedule with an :class:`AsyncIOScheduler` (apscheduler). On each
firing tick, the schedule resolves its task name through the
:class:`TaskFactoryRegistry`, constructs a coroutine, and hands it to
the :class:`BackgroundTaskManager` exactly the way an HTTP caller
would.

The scheduler is opt-in: the substrate ships it but does not start it
unless ``RAGBOT_SCHEDULER=1`` is set or the operator explicitly calls
:meth:`SchedulerLoop.start`. This keeps the test suite hermetic and
avoids surprise behaviour in unit-test invocations.

Schedule YAML schema
====================

.. code-block:: yaml

    schedules:
      - id: nightly-consolidation
        name: "Nightly memory consolidation"   # optional, defaults to id
        cron: "0 3 * * *"
        task: "memory.consolidate_recent_idle"
        args:
          idle_threshold_hours: 4
        enabled: true
        timeout_seconds: 3600                  # optional
        webhook_url: "https://example.invalid/hook"  # optional

Each field maps cleanly onto :class:`Schedule`. Unknown fields are
preserved on the dataclass via the ``extra`` dict so future schema
extensions don't break older readers.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep
    yaml = None  # type: ignore[assignment]

from .manager import BackgroundTaskManager, default_manager
from .registry import TaskFactoryRegistry, get_default_registry

logger = logging.getLogger("synthesis_engine.tasks.scheduler")


DEFAULT_SCHEDULES_PATH = Path.home() / ".synthesis" / "schedules.yaml"
SCHEDULER_ENV = "RAGBOT_SCHEDULER"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class Schedule:
    """One schedule entry from the YAML."""

    id: str
    cron: str
    task: str
    name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timeout_seconds: Optional[int] = None
    webhook_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Schedule":
        known = {
            "id",
            "cron",
            "task",
            "name",
            "args",
            "enabled",
            "timeout_seconds",
            "webhook_url",
        }
        extra = {k: v for k, v in raw.items() if k not in known}
        sched = cls(
            id=str(raw["id"]),
            cron=str(raw["cron"]),
            task=str(raw["task"]),
            name=str(raw.get("name") or raw["id"]),
            args=dict(raw.get("args") or {}),
            enabled=bool(raw.get("enabled", True)),
            timeout_seconds=raw.get("timeout_seconds"),
            webhook_url=raw.get("webhook_url"),
            extra=extra,
        )
        return sched

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "cron": self.cron,
            "task": self.task,
            "args": dict(self.args),
            "enabled": self.enabled,
        }
        if self.timeout_seconds is not None:
            out["timeout_seconds"] = self.timeout_seconds
        if self.webhook_url is not None:
            out["webhook_url"] = self.webhook_url
        out.update(self.extra)
        return out


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class ScheduleStore:
    """Read / write the YAML schedules file.

    Writes preserve unknown top-level keys so an operator-extended
    YAML keeps its custom blocks across a flip-enable round-trip.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else DEFAULT_SCHEDULES_PATH

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> List[Schedule]:
        if yaml is None:
            raise RuntimeError(
                "PyYAML is required for ScheduleStore but is not installed."
            )
        if not self._path.is_file():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise RuntimeError(
                f"Failed to read schedules at {self._path}: {exc}"
            ) from exc
        raw = data.get("schedules") or []
        if not isinstance(raw, list):
            raise RuntimeError(
                f"schedules block in {self._path} must be a list, got "
                f"{type(raw).__name__}."
            )
        result: List[Schedule] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                result.append(Schedule.from_dict(entry))
            except KeyError as exc:
                logger.warning(
                    "Skipping malformed schedule entry (missing %s)", exc,
                )
        return result

    def save(self, schedules: List[Schedule]) -> None:
        if yaml is None:
            raise RuntimeError(
                "PyYAML is required for ScheduleStore but is not installed."
            )
        # Read existing top-level keys so we don't accidentally drop
        # an operator's hand-edited config block.
        top: Dict[str, Any] = {}
        if self._path.is_file():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                if isinstance(raw, dict):
                    top = dict(raw)
            except (OSError, yaml.YAMLError):
                top = {}
        top["schedules"] = [s.to_dict() for s in schedules]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(top, f, sort_keys=False)
        os.replace(tmp, self._path)

    def set_enabled(self, schedule_id: str, enabled: bool) -> Optional[Schedule]:
        schedules = self.load()
        updated: Optional[Schedule] = None
        for s in schedules:
            if s.id == schedule_id:
                s.enabled = enabled
                updated = s
                break
        if updated is not None:
            self.save(schedules)
        return updated


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------


# Type alias for the apscheduler instance — kept as Any so the substrate
# does not hard-fail import when apscheduler is absent in a stripped-
# down environment. The constructor raises a clear error in that case.
APSScheduler = Any


class SchedulerLoop:
    """Runs scheduled tasks in the FastAPI app's event loop.

    Construction does NOT start the scheduler — call :meth:`start` to
    register schedules and begin firing. This split lets tests
    construct a loop, inspect its planned registrations, and not
    actually schedule anything in apscheduler's clock.
    """

    def __init__(
        self,
        *,
        store: Optional[ScheduleStore] = None,
        manager: Optional[BackgroundTaskManager] = None,
        registry: Optional[TaskFactoryRegistry] = None,
        aps_scheduler: Optional[APSScheduler] = None,
    ) -> None:
        self._store = store or ScheduleStore()
        self._manager = manager or default_manager()
        self._registry = registry or get_default_registry()
        self._aps = aps_scheduler
        self._running = False
        self._registered_ids: List[str] = []

    @property
    def manager(self) -> BackgroundTaskManager:
        return self._manager

    @property
    def registry(self) -> TaskFactoryRegistry:
        return self._registry

    @property
    def store(self) -> ScheduleStore:
        return self._store

    @property
    def registered_ids(self) -> List[str]:
        return list(self._registered_ids)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Register enabled schedules with the underlying APScheduler."""
        if self._running:
            return
        if self._aps is None:
            self._aps = _build_aps_scheduler()
        schedules = self._store.load()
        self._registered_ids = []
        for sched in schedules:
            if not sched.enabled:
                logger.debug(
                    "Skipping disabled schedule %s (%s).", sched.id, sched.task,
                )
                continue
            if not self._registry.has(sched.task):
                logger.warning(
                    "Schedule %s references unregistered task %s; skipping.",
                    sched.id,
                    sched.task,
                )
                continue
            self._register_one(sched)
        if hasattr(self._aps, "start"):
            try:
                self._aps.start()
            except Exception as exc:  # noqa: BLE001 — log but stay alive
                logger.warning("Scheduler start() raised: %s", exc)
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        if self._aps is not None and hasattr(self._aps, "shutdown"):
            try:
                self._aps.shutdown(wait=False)
            except Exception:  # noqa: BLE001 — shutdown is best-effort
                pass
        self._running = False
        self._registered_ids = []

    def fire_now(self, schedule_id: str) -> None:
        """Run a schedule's task immediately (used by tests + manual triggers)."""
        for sched in self._store.load():
            if sched.id == schedule_id:
                self._spawn(sched)
                return
        raise KeyError(f"No schedule with id {schedule_id!r}.")

    # ----- internals ---------------------------------------------------------

    def _register_one(self, sched: Schedule) -> None:
        try:
            trigger = _build_cron_trigger(sched.cron)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Schedule %s has invalid cron %r: %s",
                sched.id,
                sched.cron,
                exc,
            )
            return

        def _job() -> None:
            # The apscheduler job runs in the asyncio loop; spawning the
            # task on the manager schedules it on the same loop.
            try:
                self._spawn(sched)
            except Exception as exc:  # noqa: BLE001 — never let a job crash propagate
                logger.warning(
                    "Schedule %s firing failed: %s", sched.id, exc,
                )

        try:
            self._aps.add_job(_job, trigger=trigger, id=sched.id, replace_existing=True)
            self._registered_ids.append(sched.id)
        except Exception as exc:  # noqa: BLE001 — bad apscheduler install
            logger.warning(
                "apscheduler refused to add job %s: %s", sched.id, exc,
            )

    def _spawn(self, sched: Schedule) -> None:
        factory = self._registry.get(sched.task)

        async def _coro_factory(_record):  # noqa: ANN001 — record type from manager
            return await factory(dict(sched.args))

        self._manager.start_task(
            sched.name or sched.id,
            _coro_factory,
            timeout_seconds=sched.timeout_seconds,
            webhook_url=sched.webhook_url,
            metadata={"schedule_id": sched.id, "task": sched.task},
        )


# ---------------------------------------------------------------------------
# apscheduler glue
# ---------------------------------------------------------------------------


def _build_aps_scheduler() -> APSScheduler:
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - apscheduler is a hard dep when scheduling
        raise RuntimeError(
            "apscheduler is required for SchedulerLoop but is not installed. "
            "Run `pip install apscheduler`."
        ) from exc
    return AsyncIOScheduler(timezone="UTC")


def _build_cron_trigger(expr: str):
    try:
        from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "apscheduler is required for SchedulerLoop but is not installed."
        ) from exc
    return CronTrigger.from_crontab(expr, timezone="UTC")


# ---------------------------------------------------------------------------
# Env-var gate
# ---------------------------------------------------------------------------


def scheduler_enabled() -> bool:
    """True iff the operator opted in via ``RAGBOT_SCHEDULER=1``."""
    value = os.environ.get(SCHEDULER_ENV, "").strip().lower()
    return value in ("1", "true", "yes", "on")


__all__ = [
    "DEFAULT_SCHEDULES_PATH",
    "SCHEDULER_ENV",
    "Schedule",
    "ScheduleStore",
    "SchedulerLoop",
    "scheduler_enabled",
]
