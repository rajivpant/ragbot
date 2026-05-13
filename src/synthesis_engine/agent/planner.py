"""Planning + replanning helpers driven by the LLM backend.

The planner consumes the task, the list of available tools, and any
retrieved memory context, asks the LLM for a structured plan as JSON,
parses and validates the response, and returns a list of
:class:`PlanStep`. Replan consumes a failed :class:`GraphState`, asks
the LLM for a corrective plan that takes the failure context into
account, and returns the new step list.

The planner is intentionally minimal: one LLM call, one structured
response, one validation pass. Production extensions (tree-of-thought
planning, scratchpad reasoning, multiple planners voting) can wrap this
function — the substrate stays simple.

JSON contract the LLM is asked to follow:

    {
      "steps": [
        {
          "step_id": "s1",
          "action_type": "TOOL_CALL" | "LLM_CALL" | "MEMORY_QUERY",
          "target": "<tool name or model id>",
          "inputs": { ... },
          "description": "<one-line human-readable summary>"
        },
        ...
      ]
    }

The planner forgives the model adding a JSON-code-fence wrapper around
the object, and it tolerates the steps array being top-level instead of
nested under ``steps``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional

from .state import (
    ActionType,
    ContextBlock,
    GraphState,
    PlanStep,
    StepStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PlanValidationError(ValueError):
    """Raised when the LLM's plan response cannot be parsed/validated."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def make_plan(
    task: str,
    *,
    available_tools: Iterable[Any],
    retrieved_context: Optional[List[ContextBlock]] = None,
    llm_backend: Any,
    model: Optional[str] = None,
    max_tokens: int = 2048,
) -> List[PlanStep]:
    """Ask the LLM for a structured plan and return parsed PlanSteps.

    Args:
        task: The original user task in natural language.
        available_tools: Iterable of tool descriptors. Each item may be
            a string (tool name) or an object with ``name`` and optional
            ``description``/``inputSchema`` attributes (the shape MCP
            ``Tool`` carries). The planner reduces them to a name +
            description list inside the prompt.
        retrieved_context: Memory blocks the agent surfaced in the
            INIT/PLAN transition. The planner concatenates their text
            into the prompt under a ``CONTEXT`` section.
        llm_backend: Anything with ``complete(LLMRequest) -> LLMResponse``.
            Tests pass a fake; production passes the result of
            ``synthesis_engine.llm.get_llm_backend()``.
        model: The model id to use. Defaults to ``"planner-default"``
            so tests can route on it; production callers pass an
            ``engines.yaml`` model id.
        max_tokens: Generation budget for the LLM call.

    Returns:
        A list of :class:`PlanStep` with all-pending status, ready for
        the agent loop to execute.

    Raises:
        PlanValidationError: when the LLM's response cannot be parsed
            or validated against the expected schema.
    """

    prompt = _build_plan_prompt(
        task=task,
        available_tools=available_tools,
        retrieved_context=retrieved_context or [],
    )
    request = _build_request(
        model=model or "planner-default",
        prompt=prompt,
        max_tokens=max_tokens,
    )

    response = await _call_backend(llm_backend, request)
    return _parse_plan(response.text)


