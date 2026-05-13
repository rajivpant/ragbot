"""Sub-agent dispatch: parallel child :class:`AgentLoop` invocations.

The plan-and-execute pattern in :mod:`synthesis_engine.agent.loop` is
recursive: a parent loop's EXECUTE step can spawn N child loops with
their own task descriptions, each running on its own checkpoint stream
and contributing back its final state. This module provides the
:class:`SubAgentDispatcher` that orchestrates the fan-out under an
``asyncio.Semaphore`` so a parent never floods the substrate.

Design notes
============

* Each child task_id is derived from the parent's: ``"{parent}/sub/{i}"``.
  The filesystem checkpoint store flattens the slash for safety, so
  on-disk paths still work, but the LOGICAL parent/child relationship
  is preserved in the id itself — useful for trace queries.

* Child failures surface to the parent's plan step. The dispatcher
  returns the list of child :class:`GraphState` values; the parent's
  ``_handle_execute`` reads the list and raises if any child ended in
  ``ERROR``, which sends the parent's step through the standard
  attempt-and-replan path.

* Each child runs inside a parallel-research span ("agent.subagent") so
  the trace shows the fan-out clearly. The number of child spans equals
  the number of sub-tasks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, List, Optional

from .state import GraphState

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .loop import AgentLoop


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SubAgentFailure(RuntimeError):
    """Raised when one or more child agent loops ended in ERROR.

    Attributes:
        failures: A list of ``(index, error_message)`` tuples — one
            entry per child that did not reach a successful terminal
            state. The parent's plan step records this message so the
            replanner sees exactly which child failed.
        child_states: Every child's final :class:`GraphState`, in the
            order they were dispatched. Successful children appear here
            too, so the parent can still inspect their outputs.
    """

    def __init__(
        self,
        failures: List[tuple],
        child_states: List[GraphState],
    ) -> None:
        self.failures = failures
        self.child_states = child_states
        joined = "; ".join(
            f"child[{idx}]: {msg}" for idx, msg in failures
        )
        super().__init__(
            f"{len(failures)}/{len(child_states)} child loops failed: {joined}"
        )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class SubAgentDispatcher:
    """Run N child :class:`AgentLoop` invocations in parallel.

    The parent loop holds a reference to one dispatcher; on every
    SUBAGENT_DISPATCH step it calls :meth:`dispatch` with the parent
    state and the list of sub-task strings.

    The dispatcher is a thin wrapper around ``asyncio.gather`` plus an
    ``asyncio.Semaphore`` so the parent can cap the in-flight child
    count. The default cap is 4, which matches the typical "parallel
    research" use-case (one child per source) without overwhelming the
    LLM or the MCP server.
    """

    def __init__(self, parent_loop: "AgentLoop") -> None:
        self._parent = parent_loop

    # ----- public API -------------------------------------------------------

    async def dispatch(
        self,
        parent_state: GraphState,
        subtasks: List[str],
        max_parallel: int = 4,
    ) -> List[GraphState]:
        """Run one child loop per subtask, capped at ``max_parallel``.

        Args:
            parent_state: The parent loop's state. The dispatcher reads
                only ``task_id`` so it can mint per-child task ids; the
                state itself is not mutated here (the parent's
                ``_handle_execute`` handles state updates after this
                returns).
            subtasks: One natural-language sub-task per child loop.
                Must be non-empty.
            max_parallel: Cap on concurrent child loops. Must be >= 1.

        Returns:
            A list of child :class:`GraphState` values in the same
            order as ``subtasks``. Children that succeeded have
            ``current_state`` in ``{DONE, DONE_GRADED}``; failed
            children have ``ERROR``.

        Raises:
            ValueError: when ``subtasks`` is empty or ``max_parallel``
                is < 1.
            SubAgentFailure: when at least one child ended in ERROR.
                The caller (the parent's ``_handle_execute``) lets this
                propagate so the parent's plan step records the failure
                via the standard retry-and-replan path.
        """

        if not subtasks:
            raise ValueError("subtasks must be a non-empty list.")
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1.")

        semaphore = asyncio.Semaphore(max_parallel)

        async def run_child(idx: int, subtask: str) -> GraphState:
            async with semaphore:
                return await self._run_one_child(parent_state, idx, subtask)

        # Gather even on exceptions so all children get to terminate.
        child_results = await asyncio.gather(
            *(run_child(i, st) for i, st in enumerate(subtasks)),
            return_exceptions=True,
        )

        child_states: List[GraphState] = []
        failures: List[tuple] = []
        for idx, item in enumerate(child_results):
            if isinstance(item, BaseException):
                # An unexpected exception bubbled out of the child loop
                # itself. Synthesise a placeholder ERROR state so the
                # parent's step ID -> state map stays positional.
                placeholder = GraphState.new(subtasks[idx])
                placeholder.task_id = self._child_task_id(parent_state, idx)
                placeholder.error_message = (
                    f"Child agent loop raised: {item!r}"
                )
                placeholder.metadata["parent_task_id"] = parent_state.task_id
                placeholder.metadata["parent_subtask_index"] = idx
                # Use ERROR so downstream code sees a real terminal failure.
                from .state import AgentState  # local import to avoid cycle
                placeholder.current_state = AgentState.ERROR
                child_states.append(placeholder)
                failures.append((idx, str(item)))
                continue

            child_states.append(item)
            if item.error_message:
                failures.append((idx, item.error_message))
            elif item.current_state.value == "ERROR":
                failures.append(
                    (idx, item.error_message or "child ended in ERROR")
                )

        if failures:
            raise SubAgentFailure(failures, child_states)
        return child_states

    # ----- internals --------------------------------------------------------

    async def _run_one_child(
        self,
        parent_state: GraphState,
        idx: int,
        subtask: str,
    ) -> GraphState:
        """Drive one child loop and tag its state with the parent linkage.

        Each child has its own ``GraphState`` (and thus its own
        checkpoint stream); we only patch the task_id and a couple of
        provenance fields so a debugger can walk back to the parent.
        """

        # Wrap the child run in a "subagent" span so the trace shows the
        # fan-out as a nested span tree under the parent's iteration.
        span_cm = self._parent.subagent_span(
            parent_task_id=parent_state.task_id,
            child_index=idx,
        )

        with span_cm:
            child_state = await self._invoke_child(parent_state, idx, subtask)
            # Annotate the child's metadata with provenance and persist
            # one extra checkpoint so the link survives replays.
            child_state.metadata["parent_task_id"] = parent_state.task_id
            child_state.metadata["parent_subtask_index"] = idx
            try:
                await self._parent.checkpoint_store.save(child_state)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Failed to persist child checkpoint")
            return child_state

    async def _invoke_child(
        self,
        parent_state: GraphState,
        idx: int,
        subtask: str,
    ) -> GraphState:
        """Run the child loop via ``AgentLoop.run`` and override its task_id.

        ``AgentLoop.run`` mints a UUID by default. We need a parent-linked
        id, so we run the loop in stepped mode: build the initial state
        with the parent-derived id, then drive it.
        """

        from .state import AgentState  # local import to avoid cycle

        child_id = self._child_task_id(parent_state, idx)
        child_state = GraphState.new(
            subtask, max_iterations=self._parent.max_iterations
        )
        child_state.task_id = child_id
        child_state.add_turn(child_state.current_state, "Initial state.")
        child_state.metadata["parent_task_id"] = parent_state.task_id
        child_state.metadata["parent_subtask_index"] = idx

        await self._parent.checkpoint_store.save(child_state)
        try:
            return await self._parent.drive_to_terminal(child_state)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Child loop %s crashed", child_id)
            child_state.error_message = f"Child loop crashed: {exc!r}"
            child_state.current_state = AgentState.ERROR
            try:
                await self._parent.checkpoint_store.save(child_state)
            except Exception:
                pass
            return child_state

    @staticmethod
    def _child_task_id(parent_state: GraphState, idx: int) -> str:
        return f"{parent_state.task_id}/sub/{idx}"


__all__ = [
    "SubAgentDispatcher",
    "SubAgentFailure",
]
