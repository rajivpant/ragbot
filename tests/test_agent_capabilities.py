"""Tests for sub-agent dispatch, sandboxed execution, and the self-grading loop.

Round 4b of Phase 1 layers three capabilities on top of the agent-loop
core that Round 4a shipped:

  - Sub-agent dispatch (SUBAGENT_DISPATCH action type, parallel child
    AgentLoop runs)
  - Sandboxed code execution (SANDBOX_EXEC action type, provider-agnostic
    Sandbox interface, fail-closed by default)
  - Self-grading "Outcomes" loop (GRADE state, DONE_GRADED terminal,
    REPLAN injection on low score)

The tests use the same FakeLLMBackend / FakeMCPClient pattern as
``test_agent_loop.py`` plus two new fakes specific to this round:

  - FakeSandbox: returns pre-canned ExecutionResults keyed by SHA-1
    of the code body.
  - FakeSubAgentDispatcher: returns pre-canned GraphState results
    without actually running child loops (used for the replay test
    where we want determinism without recursion).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pytest

# Make ``src/`` importable just like the other test modules do.
_REPO_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
)
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)


from synthesis_engine.agent import (  # noqa: E402
    ActionType,
    AgentLoop,
    AgentState,
    DaytonaSandbox,
    DisabledSandbox,
    E2BSandbox,
    ExecutionResult,
    FilesystemCheckpointStore,
    GraphState,
    GradingResult,
    PermissionRegistry,
    PermissionResult,
    PlanStep,
    SANDBOX_EXEC_TOOL_NAME,
    SUBAGENT_DISPATCH_TOOL_NAME,
    Sandbox,
    SelfGrader,
    StepStatus,
    SubAgentDispatcher,
)
from synthesis_engine.agent.checkpoints import InMemoryCheckpointStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes — re-imported from test_agent_loop's style
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class FakeLLMBackend:
    """LLM backend that returns pre-canned responses by call signature.

    Two scripting modes: ``scripted`` is a flat queue consumed in order
    on every call. ``by_marker`` is a per-marker queue keyed by a
    substring of the user message (so PLAN / REPLAN / GRADE prompts can
    return different responses without depending on call order).
    """

    def __init__(
        self,
        scripted: Optional[List[str]] = None,
        *,
        by_marker: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self._scripted = list(scripted or [])
        self._by_marker = {k: list(v) for k, v in (by_marker or {}).items()}
        self.calls: List[Any] = []

    def complete(self, request: Any) -> FakeLLMResponse:
        self.calls.append(request)
        user_text = _user_text(request)
        # by_marker beats scripted so a test can inject a grader reply
        # without competing with the planner's queue.
        for marker, responses in self._by_marker.items():
            if marker in user_text and responses:
                return FakeLLMResponse(
                    text=responses.pop(0), model=_request_model(request),
                )
        if self._scripted:
            return FakeLLMResponse(
                text=self._scripted.pop(0), model=_request_model(request)
            )
        raise AssertionError(
            f"FakeLLMBackend: no scripted response for request "
            f"(user_text={user_text[:120]!r}, "
            f"marker_keys={list(self._by_marker)})"
        )


def _request_model(request: Any) -> str:
    if isinstance(request, dict):
        return str(request.get("model", "fake-model"))
    return getattr(request, "model", "fake-model")


def _user_text(request: Any) -> str:
    if isinstance(request, dict):
        msgs = request.get("messages") or []
    else:
        msgs = getattr(request, "messages", []) or []
    parts: List[str] = []
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "user":
            parts.append(str(m.get("content", "")))
    return "\n".join(parts)


class FakeMCPClient:
    """In-memory MCP-like client that returns canned tool responses."""

    def __init__(
        self,
        *,
        tools: Optional[List[str]] = None,
        responses: Optional[Dict[str, Callable[[Dict[str, Any]], Any]]] = None,
    ) -> None:
        self._tools = tools or []
        self._responses = responses or {}
        self.call_log: List[Dict[str, Any]] = []

    async def list_tools(self, server_id: str) -> List[Any]:
        return [
            {"name": name, "description": f"fake tool {name}"}
            for name in self._tools
        ]

    async def call_tool(
        self,
        server_id: str,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        self.call_log.append(
            {"server": server_id, "name": name, "arguments": arguments}
        )
        handler = self._responses.get(name)
        if handler is None:
            return {"text": f"{name} ok", "args": arguments}
        return handler(arguments or {})


class FakeSandbox(Sandbox):
    """Sandbox that returns pre-canned ExecutionResults keyed by code hash.

    Useful for deterministic tests of SANDBOX_EXEC dispatch and for
    replay tests where we need the same code to produce the same result
    on every call.
    """

    provider = "fake"
    supported_languages = ("python", "bash", "javascript", "typescript")

    def __init__(
        self,
        *,
        results_by_hash: Optional[Dict[str, ExecutionResult]] = None,
        default: Optional[ExecutionResult] = None,
    ) -> None:
        self._results = dict(results_by_hash or {})
        self._default = default or ExecutionResult(
            stdout="ok", exit_code=0, provider="fake"
        )
        self.call_log: List[Dict[str, Any]] = []

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha1(code.encode("utf-8")).hexdigest()

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 30,
        files: Optional[Dict[str, bytes]] = None,
    ) -> ExecutionResult:
        self.call_log.append(
            {
                "code": code,
                "language": language,
                "timeout_seconds": timeout_seconds,
                "files": dict(files or {}),
            }
        )
        return self._results.get(self.hash_code(code), self._default)


class ConcurrencyTrackingSandbox(FakeSandbox):
    """Sandbox that records the high-water concurrency count."""

    def __init__(self, *, default: Optional[ExecutionResult] = None) -> None:
        super().__init__(default=default)
        self._in_flight = 0
        self.max_observed = 0
        self._lock = asyncio.Lock()

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 30,
        files: Optional[Dict[str, bytes]] = None,
    ) -> ExecutionResult:
        async with self._lock:
            self._in_flight += 1
            if self._in_flight > self.max_observed:
                self.max_observed = self._in_flight
        try:
            # Yield to other coroutines so concurrency actually overlaps.
            await asyncio.sleep(0.01)
            return await super().execute(code, language, timeout_seconds, files)
        finally:
            async with self._lock:
                self._in_flight -= 1


# ---------------------------------------------------------------------------
# Helpers — canned plan/grader responses
# ---------------------------------------------------------------------------


def _plan_with_subagent(subtasks: List[str], max_parallel: int = 4) -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "fanout",
                    "action_type": "SUBAGENT_DISPATCH",
                    "target": "parallel-research",
                    "inputs": {
                        "subtasks": subtasks,
                        "max_parallel": max_parallel,
                    },
                    "description": "Fan out to N child loops.",
                }
            ]
        }
    )


def _plan_with_sandbox_exec(code: str, language: str = "python") -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "exec1",
                    "action_type": "SANDBOX_EXEC",
                    "target": language,
                    "inputs": {"code": code, "timeout_seconds": 10},
                    "description": "Run the snippet in the sandbox.",
                }
            ]
        }
    )


def _trivial_child_plan() -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "child-s1",
                    "action_type": "TOOL_CALL",
                    "target": "summarise",
                    "inputs": {"text": "child"},
                    "description": "Child step.",
                }
            ]
        }
    )


def _trivial_plan_json() -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "s1",
                    "action_type": "TOOL_CALL",
                    "target": "summarise",
                    "inputs": {"text": "hello"},
                    "description": "Summarise the input.",
                }
            ]
        }
    )


def _grader_pass_json(score: float = 0.95) -> str:
    return json.dumps(
        {
            "score": score,
            "rubric_breakdown": {"accuracy": score, "clarity": score},
            "suggested_revisions": [],
            "rationale": "Answer satisfies every criterion.",
        }
    )


def _grader_fail_json(score: float = 0.3) -> str:
    return json.dumps(
        {
            "score": score,
            "rubric_breakdown": {"accuracy": score, "clarity": 0.6},
            "suggested_revisions": [
                "tighten the wording around the second point",
                "add a concrete example",
            ],
            "rationale": "Answer is too vague.",
        }
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fs_checkpoint_store(tmp_path):
    return FilesystemCheckpointStore(base_dir=tmp_path / "checkpoints")


@pytest.fixture
def permissive_registry():
    """Allow every tool by default. Tests that exercise deny use isolated_registry."""
    reg = PermissionRegistry()
    reg.register("*", lambda _ctx: PermissionResult.allow("test-permissive"))
    return reg


@pytest.fixture
def isolated_registry():
    """Empty registry — strict fail-closed defaults apply."""
    return PermissionRegistry()


@pytest.fixture(scope="session")
def _session_tracer():
    """Session-scoped in-memory OTEL tracer for this file's tests.

    Both this file and ``test_agent_loop.py`` exercise the agent-loop
    observability hooks. The OpenTelemetry API refuses to replace the
    global TracerProvider once it has been set in a process, and the
    substrate's Prometheus reader can only register once. To stay
    compatible regardless of test order, we either:

      (a) call init_tracer with a fresh InMemorySpanExporter, when OTEL
          has not yet been initialised in this session, OR
      (b) attach a SimpleSpanProcessor that wraps our exporter to the
          provider that another test module already installed, when
          OTEL has been initialised. This way our exporter sees every
          span emitted under our fixture without fighting the global.
    """
    pytest.importorskip(
        "opentelemetry.sdk.trace.export.in_memory_span_exporter"
    )
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from synthesis_engine.observability import init_tracer, shutdown_tracer
    from synthesis_engine.observability.tracer import is_initialized

    exporter = InMemorySpanExporter()

    if is_initialized():
        # A sibling test module already initialised OTEL. Attach our
        # exporter to the live provider via a SimpleSpanProcessor so
        # spans emitted during our tests land in our exporter.
        provider = _otel_trace.get_tracer_provider()
        attached = False
        if hasattr(provider, "add_span_processor"):
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            attached = True
        if not attached:
            pytest.skip(
                "Cannot attach a span processor to the live provider."
            )
        yield exporter
        # No tear-down — we did not own the provider.
        return

    provider = init_tracer(
        service_name="synthesis_engine_agent_capabilities_test",
        exporter=exporter,
        force=True,
    )
    assert provider is not None
    yield exporter
    shutdown_tracer()


@pytest.fixture
def in_memory_tracer(_session_tracer):
    _session_tracer.clear()
    return _session_tracer


# ---------------------------------------------------------------------------
# Sub-agent dispatch — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subagent_dispatch_runs_three_children_in_parallel(
    fs_checkpoint_store, permissive_registry
):
    """The parent fans out three subtasks; each child reaches DONE; the parent aggregates."""

    # Parent plan: SUBAGENT_DISPATCH with three subtasks.
    parent_plan = _plan_with_subagent(
        ["subtask alpha", "subtask beta", "subtask gamma"]
    )
    # Each child runs a trivial child plan.
    child_plan = _trivial_child_plan()

    # The LLM is called 1 (parent plan) + 3 (child plans) = 4 times.
    llm = FakeLLMBackend(scripted=[parent_plan, child_plan, child_plan, child_plan])
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "child output"}},
    )

    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
    )
    final = await loop.run("aggregate three subtasks")

    assert final.current_state == AgentState.DONE
    fanout_step = final.plan[0]
    assert fanout_step.status == StepStatus.SUCCEEDED
    output = fanout_step.output
    assert isinstance(output, dict)
    assert output["subtasks"] == [
        "subtask alpha",
        "subtask beta",
        "subtask gamma",
    ]
    assert len(output["results"]) == 3
    for child in output["results"]:
        assert child["current_state"] == AgentState.DONE.value
        assert child["error_message"] is None
        # Each child's task_id is parent-linked.
        assert "/sub/" in child["task_id"]


# ---------------------------------------------------------------------------
# Sub-agent dispatch — one child fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subagent_dispatch_surfaces_child_failure(
    fs_checkpoint_store, permissive_registry
):
    """When a child loop reaches ERROR, the parent's plan step is FAILED with the error surfaced."""

    parent_plan = _plan_with_subagent(["good 1", "bad", "good 2"])
    child_plan = _trivial_child_plan()
    bad_plan = "not json at all"

    # Parent + replan plans (the loop will replan after the failure) + three child plans.
    # The bad child gets the invalid plan response so it transitions to ERROR.
    # The replan response (after the failure) is intentionally also failing so the loop hits ERROR.
    llm = FakeLLMBackend(
        scripted=[
            parent_plan,  # parent's PLAN
            child_plan,   # child 0 PLAN -> succeeds
            bad_plan,     # child 1 PLAN -> ERROR (invalid JSON)
            child_plan,   # child 2 PLAN -> succeeds
            # After the failure, parent retries the same step once more
            # (MAX_STEP_ATTEMPTS=2), then asks for a replan. We give it
            # plans that keep failing the same way so we can assert ERROR.
            child_plan,   # child 0 PLAN retry
            bad_plan,     # child 1 PLAN retry -> ERROR
            child_plan,   # child 2 PLAN retry
            parent_plan,  # replan
            child_plan, bad_plan, child_plan,
            child_plan, bad_plan, child_plan,
            parent_plan,
            child_plan, bad_plan, child_plan,
            child_plan, bad_plan, child_plan,
            parent_plan,
            child_plan, bad_plan, child_plan,
            child_plan, bad_plan, child_plan,
        ]
    )
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "ok"}},
    )

    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        max_iterations=60,
    )

    final = await loop.run("fan out with a bad child")

    # The loop should reach ERROR (every replan attempt failed the same way).
    # The parent's plan step error mentions the child failure.
    error_records = [s.error for s in final.plan if s.error]
    turn_summaries = [t.summary for t in final.turn_history]
    combined = " ".join((error_records or []) + (turn_summaries or []))
    assert (
        "child loops failed" in combined.lower()
        or "child[1]" in combined.lower()
        or "invalid plan" in combined.lower()
    ), f"expected child failure to surface; got: {combined[:300]}"


