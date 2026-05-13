"""Self-grading "Outcomes" loop for the agent.

After the agent's plan-and-execute path reaches DONE, an optional
:class:`SelfGrader` scores the final answer against a caller-supplied
rubric. The grader prompts the LLM with the task, the rubric, and the
loop's final output; parses the response as JSON; and returns a
structured :class:`GradingResult`.

The agent loop integrates the grader by:

1. Accepting an optional ``rubric=`` parameter on
   :meth:`AgentLoop.run`. When supplied, the loop records the rubric in
   ``state.metadata["rubric"]`` and flags ``pending_grade=True`` so the
   driver does not treat DONE as terminal.

2. Adding a GRADE state to the FSM. ``_handle_grade`` runs the grader
   on the final state, records ``state.metadata["grading"]`` with the
   result, and transitions to DONE_GRADED (passed) or REPLAN (low score
   with revision budget remaining).

3. Respecting a per-loop revision budget (``max_revision_rounds`` on
   :class:`SelfGrader`). When the budget runs out the loop accepts
   the current answer and transitions to DONE_GRADED with
   ``passed=False`` recorded — the operator sees the verdict but the
   loop doesn't spin forever.

The grader is intentionally strict about JSON parsing: a malformed
response is not a fatal error, but the resulting GradingResult records
a low score and a clear error message so the caller can tell apart
"the LLM rejected the answer" from "the LLM produced garbage."
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .state import GraphState


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


#: Score threshold below which the grader marks ``passed=False``. The
#: agent loop uses this default; callers can override via
#: ``SelfGrader(threshold=...)``.
DEFAULT_PASS_THRESHOLD: float = 0.7


@dataclass
class GradingResult:
    """The grader's verdict on one agent run.

    Attributes:
        score: Overall score in ``[0.0, 1.0]``. 0 means "completely
            failed the rubric"; 1 means "perfect by every criterion."
        passed: True iff ``score >= threshold``. The agent loop reads
            this to decide DONE_GRADED vs REPLAN.
        rubric_breakdown: Per-criterion scores, also in ``[0.0, 1.0]``.
            The grader prompts the LLM to score each rubric criterion
            independently so the agent can target revisions at the
            weakest dimension.
        suggested_revisions: Free-form list of strings the grader
            produced to guide a replan. Each entry is a short sentence
            describing what the answer needs to do better.
        rationale: Human-readable explanation the grader produced.
            Recorded in the trace; not used to drive replans.
        error: ``None`` on a successful parse; an operator-facing error
            message when the LLM returned malformed JSON or an
            otherwise unusable response. When ``error`` is non-None the
            score is forced to 0.0 and ``passed`` is False.
    """

    score: float = 0.0
    passed: bool = False
    rubric_breakdown: Dict[str, float] = field(default_factory=dict)
    suggested_revisions: List[str] = field(default_factory=list)
    rationale: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly dict; safe to embed in state.metadata."""
        return {
            "score": float(self.score),
            "passed": bool(self.passed),
            "rubric_breakdown": {k: float(v) for k, v in self.rubric_breakdown.items()},
            "suggested_revisions": list(self.suggested_revisions),
            "rationale": self.rationale,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Grader
# ---------------------------------------------------------------------------


_GRADER_SYSTEM_PROMPT = (
    "You are the grader for a synthesis-engineering agent loop. Given a "
    "task, a rubric, and the agent's final answer, score how well the "
    "answer meets the rubric.\n\n"
    "Output a single JSON object — no prose, no code fence. The object "
    "must have these keys:\n"
    "  - score: number between 0.0 and 1.0. 1.0 = perfect by every "
    "criterion; 0.0 = complete failure.\n"
    "  - rubric_breakdown: object mapping each rubric criterion (as a "
    "short string key) to a number between 0.0 and 1.0.\n"
    "  - suggested_revisions: array of short, actionable strings that "
    "tell the agent what to do differently. Empty if score is >= 0.9.\n"
    "  - rationale: one-paragraph explanation of the overall score.\n\n"
    "Be honest. Do not inflate the score; the agent loop uses your "
    "score to decide whether to keep trying."
)


class SelfGrader:
    """Score an agent's final answer against a caller-supplied rubric.

    The grader is a thin wrapper over an LLM call: it builds a prompt,
    calls the supplied backend, and parses the response. The agent loop
    constructs a SelfGrader once and reuses it across runs.

    Args:
        llm_backend: Anything with ``complete(request) -> response``.
            Sync or async — :func:`call_backend` handles both. Tests
            pass a fake; production passes
            ``synthesis_engine.llm.get_llm_backend()``.
        max_revision_rounds: How many ``GRADE -> REPLAN -> ... -> GRADE``
            cycles the loop tolerates before accepting whatever the
            agent produced. Default 2 — enough to try one targeted
            revision after the initial pass.
        threshold: Score at or above which the result is marked
            ``passed=True``. Default :data:`DEFAULT_PASS_THRESHOLD`.
        model: LLM model id for the grader. Default ``"grader-default"``
            so tests can route on the value; production callers pass an
            ``engines.yaml`` model id.
    """

    def __init__(
        self,
        llm_backend: Any,
        max_revision_rounds: int = 2,
        *,
        threshold: float = DEFAULT_PASS_THRESHOLD,
        model: Optional[str] = None,
    ) -> None:
        self._llm = llm_backend
        self._max_revision_rounds = int(max_revision_rounds)
        self._threshold = float(threshold)
        self._model = model or "grader-default"

    # ----- accessors --------------------------------------------------------

    @property
    def max_revision_rounds(self) -> int:
        return self._max_revision_rounds

    @property
    def threshold(self) -> float:
        return self._threshold

    # ----- public API -------------------------------------------------------

    async def grade(
        self,
        final_state: GraphState,
        rubric: str,
    ) -> GradingResult:
        """Score ``final_state`` against ``rubric`` and return a verdict."""

        prompt = self._build_prompt(
            task=final_state.original_task,
            rubric=rubric,
            final_answer=final_state.final_answer or "",
        )
        request = self._build_request(prompt)

        try:
            response = await _call_backend(self._llm, request)
            raw_text = getattr(response, "text", response)
        except Exception as exc:
            logger.warning("Grader LLM call failed: %s", exc)
            return GradingResult(
                score=0.0,
                passed=False,
                rationale="Grader LLM call failed.",
                error=f"LLM backend raised: {exc!r}",
            )

        return self._parse_response(raw_text)

    # ----- internals --------------------------------------------------------

    def _build_prompt(
        self,
        *,
        task: str,
        rubric: str,
        final_answer: str,
    ) -> List[Dict[str, str]]:
        user_text = (
            f"TASK:\n{task}\n\n"
            f"RUBRIC:\n{rubric}\n\n"
            f"AGENT_FINAL_ANSWER:\n{final_answer}\n\n"
            "Score the answer now. Output JSON only."
        )
        return [
            {"role": "system", "content": _GRADER_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

    def _build_request(self, prompt: List[Dict[str, str]]) -> Any:
        try:
            from synthesis_engine.llm.base import LLMRequest  # noqa: WPS433

            return LLMRequest(
                model=self._model,
                messages=prompt,
                max_tokens=1024,
                temperature=0.0,
            )
        except Exception:
            return {
                "model": self._model,
                "messages": prompt,
                "max_tokens": 1024,
                "temperature": 0.0,
            }

    def _parse_response(self, raw_text: str) -> GradingResult:
        """Parse the grader LLM's response, tolerating common deviations.

        The grader is asked to return raw JSON, but LLMs sometimes wrap
        it in a ```json fence anyway. We strip a fence if present, then
        ``json.loads``. Anything else produces a low-score result with
        a clear error rather than crashing.
        """

        if not raw_text or not str(raw_text).strip():
            return GradingResult(
                score=0.0,
                passed=False,
                error="Grader returned an empty response.",
            )

        body = str(raw_text).strip()
        fence = _CODE_FENCE_RE.search(body)
        if fence:
            body = fence.group("body").strip()

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            return GradingResult(
                score=0.0,
                passed=False,
                error=f"Grader response is not valid JSON: {exc}",
            )

        if not isinstance(parsed, dict):
            return GradingResult(
                score=0.0,
                passed=False,
                error=(
                    "Grader response must be a JSON object, got "
                    f"{type(parsed).__name__}."
                ),
            )

        try:
            score = float(parsed.get("score", 0.0))
        except (TypeError, ValueError):
            return GradingResult(
                score=0.0,
                passed=False,
                error="Grader 'score' field is not a number.",
            )
        score = max(0.0, min(1.0, score))

        breakdown_raw = parsed.get("rubric_breakdown") or {}
        breakdown: Dict[str, float] = {}
        if isinstance(breakdown_raw, dict):
            for key, value in breakdown_raw.items():
                try:
                    breakdown[str(key)] = max(0.0, min(1.0, float(value)))
                except (TypeError, ValueError):
                    continue

        revisions_raw = parsed.get("suggested_revisions") or []
        revisions: List[str] = []
        if isinstance(revisions_raw, list):
            revisions = [str(item) for item in revisions_raw if item]

        rationale = str(parsed.get("rationale") or "")

        return GradingResult(
            score=score,
            passed=score >= self._threshold,
            rubric_breakdown=breakdown,
            suggested_revisions=revisions,
            rationale=rationale,
            error=None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*(?P<body>[\s\S]+?)```", re.MULTILINE
)


async def _call_backend(backend: Any, request: Any) -> Any:
    """Call ``backend.complete`` whether sync or async (mirrors planner)."""

    import asyncio

    result = backend.complete(request)
    if asyncio.iscoroutine(result):
        return await result
    return result


__all__ = [
    "DEFAULT_PASS_THRESHOLD",
    "GradingResult",
    "SelfGrader",
]
