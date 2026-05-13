"""Graph state dataclasses for the agent loop.

The agent loop is a finite-state machine whose entire working memory
lives in a single serialisable :class:`GraphState` dataclass. Every
state transition produces a new ``GraphState`` value that the
checkpoint store persists to disk; replay reconstructs the loop from any
saved checkpoint.

Serialisation contract:

  - All fields are JSON-friendly: enums serialise as their string value,
    timestamps as ISO-8601 strings, dataclasses as nested dicts.
  - ``GraphState.to_dict()`` produces a deterministic JSON-friendly dict
    suitable for ``json.dumps``. ``GraphState.from_dict()`` is the
    inverse and is round-trip-idempotent.

The dataclasses avoid third-party validation libraries (no pydantic) so
that ``from_dict`` is fast, transparent, and inspectable; the substrate
layer below uses pydantic for its on-the-wire contracts where that's
appropriate, but the agent state is intentionally a plain dataclass
graph because it is the agent's hot path.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentState(str, enum.Enum):
    """The finite set of states the loop can be in.

    Ordering matters for human readability of trace timelines:

        INIT        — initial state; loop has not run any transition yet.
        PLAN        — produce or refresh the plan via an LLM call.
        EXECUTE     — run the next pending step in the plan.
        EVALUATE    — inspect the step result; decide DONE / EXECUTE / REPLAN.
        REPLAN      — a step failed (or evaluation said the plan is wrong);
                      produce a new plan that incorporates the failure.
        DONE        — every step succeeded. Terminal unless a rubric was
                      supplied — in that case the loop transitions to GRADE.
        GRADE       — score the final answer against a rubric via an LLM
                      call; route to DONE_GRADED or REPLAN with revisions.
        DONE_GRADED — terminal: the grader produced a final verdict
                      (passed or not — the verdict lives in metadata).
        ERROR       — terminal: an unrecoverable error stopped the loop.
    """

    INIT = "INIT"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    EVALUATE = "EVALUATE"
    REPLAN = "REPLAN"
    DONE = "DONE"
    GRADE = "GRADE"
    DONE_GRADED = "DONE_GRADED"
    ERROR = "ERROR"


class ActionType(str, enum.Enum):
    """The kinds of actions a plan step can dispatch.

    TOOL_CALL          — call an MCP tool. ``target`` is the tool name
                         (optionally ``server_id::tool_name`` to disambiguate);
                         ``inputs`` is the tool's argument dict.
    LLM_CALL           — call the LLM backend. ``target`` is a model id;
                         ``inputs`` carries ``messages`` and optional
                         generation parameters.
    MEMORY_QUERY       — call the memory retriever. ``target`` is a tier
                         hint (or empty); ``inputs`` carries the query
                         text and workspace.
    SUBAGENT_DISPATCH  — dispatch one or more child agent loops in
                         parallel. ``target`` is informational (e.g.,
                         "parallel-research"); ``inputs.subtasks`` is a
                         list of natural-language sub-task strings;
                         ``inputs.max_parallel`` caps concurrency.
    SANDBOX_EXEC       — run untrusted code inside the configured
                         sandbox. ``target`` is the language id
                         (``"python"`` by default); ``inputs.code`` is
                         the source; ``inputs.files`` is an optional
                         {path: base64} mapping uploaded before
                         execution; ``inputs.timeout_seconds`` overrides
                         the default 30-second wall clock.
    """

    TOOL_CALL = "TOOL_CALL"
    LLM_CALL = "LLM_CALL"
    MEMORY_QUERY = "MEMORY_QUERY"
    SUBAGENT_DISPATCH = "SUBAGENT_DISPATCH"
    SANDBOX_EXEC = "SANDBOX_EXEC"


class StepStatus(str, enum.Enum):
    """Lifecycle of a single plan step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ContextBlock:
    """A block of retrieved context wired into the agent's prompt.

    Produced by the memory retriever during PLAN. ``source`` carries the
    tier label so the LLM can decide how much weight to give the block;
    ``provenance`` is a free-form dict (e.g., ``{"document_id": ...}``)
    that downstream code can use to render citations.
    """

    text: str
    source: str = "unknown"
    score: float = 0.0
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "score": self.score,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextBlock":
        return cls(
            text=data["text"],
            source=data.get("source", "unknown"),
            score=float(data.get("score", 0.0)),
            provenance=dict(data.get("provenance") or {}),
        )


@dataclass
class PlanStep:
    """A single step in the agent's plan."""

    step_id: str
    action_type: ActionType
    target: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    output: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "inputs": _json_safe(self.inputs),
            "status": self.status.value,
            "output": _json_safe(self.output),
            "error": self.error,
            "attempts": self.attempts,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            step_id=str(data["step_id"]),
            action_type=ActionType(data["action_type"]),
            target=str(data["target"]),
            inputs=dict(data.get("inputs") or {}),
            status=StepStatus(data.get("status", StepStatus.PENDING.value)),
            output=data.get("output"),
            error=data.get("error"),
            attempts=int(data.get("attempts", 0)),
            description=str(data.get("description", "")),
        )