# ---------------------------------------------------------------------------
# Sub-agent dispatch — max_parallel honoured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subagent_dispatch_respects_max_parallel(
    fs_checkpoint_store, permissive_registry
):
    """SubAgentDispatcher caps concurrency to max_parallel using a semaphore."""

    observed: List[int] = []
    high_water = {"max": 0, "current": 0}
    lock = asyncio.Lock()

    # We monkey-patch the loop's drive_to_terminal so we can observe how
    # many child loops are in-flight without depending on the real loop's
    # sleep model. This is the most direct way to assert the semaphore.

    parent_state = GraphState.new("parent")
    parent_state.task_id = "parent-task"

    # A minimal stand-in loop that records concurrency.
    class StandinLoop:
        max_iterations = 10
        checkpoint_store = InMemoryCheckpointStore()

        def subagent_span(self, **kwargs):
            class _NoopCM:
                def __enter__(self):
                    return None
                def __exit__(self, *a):
                    return False
            return _NoopCM()

        async def drive_to_terminal(self, state: GraphState):
            async with lock:
                high_water["current"] += 1
                if high_water["current"] > high_water["max"]:
                    high_water["max"] = high_water["current"]
                observed.append(high_water["current"])
            try:
                # Sleep long enough that the next child has a chance
                # to actually enter run() concurrently.
                await asyncio.sleep(0.05)
                state.current_state = AgentState.DONE
                state.final_answer = f"done: {state.original_task}"
            finally:
                async with lock:
                    high_water["current"] -= 1
            return state

    standin = StandinLoop()
    dispatcher = SubAgentDispatcher(parent_loop=standin)  # type: ignore[arg-type]

    subtasks = ["t0", "t1", "t2", "t3", "t4", "t5"]
    results = await dispatcher.dispatch(parent_state, subtasks, max_parallel=2)

    assert len(results) == 6
    # Concurrency never exceeded the cap.
    assert high_water["max"] <= 2, (
        f"semaphore should have capped at 2; max observed was {high_water['max']}"
    )
    # And the cap was reached at least once (so the test is not vacuous).
    assert high_water["max"] >= 2, (
        f"with 6 tasks and max_parallel=2 we should see >= 2 in flight; "
        f"max observed was {high_water['max']}"
    )


