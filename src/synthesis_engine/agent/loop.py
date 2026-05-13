"""Agent-loop driver: an explicit-FSM plan-and-execute runtime.

The :class:`AgentLoop` consumes the substrate components (LLM backend,
MCP client, memory retriever, permission registry, checkpoint store)
and drives a task from INIT to DONE (or ERROR) one state transition at
a time. Every transition produces a new :class:`GraphState` value;
that value is observably traced and durably checkpointed.

Architectural notes:

* The transition table is a plain dict of async functions. There is no
  framework, no decorator magic, no DAG library. The whole point of
  this substrate is to keep the agent-loop semantics inspectable.

* The same code path drives both fresh runs (``run()``) and replays
  (``replay()``). Replay simply loads a checkpoint and re-invokes the
  driver loop; deterministic substrates (fake LLMs, fake tool clients)
  reproduce the same final state.

* Every state transition is wrapped in an ``agent_iteration_span`` so
  one OTEL span per transition lands in the tracer. Tool calls are
  additionally wrapped in ``tool_span``; LLM calls in
  ``chat_completion_span``.

* The loop's "plan and execute with replan on failure" pattern is
  pinned to a small, explicit retry budget per step (``MAX_STEP_ATTEMPTS``)
  before the loop transitions to REPLAN. Once REPLAN consumes its own
  budget (``max_iterations`` overall, plus a separate
  ``MAX_REPLANS`` count), the loop transitions to ERROR.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .checkpoints import CheckpointStore, FilesystemCheckpointStore
from .permissions import (
    PermissionRegistry,
    PermissionResult,
    ToolCallContext,
    get_default_registry,
)
from .planner import PlanValidationError, make_plan, replan
from .state import (
    ActionType,
    AgentState,
    ContextBlock,
    GraphState,
    PlanStep,
    StepStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


# Per-step retry budget before the loop escalates to REPLAN.
MAX_STEP_ATTEMPTS: int = 2

# How many REPLAN cycles the loop tolerates before giving up.
MAX_REPLANS: int = 3


MemoryRetriever = Callable[[str], Awaitable[List[ContextBlock]]]
"""Callable signature for the optional memory retriever.