async def replan(
    failed_state: GraphState,
    *,
    llm_backend: Any,
    model: Optional[str] = None,
    max_tokens: int = 2048,
) -> List[PlanStep]:
    """Produce a corrective plan given a failed graph state.

    The replanner uses the original task plus the failure summary built
    from the most recent failed step(s) to ask the LLM for a revised
    plan that avoids the same failure.
    """

    failure_summary = _summarise_failures(failed_state)
    prompt = _build_replan_prompt(
        task=failed_state.original_task,
        failure_summary=failure_summary,
        retrieved_context=failed_state.retrieved_context,
        prior_plan=failed_state.plan,
    )
    request = _build_request(
        model=model or "planner-default",
        prompt=prompt,
        max_tokens=max_tokens,
    )

    response = await _call_backend(llm_backend, request)
    return _parse_plan(response.text)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_PLANNER_SYSTEM_PROMPT = (
    "You are the planner inside a synthesis-engineering agent loop. "
    "Given a user task, the list of available tools, and any retrieved "
    "context, produce a step-by-step plan as a JSON object.\n\n"
    "Output JSON only. The object must have a top-level key 'steps' "
    "whose value is an array of step objects. Each step has:\n"
    "  - step_id: short string id, unique within the plan\n"
    "  - action_type: one of TOOL_CALL | LLM_CALL | MEMORY_QUERY\n"
    "  - target: the tool name (TOOL_CALL), the model id (LLM_CALL), "
    "or a memory tier hint (MEMORY_QUERY)\n"
    "  - inputs: a JSON object with the arguments for the action\n"
    "  - description: one-line human-readable summary\n\n"
    "Keep the plan minimal: every step must move the task forward. "
    "Do not invent tools that are not in the available list."
)


def _build_plan_prompt(
    *,
    task: str,
    available_tools: Iterable[Any],
    retrieved_context: List[ContextBlock],
) -> List[Dict[str, str]]:
    """Assemble the message array for a fresh-plan LLM call."""

    user_blocks: List[str] = [f"TASK:\n{task}\n"]

    tools_block = _render_tools(available_tools)
    if tools_block:
        user_blocks.append(f"AVAILABLE_TOOLS:\n{tools_block}\n")

    if retrieved_context:
        rendered = "\n---\n".join(
            f"[{block.source}] {block.text}"
            for block in retrieved_context
        )
        user_blocks.append(f"CONTEXT:\n{rendered}\n")

    user_blocks.append(
        "Produce the plan now. Output JSON only, no prose around it."
    )

    return [
        {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_blocks)},
    ]


def _build_replan_prompt(
    *,
    task: str,
    failure_summary: str,
    retrieved_context: List[ContextBlock],
    prior_plan: List[PlanStep],
) -> List[Dict[str, str]]:
    """Assemble the message array for a replan LLM call."""

    prior_plan_rendered = json.dumps(
        [step.to_dict() for step in prior_plan],
        indent=2,
        default=str,
    )

    user_blocks: List[str] = [
        f"TASK:\n{task}\n",
        f"PRIOR_PLAN:\n{prior_plan_rendered}\n",
        f"FAILURE_SUMMARY:\n{failure_summary}\n",
    ]

    if retrieved_context:
        rendered = "\n---\n".join(
            f"[{block.source}] {block.text}"
            for block in retrieved_context
        )
        user_blocks.append(f"CONTEXT:\n{rendered}\n")

    user_blocks.append(
        "Produce a corrective plan that addresses the failure. "
        "Output JSON only."
    )

    return [
        {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_blocks)},
    ]


def _render_tools(available_tools: Iterable[Any]) -> str:
    lines: List[str] = []
    for tool in available_tools:
        if isinstance(tool, str):
            lines.append(f"  - {tool}")
            continue
        name = getattr(tool, "name", None) or (
            tool.get("name") if isinstance(tool, dict) else None
        )
        if not name:
            continue
        description = getattr(tool, "description", None) or (
            tool.get("description") if isinstance(tool, dict) else ""
        )
        if description:
            lines.append(f"  - {name}: {description}")
        else:
            lines.append(f"  - {name}")
    return "\n".join(lines)