# ---------------------------------------------------------------------------
# Permission gate denies SUBAGENT_DISPATCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permission_denies_subagent_dispatch(
    fs_checkpoint_store, isolated_registry
):
    """SUBAGENT_DISPATCH requires an explicit allow gate; default registry denies it."""

    parent_plan = _plan_with_subagent(["t1"])
    # The registry has nothing registered for "subagent_dispatch", so the
    # default fall-through gate fires — which denies unknown tools.
    llm = FakeLLMBackend(scripted=[parent_plan] * 12)  # plenty for replans
    loop = AgentLoop(
        llm_backend=llm,
        permission_registry=isolated_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
    )

    final = await loop.run("attempt subagent dispatch")
    # Permission denial appears either on a plan step or in the turn history.
    assert final.current_state == AgentState.ERROR
    denial_seen = any(
        "Permission denied" in (s.error or "") for s in final.plan
    ) or any(
        "Permission denied" in (t.summary or "")
        for t in final.turn_history
    )
    assert denial_seen, (
        "expected a Permission denied record on the step or in turn history"
    )


# ---------------------------------------------------------------------------
# Permission gate denies SANDBOX_EXEC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_permission_denies_sandbox_exec(
    fs_checkpoint_store, isolated_registry
):
    """SANDBOX_EXEC also routes through the permission registry; default denies."""

    plan = _plan_with_sandbox_exec("print(1)")
    llm = FakeLLMBackend(scripted=[plan] * 12)
    # The configured sandbox is the fail-closed default DisabledSandbox,
    # but we never get there — permission is denied earlier.
    loop = AgentLoop(
        llm_backend=llm,
        permission_registry=isolated_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
    )

    final = await loop.run("attempt sandbox exec")
    assert final.current_state == AgentState.ERROR
    denial_seen = any(
        "Permission denied" in (s.error or "") for s in final.plan
    ) or any(
        "Permission denied" in (t.summary or "")
        for t in final.turn_history
    )
    assert denial_seen