Production callers wire this to a partial over
``synthesis_engine.memory.three_tier_retrieve``; tests pass a fake.
"""


# ---------------------------------------------------------------------------
# Helpers — instrumentation imports that degrade gracefully
# ---------------------------------------------------------------------------


def _import_instrumentation():
    """Return the observability context managers, falling back to no-ops.

    The substrate's observability module is always available in the
    repo, but the agent loop should never crash because OTEL is
    misconfigured. We import lazily and fall through to no-op context
    managers if anything goes wrong.
    """

    import contextlib

    try:
        from synthesis_engine.observability import (  # noqa: WPS433
            agent_iteration_span,
            chat_completion_span,
            tool_span,
        )
        return agent_iteration_span, chat_completion_span, tool_span
    except Exception:  # pragma: no cover - defensive
        @contextlib.contextmanager
        def _noop_cm(*_args, **_kwargs):
            yield None

        return _noop_cm, _noop_cm, _noop_cm


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


class AgentLoop:
    """Drive a single :class:`GraphState` from INIT to a terminal state."""

    def __init__(
        self,
        *,
        llm_backend: Any,
        mcp_client: Optional[Any] = None,
        memory_retriever: Optional[MemoryRetriever] = None,
        permission_registry: Optional[PermissionRegistry] = None,
        checkpoint_store: Optional[CheckpointStore] = None,
        max_iterations: int = 30,
        planner_model: Optional[str] = None,
        default_mcp_server: Optional[str] = None,
    ) -> None:
        self._llm = llm_backend
        self._mcp = mcp_client
        self._retriever = memory_retriever
        self._permissions = permission_registry or get_default_registry()
        self._checkpoints: CheckpointStore = (
            checkpoint_store or FilesystemCheckpointStore()
        )
        self._max_iterations = max_iterations
        self._planner_model = planner_model
        self._default_mcp_server = default_mcp_server

        (
            self._agent_iteration_span,
            self._chat_completion_span,
            self._tool_span,
        ) = _import_instrumentation()

        # Transition dispatch table — explicit, no framework.
        self._transitions: Dict[
            AgentState,
            Callable[[GraphState], Awaitable[GraphState]],
        ] = {
            AgentState.INIT: self._handle_init,
            AgentState.PLAN: self._handle_plan,
            AgentState.EXECUTE: self._handle_execute,
            AgentState.EVALUATE: self._handle_evaluate,
            AgentState.REPLAN: self._handle_replan,
        }

    # ----- public API -------------------------------------------------------

    async def run(self, task: str) -> GraphState:
        """Drive a fresh task from INIT to DONE or ERROR."""

        state = GraphState.new(task, max_iterations=self._max_iterations)
        state.add_turn(state.current_state, "Initial state.")
        await self._checkpoints.save(state)
        return await self._drive(state)

    async def step(self, state: GraphState) -> GraphState:
        """Execute exactly one transition and return the new state.

        Useful for tests and for stepping through an agent run from a
        debugger. The loop method that callers normally use is
        :meth:`run`.
        """

        if state.is_terminal():
            return state
        return await self._run_one_transition(state)

    async def replay(
        self,
        task_id: str,
        from_state_idx: Optional[int] = None,
    ) -> GraphState:
        """Resume a task from the given checkpoint and drive to a terminal state.

        Args:
            task_id: The task id whose checkpoint stream to replay.
            from_state_idx: Specific checkpoint index. None means the
                latest checkpoint.
        """

        if from_state_idx is None:
            state = await self._checkpoints.load_latest(task_id)
            if state is None:
                raise FileNotFoundError(
                    f"No checkpoints found for task {task_id}"
                )
        else:
            state = await self._checkpoints.load(task_id, from_state_idx)
        if state.is_terminal():
            return state
        return await self._drive(state)

    # ----- internals --------------------------------------------------------

    async def _drive(self, state: GraphState) -> GraphState:
        """Loop until the state is terminal or max_iterations is hit."""

        while not state.is_terminal():
            if state.iteration_count >= state.max_iterations:
                state.current_state = AgentState.ERROR
                state.error_message = (
                    f"Reached max_iterations={state.max_iterations} "
                    "without terminating."
                )
                state.add_turn(
                    state.current_state, state.error_message,
                )
                await self._checkpoints.save(state)
                break
            state = await self._run_one_transition(state)
        return state

    async def _run_one_transition(self, state: GraphState) -> GraphState:
        """Run one transition, wrap it in instrumentation, persist a checkpoint."""

        with self._agent_iteration_span(
            iteration=state.iteration_count,
            session_id=state.task_id,
        ):
            handler = self._transitions.get(state.current_state)
            if handler is None:
                state.current_state = AgentState.ERROR
                state.error_message = (
                    f"No transition handler for state {state.current_state.value}"
                )
                state.add_turn(state.current_state, state.error_message)
            else:
                try:
                    state = await handler(state)
                except Exception as exc:
                    logger.exception(
                        "Unhandled exception in transition handler"
                    )
                    state.current_state = AgentState.ERROR
                    state.error_message = (
                        f"Transition handler raised: {exc!r}"
                    )
                    state.add_turn(
                        state.current_state, state.error_message,
                    )

        state.iteration_count += 1
        await self._checkpoints.save(state)
        return state

    # ----- transition handlers ----------------------------------------------

    async def _handle_init(self, state: GraphState) -> GraphState:
        """INIT -> PLAN (optionally with retrieved context attached)."""

        if self._retriever is not None:
            try:
                context = await self._retriever(state.original_task)
                state.retrieved_context = list(context or [])
            except Exception as exc:
                logger.warning("Memory retrieval failed: %s", exc)
                state.metadata["retrieval_error"] = str(exc)

        state.current_state = AgentState.PLAN
        state.add_turn(
            state.current_state,
            f"INIT done; {len(state.retrieved_context)} context block(s) retrieved.",
        )
        return state

    async def _handle_plan(self, state: GraphState) -> GraphState:
        """PLAN -> EXECUTE: ask the LLM for a plan and store it."""

        tools = await self._list_available_tools()
        try:
            plan = await make_plan(
                state.original_task,
                available_tools=tools,
                retrieved_context=state.retrieved_context,
                llm_backend=self._llm,
                model=self._planner_model,
            )
        except PlanValidationError as exc:
            state.current_state = AgentState.ERROR
            state.error_message = f"Planner produced an invalid plan: {exc}"
            state.add_turn(state.current_state, state.error_message)
            return state

        state.plan = plan
        state.current_state = AgentState.EXECUTE
        state.add_turn(
            state.current_state,
            f"PLAN done; {len(plan)} step(s) drafted.",
        )
        return state

    async def _handle_execute(self, state: GraphState) -> GraphState:
        """EXECUTE -> EVALUATE: run the next pending step."""

        step = state.next_pending_step()
        if step is None:
            # Nothing pending: jump straight to EVALUATE so the loop
            # decides DONE vs REPLAN based on the recorded outcomes.
            state.current_state = AgentState.EVALUATE
            state.add_turn(
                state.current_state, "EXECUTE: no pending step; evaluating."
            )
            return state

        step.status = StepStatus.RUNNING
        step.attempts += 1

        # Resolve any $ref entries in the step inputs against prior outputs.
        resolved_inputs = _resolve_inputs(step.inputs, state.step_results)

        try:
            output = await self._dispatch_step(state, step, resolved_inputs)
            step.output = output
            step.status = StepStatus.SUCCEEDED
            state.step_results[step.step_id] = output
            summary = (
                f"EXECUTE step {step.step_id} ({step.action_type.value}) -> "
                "succeeded"
            )
        except PermissionError as exc:
            step.status = StepStatus.FAILED
            step.error = f"Permission denied: {exc}"
            summary = (
                f"EXECUTE step {step.step_id} permission-denied: {exc}"
            )
        except Exception as exc:
            logger.warning(
                "Step %s failed (attempt %s): %s",
                step.step_id,
                step.attempts,
                exc,
            )
            if step.attempts < MAX_STEP_ATTEMPTS:
                step.status = StepStatus.PENDING
                step.error = str(exc)
                summary = (
                    f"EXECUTE step {step.step_id} failed attempt "
                    f"{step.attempts}; will retry."
                )
            else:
                step.status = StepStatus.FAILED
                step.error = str(exc)
                summary = (
                    f"EXECUTE step {step.step_id} failed after "
                    f"{step.attempts} attempts: {exc}"
                )

        state.current_state = AgentState.EVALUATE
        state.add_turn(state.current_state, summary)
        return state

    async def _handle_evaluate(self, state: GraphState) -> GraphState:
        """EVALUATE -> DONE | EXECUTE | REPLAN."""

        # FAILED step: route to REPLAN (subject to the REPLAN budget).
        if state.has_unresolved_failure():
            replans = int(state.metadata.get("replans", 0))
            if replans >= MAX_REPLANS:
                state.current_state = AgentState.ERROR
                state.error_message = (
                    f"Exceeded MAX_REPLANS={MAX_REPLANS} without recovery."
                )
                state.add_turn(state.current_state, state.error_message)
                return state
            state.current_state = AgentState.REPLAN
            state.add_turn(
                state.current_state,
                f"EVALUATE: failure detected, transitioning to REPLAN "
                f"(replan #{replans + 1}).",
            )
            return state

        # Still steps to run? Loop back to EXECUTE.
        if state.next_pending_step() is not None:
            state.current_state = AgentState.EXECUTE
            state.add_turn(
                state.current_state, "EVALUATE: pending steps remain."
            )
            return state

        # All steps succeeded (or were skipped). The final answer is
        # the output of the last SUCCEEDED step by convention; an
        # explicit LLM_CALL with an answer-producing role can override
        # this by writing to ``metadata["final_answer"]`` itself.
        final = state.metadata.get("final_answer")
        if final is None:
            succeeded = [
                s for s in state.plan if s.status == StepStatus.SUCCEEDED
            ]
            if succeeded:
                final = succeeded[-1].output
        state.final_answer = _coerce_str(final)
        state.current_state = AgentState.DONE
        state.add_turn(state.current_state, "EVALUATE: all steps complete.")
        return state

    async def _handle_replan(self, state: GraphState) -> GraphState:
        """REPLAN -> EXECUTE with a new step list."""

        try:
            new_plan = await replan(
                state, llm_backend=self._llm, model=self._planner_model
            )
        except PlanValidationError as exc:
            state.current_state = AgentState.ERROR
            state.error_message = f"Replanner produced an invalid plan: {exc}"
            state.add_turn(state.current_state, state.error_message)
            return state

        # Track failed steps for audit, then replace plan with the new one.
        state.metadata["replans"] = int(state.metadata.get("replans", 0)) + 1
        archive = state.metadata.setdefault("replan_archive", [])
        archive.append([s.to_dict() for s in state.plan])

        state.plan = new_plan
        state.current_state = AgentState.EXECUTE
        state.add_turn(
            state.current_state,
            f"REPLAN done; new plan has {len(new_plan)} step(s).",
        )
        return state

    # ----- dispatch ---------------------------------------------------------

    async def _dispatch_step(
        self,
        state: GraphState,
        step: PlanStep,
        inputs: Dict[str, Any],
    ) -> Any:
        """Dispatch one plan step through the right substrate."""

        if step.action_type == ActionType.TOOL_CALL:
            return await self._dispatch_tool_call(state, step, inputs)
        if step.action_type == ActionType.LLM_CALL:
            return await self._dispatch_llm_call(state, step, inputs)
        if step.action_type == ActionType.MEMORY_QUERY:
            return await self._dispatch_memory_query(state, step, inputs)
        raise ValueError(
            f"Unknown ActionType {step.action_type!r} for step {step.step_id}"
        )

    async def _dispatch_tool_call(
        self,
        state: GraphState,
        step: PlanStep,
        inputs: Dict[str, Any],
    ) -> Any:
        if self._mcp is None:
            raise RuntimeError(
                "Plan requested a TOOL_CALL but no MCP client was wired."
            )

        # Permission gate.
        server_id, tool_name = _split_tool_target(
            step.target, self._default_mcp_server
        )
        verdict: PermissionResult = self._permissions.check(
            tool_name,
            arguments=inputs,
            context=ToolCallContext(
                tool_name=tool_name,
                arguments=inputs,
                server_id=server_id,
                task_id=state.task_id,
                metadata={"step_id": step.step_id},
            ),
        )
        if not verdict.allowed:
            raise PermissionError(verdict.reason)

        # Dispatch under a tool_span.
        with self._tool_span(tool_name=tool_name) as span:
            result = await self._mcp.call_tool(
                server_id, tool_name, arguments=inputs
            )
            try:
                if span is not None:
                    span.set_attribute(
                        "synthesis.tool.server_id", server_id
                    )
            except Exception:  # pragma: no cover - defensive
                pass
            return _coerce_tool_output(result)

    async def _dispatch_llm_call(
        self,
        state: GraphState,
        step: PlanStep,
        inputs: Dict[str, Any],
    ) -> Any:
        messages = inputs.get("messages")
        if not messages:
            # Convenience: the LLM call may have been written as just a
            # `prompt` string; wrap it.
            prompt = inputs.get("prompt") or ""
            if not prompt:
                raise ValueError(
                    f"LLM_CALL step {step.step_id} needs 'messages' or 'prompt'."
                )
            messages = [{"role": "user", "content": prompt}]

        # Allow per-step model overrides; otherwise use the configured planner_model.
        model = step.target or inputs.get("model") or "default"
        provider = inputs.get("provider") or _provider_from_model(model)
        max_tokens = int(inputs.get("max_tokens", 1024))
        temperature = inputs.get("temperature")

        with self._chat_completion_span(
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            request = _build_llm_request(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            response = self._llm.complete(request)
            if asyncio.iscoroutine(response):
                response = await response
            return getattr(response, "text", response)

    async def _dispatch_memory_query(
        self,
        state: GraphState,
        step: PlanStep,
        inputs: Dict[str, Any],
    ) -> Any:
        if self._retriever is None:
            raise RuntimeError(
                "Plan requested a MEMORY_QUERY but no retriever was wired."
            )
        query = inputs.get("query") or inputs.get("text") or state.original_task
        blocks = await self._retriever(query)
        return [b.to_dict() if isinstance(b, ContextBlock) else b for b in blocks]

    async def _list_available_tools(self) -> List[Any]:
        if self._mcp is None:
            return []
        if self._default_mcp_server is None:
            # Without a default server, we don't know which to list;
            # return an empty list rather than guessing.
            return []
        try:
            return await self._mcp.list_tools(self._default_mcp_server)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not list MCP tools: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_tool_target(
    target: str, default_server: Optional[str]
) -> tuple:
    """Split a ``server::tool`` target into (server_id, tool_name).

    A bare tool name uses ``default_server`` as the server id. Raises
    ``ValueError`` if no server can be resolved.
    """

    if "::" in target:
        server_id, tool_name = target.split("::", 1)
        return server_id, tool_name
    if default_server:
        return default_server, target
    raise ValueError(
        f"Tool target {target!r} has no server prefix and the agent loop "
        "has no default_mcp_server configured."
    )


def _resolve_inputs(
    inputs: Dict[str, Any], step_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve ``{"$ref": "step_id.output"}`` placeholders against prior results.

    Allows a plan step to reference the output of an earlier step. The
    syntax is ``{"$ref": "step_id"}`` for the whole output and
    ``{"$ref": "step_id.field"}`` for a dotted path into a dict output.
    Anything else passes through untouched.
    """

    def _resolve(value: Any) -> Any:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if ref is not None and isinstance(ref, str):
                parts = ref.split(".")
                head = parts[0]
                cursor: Any = step_results.get(head)
                for p in parts[1:]:
                    if isinstance(cursor, dict):
                        cursor = cursor.get(p)
                    else:
                        cursor = None
                        break
                return cursor
            return {k: _resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve(v) for v in value]
        return value

    return {k: _resolve(v) for k, v in inputs.items()}