def _summarise_failures(state: GraphState) -> str:
    """Build a human-readable failure summary for the replan prompt."""

    failed = [s for s in state.plan if s.status == StepStatus.FAILED]
    if not failed:
        return "(no FAILED steps recorded; replan was triggered for another reason)"

    lines: List[str] = []
    for step in failed:
        lines.append(
            f"- step {step.step_id} ({step.action_type.value} -> "
            f"{step.target}) failed after {step.attempts} attempt(s): "
            f"{step.error or 'no error message recorded'}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backend invocation
# ---------------------------------------------------------------------------


def _build_request(
    *,
    model: str,
    prompt: List[Dict[str, str]],
    max_tokens: int,
) -> Any:
    """Construct an LLMRequest, falling back to a dict if the dataclass
    cannot be imported (tests can construct stand-ins easily).
    """
    try:
        from synthesis_engine.llm.base import LLMRequest  # noqa: WPS433

        return LLMRequest(
            model=model,
            messages=prompt,
            max_tokens=max_tokens,
            temperature=0.2,
        )
    except Exception:
        # Substrate fallback so test stand-ins that don't pull in
        # synthesis_engine.llm can still call us.
        return {
            "model": model,
            "messages": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }


async def _call_backend(backend: Any, request: Any) -> Any:
    """Call ``backend.complete(request)`` whether complete is sync or async.

    The substrate's :class:`LLMBackend` defines a synchronous
    ``complete``, but the agent loop is async — so we use ``run_in_executor``
    semantics implicitly by allowing the backend to be either sync or async.
    Tests inject ``async def complete(...)`` mocks.
    """

    import asyncio

    result = backend.complete(request)
    if asyncio.iscoroutine(result):
        return await result
    return result


# ---------------------------------------------------------------------------
# Response parsing + validation
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*(?P<body>[\s\S]+?)```", re.MULTILINE
)


def _parse_plan(raw_text: str) -> List[PlanStep]:
    """Parse the LLM's plan response and validate it.

    Tolerates a leading/trailing code fence (Claude/Gemini both
    sometimes wrap JSON in ```json fences). Returns a list of PlanSteps
    with all-pending status. Raises :class:`PlanValidationError` on any
    structural problem.
    """

    if not raw_text or not raw_text.strip():
        raise PlanValidationError("Planner returned empty response.")

    body = raw_text.strip()

    # Strip an optional code fence.
    fence = _CODE_FENCE_RE.search(body)
    if fence:
        body = fence.group("body").strip()

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PlanValidationError(
            f"Plan response is not valid JSON: {exc}"
        ) from exc

    # The schema is { "steps": [...] }; tolerate a bare list at the top
    # level for forgiveness.
    if isinstance(parsed, list):
        raw_steps = parsed
    elif isinstance(parsed, dict):
        raw_steps = parsed.get("steps")
        if raw_steps is None:
            raise PlanValidationError(
                "Plan response missing required 'steps' key."
            )
    else:
        raise PlanValidationError(
            f"Plan response must be an object or list, got {type(parsed).__name__}."
        )

    if not isinstance(raw_steps, list):
        raise PlanValidationError(
            "'steps' must be a list."
        )
    if not raw_steps:
        raise PlanValidationError(
            "Plan must include at least one step."
        )

    steps: List[PlanStep] = []
    seen_ids: set = set()
    for idx, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise PlanValidationError(
                f"Step {idx} is not a JSON object."
            )
        step_id = str(raw.get("step_id") or f"s{idx + 1}")
        if step_id in seen_ids:
            raise PlanValidationError(
                f"Duplicate step_id {step_id!r} in plan."
            )
        seen_ids.add(step_id)

        raw_action = raw.get("action_type")
        if not raw_action:
            raise PlanValidationError(
                f"Step {step_id} missing 'action_type'."
            )
        try:
            action_type = ActionType(str(raw_action))
        except ValueError as exc:
            raise PlanValidationError(
                f"Step {step_id} has unknown action_type {raw_action!r}."
            ) from exc

        target = raw.get("target")
        if not target:
            raise PlanValidationError(
                f"Step {step_id} missing 'target'."
            )

        inputs = raw.get("inputs") or {}
        if not isinstance(inputs, dict):
            raise PlanValidationError(
                f"Step {step_id} 'inputs' must be an object."
            )

        steps.append(
            PlanStep(
                step_id=step_id,
                action_type=action_type,
                target=str(target),
                inputs=dict(inputs),
                description=str(raw.get("description", "")),
                status=StepStatus.PENDING,
            )
        )

    return steps


__all__ = [
    "PlanValidationError",
    "make_plan",
    "replan",
]