# ---------------------------------------------------------------------------
# DisabledSandbox returns -1 with a clear message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_sandbox_returns_actionable_error():
    sandbox = DisabledSandbox()
    result = await sandbox.execute("print('hi')")
    assert result.exit_code == -1
    assert result.provider == "disabled"
    assert "disabled" in result.stderr.lower()
    # The message should mention every real backend so the operator
    # has actionable next steps.
    assert "E2BSandbox" in result.stderr
    assert "DaytonaSandbox" in result.stderr


# ---------------------------------------------------------------------------
# E2BSandbox / DaytonaSandbox are importable without their SDKs
# ---------------------------------------------------------------------------


def test_e2b_sandbox_class_importable_without_sdk():
    """The E2BSandbox class must construct cleanly even when the e2b SDK is absent."""
    sandbox = E2BSandbox()  # no api key, no SDK — must not crash
    assert sandbox.provider == "e2b"


@pytest.mark.asyncio
async def test_e2b_sandbox_returns_error_without_api_key():
    sandbox = E2BSandbox(api_key=None)
    # Ensure E2B_API_KEY env var isn't set for this assertion.
    saved = os.environ.pop("E2B_API_KEY", None)
    try:
        result = await sandbox.execute("print(1)")
    finally:
        if saved is not None:
            os.environ["E2B_API_KEY"] = saved
    assert result.exit_code == -1
    assert "E2B_API_KEY" in result.stderr


