"""Durable checkpoint store for the agent loop.

The loop persists a value of :class:`GraphState` after every state
transition so a crashed or paused agent can be resumed (or audited)
later. The store is filesystem-backed JSON, one file per transition,
arranged so that the per-task directory acts as a write-ahead log.

Layout::

    {base_dir}/{task_id}/0000.json   # state after the very first transition
    {base_dir}/{task_id}/0001.json   # state after the second transition
    ...

The four-digit zero-padding keeps the on-disk order lexicographic
without forcing a per-directory index file. ``list_checkpoints`` simply
sorts the filenames.

Atomic writes:

    JSON is written to ``{N:04d}.json.tmp``, fsynced, then renamed to
    the final name. The rename is atomic on every POSIX file system,
    so a crash mid-write cannot leave a half-written checkpoint that
    later parses as truncated JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol

from .state import GraphState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class CheckpointStore(Protocol):
    """Minimal protocol for any checkpoint persistence layer.

    Implementing this protocol is enough to plug a custom store (e.g.,
    Redis, SQLite) into the agent loop.
    """

    async def save(self, state: GraphState) -> int:
        """Append ``state`` and return its checkpoint index (0-based)."""

    async def load(self, task_id: str, n: int) -> GraphState:
        """Load checkpoint ``n`` for ``task_id``."""

    async def list_checkpoints(self, task_id: str) -> List[int]:
        """Return the sorted list of checkpoint indices for ``task_id``."""


# ---------------------------------------------------------------------------
# Filesystem implementation
# ---------------------------------------------------------------------------


_CHECKPOINT_RE = re.compile(r"^(\d{4,})\.json$")


def _default_base_dir() -> Path:
    """Resolve the default checkpoint root.

    Honours ``SYNTHESIS_AGENT_CHECKPOINT_DIR`` for redirection in tests
    and CI; otherwise falls back to ``~/.synthesis/agent-checkpoints``.
    """

    override = os.environ.get("SYNTHESIS_AGENT_CHECKPOINT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".synthesis" / "agent-checkpoints"


class FilesystemCheckpointStore:
    """JSON-on-disk implementation of :class:`CheckpointStore`."""

    def __init__(self, base_dir: Optional[os.PathLike] = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _default_base_dir()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ----- save / load ------------------------------------------------------

    async def save(self, state: GraphState) -> int:
        """Atomically append the state and return its index.

        The save method itself is sync at heart — disk I/O — but the
        agent loop is async, so we expose it as an async method to keep
        the calling convention uniform. The async cost is zero
        (`await`-less wait for a sync call).
        """

        task_dir = self._task_dir(state.task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        existing = self._list_indices(task_dir)
        next_idx = (max(existing) + 1) if existing else 0
        target = task_dir / f"{next_idx:04d}.json"

        # Write atomically: write to a tmp file, fsync, rename.
        payload = json.dumps(
            state.to_dict(),
            indent=2,
            default=str,
            sort_keys=False,
        ).encode("utf-8")

        fd, tmp_path = tempfile.mkstemp(
            prefix=f"{next_idx:04d}.",
            suffix=".json.tmp",
            dir=task_dir,
        )
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, target)
        except Exception:
            # Clean up the tmp file if the rename never happened.
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

        return next_idx

    async def load(self, task_id: str, n: int) -> GraphState:
        """Load checkpoint ``n`` for ``task_id`` and return a GraphState."""

        target = self._task_dir(task_id) / f"{n:04d}.json"
        if not target.exists():
            raise FileNotFoundError(
                f"Checkpoint {n} not found for task {task_id} at {target}"
            )
        data = json.loads(target.read_text("utf-8"))
        return GraphState.from_dict(data)

    async def list_checkpoints(self, task_id: str) -> List[int]:
        """Return the sorted list of checkpoint indices."""

        task_dir = self._task_dir(task_id)
        if not task_dir.exists():
            return []
        return self._list_indices(task_dir)

    async def load_latest(self, task_id: str) -> Optional[GraphState]:
        """Return the most-recent checkpoint or None if none exist."""

        indices = await self.list_checkpoints(task_id)
        if not indices:
            return None
        return await self.load(task_id, indices[-1])

    # ----- inspection helpers (Phase 4 — CLI replay support) ---------------

    def list_recent_task_ids(self, limit: int = 100) -> List[str]:
        """Return the task ids in the store, most-recently-modified first.

        The recency signal is the mtime of each task directory's most
        recent checkpoint file. Directories with no parseable checkpoint
        files are skipped (the store may briefly contain a freshly-made
        task directory before its first save lands).

        Args:
            limit: Maximum number of task ids to return. Negative or zero
                values return an empty list.
        """

        if limit <= 0:
            return []
        if not self._base_dir.exists():
            return []

        scored: List[tuple] = []
        for entry in self._base_dir.iterdir():
            if not entry.is_dir():
                continue
            indices = self._list_indices(entry)
            if not indices:
                continue
            latest_file = entry / f"{indices[-1]:04d}.json"
            try:
                mtime = latest_file.stat().st_mtime
            except OSError:
                continue
            scored.append((mtime, entry.name))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [name for _mtime, name in scored[:limit]]

    def summarise_checkpoint(self, task_id: str, n: int) -> Dict[str, Any]:
        """Return a lightweight summary of a checkpoint without full state load.

        The summary carries enough information for ``ragbot agent
        checkpoints <task_id>`` to render a useful inspection table:
        the FSM state, the iteration count, the plan length, and a
        one-line synopsis pulled from the most recent turn record (or
        the final answer / error message when the checkpoint is
        terminal).

        Raises ``FileNotFoundError`` when the checkpoint does not exist.
        """

        target = self._task_dir(task_id) / f"{n:04d}.json"
        if not target.exists():
            raise FileNotFoundError(
                f"Checkpoint {n} not found for task {task_id} at {target}"
            )
        try:
            data = json.loads(target.read_text("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"Checkpoint {n} for task {task_id} is unreadable: {exc}"
            ) from exc

        plan = data.get("plan") or []
        turn_history = data.get("turn_history") or []
        last_summary = ""
        if turn_history:
            last = turn_history[-1] or {}
            last_summary = str(last.get("summary") or "")

        # Choose a one-line synopsis with a sensible precedence:
        # explicit final answer > error message > most recent turn line.
        synopsis = (
            data.get("final_answer")
            or data.get("error_message")
            or last_summary
            or ""
        )
        return {
            "state": data.get("current_state", "UNKNOWN"),
            "iteration_count": int(data.get("iteration_count", 0)),
            "plan_step_count": len(plan),
            "summary": str(synopsis),
        }

    # ----- helpers ----------------------------------------------------------

    def _task_dir(self, task_id: str) -> Path:
        # ``task_id`` should be a UUID-like string, but we sanitise just
        # in case a caller passes something with directory separators.
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", task_id)
        return self._base_dir / safe

    @staticmethod
    def _list_indices(task_dir: Path) -> List[int]:
        indices: List[int] = []
        for entry in task_dir.iterdir():
            if not entry.is_file():
                continue
            match = _CHECKPOINT_RE.match(entry.name)
            if not match:
                continue
            indices.append(int(match.group(1)))
        return sorted(indices)


# ---------------------------------------------------------------------------
# In-memory store (useful for tests)
# ---------------------------------------------------------------------------


class InMemoryCheckpointStore:
    """Volatile, dict-backed implementation of the protocol.

    Useful for tests that want to assert on the checkpoint stream
    without touching disk. Not thread-safe — single-task tests only.
    """

    def __init__(self) -> None:
        self._tasks: dict = {}

    async def save(self, state: GraphState) -> int:
        entries = self._tasks.setdefault(state.task_id, [])
        entries.append(json.loads(json.dumps(state.to_dict(), default=str)))
        return len(entries) - 1

    async def load(self, task_id: str, n: int) -> GraphState:
        entries = self._tasks.get(task_id) or []
        if n < 0 or n >= len(entries):
            raise FileNotFoundError(
                f"Checkpoint {n} not found for task {task_id} "
                f"(have {len(entries)})"
            )
        return GraphState.from_dict(entries[n])

    async def list_checkpoints(self, task_id: str) -> List[int]:
        return list(range(len(self._tasks.get(task_id) or [])))


__all__ = [
    "CheckpointStore",
    "FilesystemCheckpointStore",
    "InMemoryCheckpointStore",
]