def _build_llm_request(
    *,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: Optional[float],
) -> Any:
    try:
        from synthesis_engine.llm.base import LLMRequest  # noqa: WPS433

        return LLMRequest(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception:
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }


def _provider_from_model(model: str) -> str:
    """Best-effort provider extraction from a model id (e.g., ``anthropic/...``)."""
    if "/" in model:
        return model.split("/", 1)[0]
    return "unknown"


def _coerce_tool_output(result: Any) -> Any:
    """Reduce an MCP CallToolResult to a serialisable form.

    ``CallToolResult`` carries a ``.content`` list of typed content
    blocks and an ``.isError`` flag. For the agent state we capture the
    flag plus a list of text fragments; structured content is preserved
    under ``structured_content`` when present.
    """

    if result is None:
        return None
    if isinstance(result, (str, int, float, bool, list, dict)):
        return result

    payload: Dict[str, Any] = {}
    is_error = getattr(result, "isError", None)
    if is_error is not None:
        payload["is_error"] = bool(is_error)
        if is_error:
            raise RuntimeError(
                f"Tool reported error: {_extract_text(result) or 'unknown'}"
            )
    text = _extract_text(result)
    if text:
        payload["text"] = text
    structured = getattr(result, "structuredContent", None) or getattr(
        result, "structured_content", None
    )
    if structured is not None:
        payload["structured_content"] = structured
    return payload or _coerce_str(result)


def _extract_text(result: Any) -> str:
    """Pull a single text string out of an MCP CallToolResult."""

    content = getattr(result, "content", None)
    if not content:
        return ""
    parts: List[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        import json

        return json.dumps(value, default=str)
    except Exception:
        return str(value)


__all__ = [
    "AgentLoop",
    "MAX_REPLANS",
    "MAX_STEP_ATTEMPTS",
    "MemoryRetriever",
]