def test_daytona_sandbox_class_importable_without_sdk():
    """DaytonaSandbox constructs even when httpx is unavailable / API_URL unset."""
    sandbox = DaytonaSandbox()
    assert sandbox.provider == "daytona"


@pytest.mark.asyncio
async def test_daytona_sandbox_returns_error_without_api_url():
    saved = os.environ.pop("DAYTONA_API_URL", None)
    try:
        sandbox = DaytonaSandbox(api_url=None)
        result = await sandbox.execute("print(1)")
    finally:
        if saved is not None:
            os.environ["DAYTONA_API_URL"] = saved
    assert result.exit_code == -1
    assert "DAYTONA_API_URL" in result.stderr


# ---------------------------------------------------------------------------
# SelfGrader — well-formed JSON parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_grader_parses_well_formed_response():
    llm = FakeLLMBackend(scripted=[_grader_pass_json(score=0.92)])
    grader = SelfGrader(llm_backend=llm, threshold=0.7)
    state = GraphState.new("compute 2+2")
    state.final_answer = "4"
    result = await grader.grade(state, rubric="Answer must be exactly 4.")
    assert isinstance(result, GradingResult)
    assert result.score == pytest.approx(0.92)
    assert result.passed is True
    assert result.error is None
    assert result.rubric_breakdown == {"accuracy": 0.92, "clarity": 0.92}
    assert result.suggested_revisions == []