@dataclass
class TurnRecord:
    """One entry in the agent's turn history (trace timeline).

    Recorded after every state transition so a debugger or replay can
    reconstruct the loop's path without re-running the whole thing.
    """

    state: AgentState
    timestamp: float
    summary: str = ""
    iteration: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "iteration": self.iteration,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TurnRecord":
        return cls(
            state=AgentState(data["state"]),
            timestamp=float(data["timestamp"]),
            summary=str(data.get("summary", "")),
            iteration=int(data.get("iteration", 0)),
        )


@dataclass
class GraphState:
    """The complete working memory of one agent run.

    The class is intentionally a plain dataclass so that ``from_dict``
    builds it without any framework. Round-trip through JSON is
    idempotent, which is what makes durable replay safe.
    """

    task_id: str
    original_task: str
    current_state: AgentState = AgentState.INIT
    plan: List[PlanStep] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    iteration_count: int = 0
    max_iterations: int = 30
    retrieved_context: List[ContextBlock] = field(default_factory=list)
    turn_history: List[TurnRecord] = field(default_factory=list)
    final_answer: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ----- constructors -----------------------------------------------------

    @classmethod
    def new(cls, task: str, *, max_iterations: int = 30) -> "GraphState":
        """Create a fresh state for a new task."""
        return cls(
            task_id=str(uuid.uuid4()),
            original_task=task,
            current_state=AgentState.INIT,
            max_iterations=max_iterations,
        )

    # ----- serialisation ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation of the state.

        The output is a plain dict whose values are all JSON-serialisable
        (str, int, float, bool, None, list, dict). Round-trippable.
        """
        return {
            "task_id": self.task_id,
            "original_task": self.original_task,
            "current_state": self.current_state.value,
            "plan": [step.to_dict() for step in self.plan],
            "step_results": _json_safe(self.step_results),
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "retrieved_context": [
                block.to_dict() for block in self.retrieved_context
            ],
            "turn_history": [turn.to_dict() for turn in self.turn_history],
            "final_answer": self.final_answer,
            "error_message": self.error_message,
            "metadata": _json_safe(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphState":
        """Reconstruct a GraphState from a dict produced by ``to_dict``."""
        return cls(
            task_id=str(data["task_id"]),
            original_task=str(data["original_task"]),
            current_state=AgentState(
                data.get("current_state", AgentState.INIT.value)
            ),
            plan=[
                PlanStep.from_dict(step) for step in (data.get("plan") or [])
            ],
            step_results=dict(data.get("step_results") or {}),
            iteration_count=int(data.get("iteration_count", 0)),
            max_iterations=int(data.get("max_iterations", 30)),
            retrieved_context=[
                ContextBlock.from_dict(b)
                for b in (data.get("retrieved_context") or [])
            ],
            turn_history=[
                TurnRecord.from_dict(t)
                for t in (data.get("turn_history") or [])
            ],
            final_answer=data.get("final_answer"),
            error_message=data.get("error_message"),
            metadata=dict(data.get("metadata") or {}),
        )

    # ----- helpers ----------------------------------------------------------

    def add_turn(self, state: AgentState, summary: str = "") -> None:
        """Append a turn-history record. Loop calls this on every transition."""
        self.turn_history.append(
            TurnRecord(
                state=state,
                timestamp=time.time(),
                summary=summary,
                iteration=self.iteration_count,
            )
        )

    def next_pending_step(self) -> Optional[PlanStep]:
        """Return the first pending step, or None if all complete/failed."""
        for step in self.plan:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def has_unresolved_failure(self) -> bool:
        """True iff at least one step is FAILED and no later steps remain."""
        return any(step.status == StepStatus.FAILED for step in self.plan)

    def is_terminal(self) -> bool:
        """True iff the current state is a terminal one.

        ``DONE`` is terminal only when no rubric is wired; with a rubric
        the loop transitions ``DONE -> GRADE -> DONE_GRADED`` (or back to
        REPLAN if the grader rejects the answer). The driver checks
        ``metadata["pending_grade"]`` to decide.
        """
        if self.current_state in (
            AgentState.ERROR,
            AgentState.DONE_GRADED,
        ):
            return True
        if self.current_state == AgentState.DONE:
            # DONE is terminal unless a rubric is pending evaluation.
            return not bool(self.metadata.get("pending_grade"))
        return False


# ---------------------------------------------------------------------------
# JSON-safe coercion
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Best-effort coercion of a Python value to a JSON-serialisable form.

    The agent state is deliberately constrained to JSON primitives, but
    callers occasionally hand us values from MCP / LLM responses that
    aren't dataclasses (e.g., pydantic models, ``datetime``s). This
    coercion handles the obvious cases; anything more exotic falls back
    to ``str()``. The contract is: round-trip through JSON, get back
    something equivalent enough for the loop to continue.
    """

    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    # pydantic v2
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_safe(model_dump())
        except Exception:
            pass
    # pydantic v1 / dataclasses
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            pass
    # dataclass
    from dataclasses import asdict, is_dataclass
    if is_dataclass(value):
        try:
            return _json_safe(asdict(value))
        except Exception:
            pass
    return str(value)