# ---------------------------------------------------------------------------
# SelfGrader — malformed JSON is handled gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_grader_rejects_malformed_json_gracefully():
    llm = FakeLLMBackend(scripted=["this is not JSON {{{"])
    grader = SelfGrader(llm_backend=llm)
    state = GraphState.new("task")
    state.final_answer = "answer"
    result = await grader.grade(state, rubric="rubric")
    assert result.score == 0.0
    assert result.passed is False
    assert result.error is not None
    assert "JSON" in result.error or "valid" in result.error.lower()


# ---------------------------------------------------------------------------
# Self-grading happy path: pass → DONE_GRADED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_grading_happy_path_done_graded(
    fs_checkpoint_store, permissive_registry
):
    """High score from grader transitions the loop to DONE_GRADED."""

    plan = _trivial_plan_json()
    # Marker ordering matters here: AGENT_FINAL_ANSWER is checked first
    # so the grader prompt is matched before the planner prompt (which
    # only carries AVAILABLE_TOOLS). AVAILABLE_TOOLS is the planner's
    # distinguishing marker; replan would use PRIOR_PLAN.
    llm = FakeLLMBackend(
        by_marker={
            "AGENT_FINAL_ANSWER": [_grader_pass_json(0.95)],
            "PRIOR_PLAN": [plan],
            "AVAILABLE_TOOLS": [plan],
        }
    )
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "great answer"}},
    )
    grader = SelfGrader(llm_backend=llm, max_revision_rounds=2)
    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        grader=grader,
    )

    final = await loop.run("graded task", rubric="answer must mention 'great'")
    assert final.current_state == AgentState.DONE_GRADED
    grading = final.metadata.get("grading")
    assert grading is not None
    assert grading["score"] == pytest.approx(0.95)
    assert grading["passed"] is True
    # The GRADE state landed in the turn history.
    assert any(t.state == AgentState.GRADE for t in final.turn_history)


# ---------------------------------------------------------------------------
# Self-grading low score triggers REPLAN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_grading_low_score_triggers_replan(
    fs_checkpoint_store, permissive_registry
):
    """A failing grader score routes the loop back to REPLAN, then GRADE re-runs."""

    plan = _trivial_plan_json()
    # Order matters — AGENT_FINAL_ANSWER beats AVAILABLE_TOOLS; PRIOR_PLAN
    # beats AVAILABLE_TOOLS so a replan prompt is matched before the fresh
    # plan branch fires.
    llm = FakeLLMBackend(
        by_marker={
            "AGENT_FINAL_ANSWER": [
                _grader_fail_json(0.3),
                _grader_pass_json(0.9),
            ],
            "PRIOR_PLAN": [plan],
            "AVAILABLE_TOOLS": [plan],
        }
    )
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "improving"}},
    )
    grader = SelfGrader(llm_backend=llm, max_revision_rounds=2)
    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        grader=grader,
        max_iterations=40,
    )

    final = await loop.run("grade-then-replan", rubric="be specific")
    assert final.current_state == AgentState.DONE_GRADED
    # Two grading entries in history: the failed and then the passing.
    history = final.metadata.get("grading_history") or []
    assert len(history) == 2
    assert history[0]["passed"] is False
    assert history[1]["passed"] is True
    # grading_rounds counted the one replan we made.
    assert final.metadata.get("grading_rounds") == 1


# ---------------------------------------------------------------------------
# Self-grading respects max_revision_rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_self_grading_respects_revision_budget(
    fs_checkpoint_store, permissive_registry
):
    """When the budget runs out the loop transitions to DONE_GRADED with passed=False."""

    plan = _trivial_plan_json()
    # Always fail the grader; budget=1 means at most one replan attempt.
    llm = FakeLLMBackend(
        by_marker={
            "AGENT_FINAL_ANSWER": [
                _grader_fail_json(0.2),
                _grader_fail_json(0.25),
                _grader_fail_json(0.3),
            ],
            "PRIOR_PLAN": [plan, plan, plan],
            "AVAILABLE_TOOLS": [plan],
        }
    )
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "still bad"}},
    )
    grader = SelfGrader(llm_backend=llm, max_revision_rounds=1)
    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        grader=grader,
        max_iterations=40,
    )

    final = await loop.run("force budget exhaustion", rubric="impossible")
    assert final.current_state == AgentState.DONE_GRADED
    grading = final.metadata.get("grading")
    assert grading is not None
    assert grading["passed"] is False
    # Budget was 1; the loop should have done exactly 1 revision round.
    assert final.metadata.get("grading_rounds") == 1
    # And there should be 2 grading entries (the initial + the post-revision attempt).
    history = final.metadata.get("grading_history") or []
    assert len(history) == 2


# ---------------------------------------------------------------------------
# Loop without rubric skips GRADE (back-compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_without_rubric_skips_grade_state(
    fs_checkpoint_store, permissive_registry
):
    """No rubric means the loop's DONE state is terminal (Round 4a behaviour preserved)."""

    plan = _trivial_plan_json()
    llm = FakeLLMBackend(scripted=[plan])
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "x"}},
    )
    # Wire a grader but don't pass a rubric — the loop must not call it.
    grader = SelfGrader(llm_backend=llm)
    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        grader=grader,
    )

    final = await loop.run("ungraded task")  # no rubric=
    assert final.current_state == AgentState.DONE
    # No GRADE state should have been visited.
    states = [t.state for t in final.turn_history]
    assert AgentState.GRADE not in states
    assert AgentState.DONE_GRADED not in states


# ---------------------------------------------------------------------------
# Instrumentation: SUBAGENT_DISPATCH emits child spans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subagent_dispatch_emits_child_spans(
    fs_checkpoint_store, permissive_registry, in_memory_tracer
):
    parent_plan = _plan_with_subagent(["a", "b", "c"])
    child_plan = _trivial_child_plan()
    llm = FakeLLMBackend(scripted=[parent_plan, child_plan, child_plan, child_plan])
    mcp = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "ok"}},
    )
    loop = AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
    )

    await loop.run("emit child spans")

    spans = in_memory_tracer.get_finished_spans()
    # Each subagent span carries the role="subagent" attribute.
    subagent_spans = [
        s for s in spans
        if (s.attributes or {}).get("synthesis.agent.role") == "subagent"
    ]
    assert len(subagent_spans) == 3, (
        f"expected 3 sub-agent spans, got {len(subagent_spans)}; "
        f"all span names: {[s.name for s in spans]}"
    )
    # Each subagent span records the parent task_id.
    for span in subagent_spans:
        attrs = span.attributes or {}
        assert "synthesis.agent.parent_task_id" in attrs


# ---------------------------------------------------------------------------
# Instrumentation: SANDBOX_EXEC emits a tool_span
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sandbox_exec_emits_tool_span(
    fs_checkpoint_store, permissive_registry, in_memory_tracer
):
    code = "print('hello world')"
    plan = _plan_with_sandbox_exec(code)
    llm = FakeLLMBackend(scripted=[plan])
    sandbox = FakeSandbox(
        results_by_hash={
            FakeSandbox.hash_code(code): ExecutionResult(
                stdout="hello world\n",
                exit_code=0,
                duration_seconds=0.123,
                provider="fake",
            )
        }
    )
    loop = AgentLoop(
        llm_backend=llm,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        sandbox=sandbox,
    )

    final = await loop.run("run code in sandbox")
    assert final.current_state == AgentState.DONE

    spans = in_memory_tracer.get_finished_spans()
    sandbox_spans = [
        s for s in spans
        if (s.attributes or {}).get("synthesis.sandbox.provider") is not None
    ]
    assert sandbox_spans, "expected at least one sandbox tool_span"
    attrs = sandbox_spans[0].attributes or {}
    assert attrs.get("synthesis.sandbox.provider") == "fake"
    assert attrs.get("synthesis.sandbox.language") == "python"
    # The post-execute span attribute records the exit code and duration.
    assert "synthesis.sandbox.exit_code" in attrs
    assert "synthesis.sandbox.duration_seconds" in attrs


# ---------------------------------------------------------------------------
# State serialization round-trip with new types
# ---------------------------------------------------------------------------


def test_state_round_trip_with_new_action_types_and_state_value():
    state = GraphState.new("round trip test")
    state.plan = [
        PlanStep(
            step_id="s1",
            action_type=ActionType.SUBAGENT_DISPATCH,
            target="parallel-research",
            inputs={"subtasks": ["a", "b"], "max_parallel": 2},
        ),
        PlanStep(
            step_id="s2",
            action_type=ActionType.SANDBOX_EXEC,
            target="python",
            inputs={"code": "x = 1\nprint(x)"},
        ),
    ]
    state.current_state = AgentState.GRADE
    state.metadata["grading"] = {
        "score": 0.8,
        "passed": True,
        "rubric_breakdown": {"accuracy": 0.8},
        "suggested_revisions": [],
        "rationale": "good",
        "error": None,
    }

    once = state.to_dict()
    rebuilt = GraphState.from_dict(once)
    twice = rebuilt.to_dict()
    assert once == twice
    assert rebuilt.plan[0].action_type == ActionType.SUBAGENT_DISPATCH
    assert rebuilt.plan[1].action_type == ActionType.SANDBOX_EXEC
    assert rebuilt.current_state == AgentState.GRADE

    # DONE_GRADED round-trips as well.
    state.current_state = AgentState.DONE_GRADED
    redo = GraphState.from_dict(state.to_dict())
    assert redo.current_state == AgentState.DONE_GRADED


# ---------------------------------------------------------------------------
# Replay across SUBAGENT_DISPATCH + SANDBOX_EXEC reproduces the final state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replay_with_subagent_and_sandbox_steps(
    fs_checkpoint_store, permissive_registry
):
    """Run a loop with both new action types, then replay from a mid checkpoint."""

    code = "print('determinism')"
    parent_plan = json.dumps(
        {
            "steps": [
                {
                    "step_id": "fanout",
                    "action_type": "SUBAGENT_DISPATCH",
                    "target": "parallel-research",
                    "inputs": {
                        "subtasks": ["t1", "t2"],
                        "max_parallel": 2,
                    },
                    "description": "Fan out.",
                },
                {
                    "step_id": "exec1",
                    "action_type": "SANDBOX_EXEC",
                    "target": "python",
                    "inputs": {"code": code},
                    "description": "Run code.",
                },
            ]
        }
    )
    child_plan = _trivial_child_plan()

    sandbox = FakeSandbox(
        results_by_hash={
            FakeSandbox.hash_code(code): ExecutionResult(
                stdout="determinism\n",
                exit_code=0,
                provider="fake",
            )
        }
    )

    # First run.
    llm1 = FakeLLMBackend(scripted=[parent_plan, child_plan, child_plan])
    mcp1 = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "deterministic"}},
    )
    loop1 = AgentLoop(
        llm_backend=llm1,
        mcp_client=mcp1,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        sandbox=sandbox,
    )
    final_a = await loop1.run("replay across new step types")
    assert final_a.current_state == AgentState.DONE
    # Both steps succeeded.
    assert all(s.status == StepStatus.SUCCEEDED for s in final_a.plan)

    parent_checkpoints = await fs_checkpoint_store.list_checkpoints(
        final_a.task_id
    )
    assert len(parent_checkpoints) >= 3
    mid = parent_checkpoints[1]

    # Second run via replay.
    llm2 = FakeLLMBackend(scripted=[parent_plan, child_plan, child_plan])
    mcp2 = FakeMCPClient(
        tools=["summarise"],
        responses={"summarise": lambda args: {"text": "deterministic"}},
    )
    loop2 = AgentLoop(
        llm_backend=llm2,
        mcp_client=mcp2,
        permission_registry=permissive_registry,
        checkpoint_store=fs_checkpoint_store,
        default_mcp_server="local",
        sandbox=sandbox,
    )
    final_b = await loop2.replay(final_a.task_id, from_state_idx=mid)
    assert final_b.current_state == AgentState.DONE
    # The deterministic substrates reproduce the same plan-step outputs.
    assert final_b.step_results.keys() == final_a.step_results.keys()
    # The sandbox step produced the same stdout in both runs.
    exec_result_a = final_a.step_results["exec1"]
    exec_result_b = final_b.step_results["exec1"]
    assert exec_result_a["stdout"] == exec_result_b["stdout"]
    assert exec_result_a["exit_code"] == exec_result_b["exit_code"]
