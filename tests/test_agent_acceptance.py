"""End-to-end acceptance test for Phase 1.3 of Ragbot v3.4.

The implementation plan calls out one canonical acceptance scenario for
the agent loop's HTTP surface:

    A multi-step task ("draft a one-pager, fact-check the claims, output
    a structured report") runs end-to-end with checkpoints; a
    checkpoint-replay reproduces the run; permission-gate violations are
    blocked with structured errors.

This module is that test, deliberately spelled out as a single
comprehensive scenario so a reader can convince themselves the FastAPI
agent surface meets the Phase 1.3 criteria in one read.

The 4-step plan exercises every dispatch path the loop knows about:

  1. LLM_CALL — draft a one-pager via the LLM backend.
  2. TOOL_CALL — fact-check the claims through an MCP "search" server.
  3. SANDBOX_EXEC — run a Python snippet inside a FakeSandbox to format
     the verified facts as a structured payload.
  4. LLM_CALL — synthesise the final structured report.

The test asserts:

  - the loop reaches DONE,
  - the final answer matches the synthesised report we scripted,
  - at least one checkpoint per state transition landed on disk,
  - a checkpoint-replay reproduces the same final state hash,
  - configuring the permission registry to deny ``search.fact_check``
    surfaces an HTTP 403 with the structured error body on a fresh
    invocation.

All substrates are fakes — no real LLM, MCP, or sandbox is invoked.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pytest

_REPO_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
)
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from synthesis_engine.agent import (  # noqa: E402
    AgentLoop,
    AgentState,
    ExecutionResult,
    FilesystemCheckpointStore,
    PermissionRegistry,
    PermissionResult,
    Sandbox,
)

from api.routers import agent as agent_router  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes — fully self-contained so the acceptance test reads as one unit
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class FakeLLMBackend:
    """LLM backend keyed by ``by_marker`` substrings of the user prompt.

    Each scripted plan-step LLM_CALL carries a distinguishing string in
    its user message; the planner's prompt carries ``AVAILABLE_TOOLS``;
    the grader (unused here) carries ``AGENT_FINAL_ANSWER``. Per-marker
    queues let us script the four LLM interactions without depending on
    call order.
    """

    def __init__(self, by_marker: Dict[str, List[str]]) -> None:
        self._by_marker = {k: list(v) for k, v in by_marker.items()}
        self.calls: List[Any] = []

    def complete(self, request: Any) -> FakeLLMResponse:
        self.calls.append(request)
        user_text = _user_text(request)
        for marker, responses in self._by_marker.items():
            if marker in user_text and responses:
                return FakeLLMResponse(
                    text=responses.pop(0), model=_request_model(request),
                )
        raise AssertionError(
            f"FakeLLMBackend: no scripted response for prompt "
            f"(user_text={user_text[:200]!r}; "
            f"markers={list(self._by_marker)})"
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
    """In-memory MCP-like client. Returns canned per-tool responses."""

    def __init__(
        self,
        *,
        tools: List[str],
        responses: Dict[str, Callable[[Dict[str, Any]], Any]],
    ) -> None:
        self._tools = list(tools)
        self._responses = dict(responses)
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
        handler = self._responses[name]
        return handler(arguments or {})


class FakeSandbox(Sandbox):
    """Sandbox that returns a single pre-canned ExecutionResult.

    The scenario only runs one snippet (the Python formatter) so a
    flat default result is all we need. The fixture passes the desired
    stdout/files_written.
    """

    provider = "fake"
    supported_languages = ("python", "bash", "javascript", "typescript")

    def __init__(self, *, default: ExecutionResult) -> None:
        self._default = default
        self.call_log: List[Dict[str, Any]] = []

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
        return self._default


# ---------------------------------------------------------------------------
# Scenario plan — the implementation-plan-mandated 4 steps
# ---------------------------------------------------------------------------


_PLAN_MARKER = "AVAILABLE_TOOLS"

# Distinguishing markers carried in the user message of each step's
# LLM_CALL so the FakeLLMBackend's by_marker routing can pick the right
# response.
_DRAFT_MARKER = "draft a one-pager"
_SYNTHESIS_MARKER = "synthesise the final structured report"

_DRAFT_TEXT = (
    "One-pager DRAFT: synthesis engineering reduces cycle time by "
    "fanning chat-first reasoning into reviewable artifacts. Two claims: "
    "(a) cycle time drops 30%, (b) review backlog clears 2x faster."
)

_FACT_CHECK_PAYLOAD: Dict[str, Any] = {
    "claims": [
        {"text": "cycle time drops 30%", "verified": True, "source": "internal-2026q1"},
        {"text": "review backlog clears 2x faster", "verified": True, "source": "internal-2026q1"},
    ]
}

_SANDBOX_FORMATTED_PAYLOAD: Dict[str, Any] = {
    "report_inputs": {
        "draft_excerpt": "synthesis engineering reduces cycle time",
        "verified_claims": [
            "cycle time drops 30%",
            "review backlog clears 2x faster",
        ],
    },
    "format_version": "1.0",
}

_FINAL_REPORT = (
    "FINAL_REPORT v1: synthesis engineering shortens cycle time (30%) "
    "and accelerates review (2x). Both claims verified against "
    "internal-2026q1."
)


def _phase_1_3_plan_json() -> str:
    """The 4-step plan that the acceptance scenario drives end-to-end."""

    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "draft",
                    "action_type": "LLM_CALL",
                    "target": "draft-model",
                    "inputs": {
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "Please draft a one-pager on synthesis "
                                    "engineering's cycle-time impact."
                                ),
                            }
                        ],
                    },
                    "description": "Draft the one-pager.",
                },
                {
                    "step_id": "fact_check",
                    "action_type": "TOOL_CALL",
                    "target": "search::search.fact_check",
                    "inputs": {
                        "claims": {"$ref": "draft"},
                    },
                    "description": "Fact-check the draft's claims.",
                },
                {
                    "step_id": "format",
                    "action_type": "SANDBOX_EXEC",
                    "target": "python",
                    "inputs": {
                        "code": (
                            "import json\n"
                            "print(json.dumps({'formatted': True}))\n"
                        ),
                        "timeout_seconds": 10,
                    },
                    "description": "Format the verified facts in the sandbox.",
                },
                {
                    "step_id": "synthesize",
                    "action_type": "LLM_CALL",
                    "target": "report-model",
                    "inputs": {
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "Please synthesise the final structured "
                                    "report from the verified facts."
                                ),
                            }
                        ],
                    },
                    "description": "Produce the final structured report.",
                },
            ]
        }
    )


def _phase_1_3_marker_scripts(num_plan_calls: int = 1) -> Dict[str, List[str]]:
    """Build the marker-keyed response queues the FakeLLMBackend serves.

    The scenario triggers four LLM calls during a fresh run:
      - one planner call (carries AVAILABLE_TOOLS),
      - the draft LLM_CALL,
      - the synthesise LLM_CALL.

    The TOOL_CALL and SANDBOX_EXEC steps do not hit the LLM, so they do
    not consume from these queues.
    """

    return {
        _PLAN_MARKER: [_phase_1_3_plan_json()] * num_plan_calls,
        _DRAFT_MARKER: [_DRAFT_TEXT],
        _SYNTHESIS_MARKER: [_FINAL_REPORT],
    }


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _build_loop(
    tmp_path,
    *,
    num_plan_calls: int = 1,
    permission_registry: Optional[PermissionRegistry] = None,
    extra_draft_responses: Optional[List[str]] = None,
    extra_synth_responses: Optional[List[str]] = None,
) -> AgentLoop:
    """Construct an AgentLoop bound to the canned scenario fakes."""

    markers = _phase_1_3_marker_scripts(num_plan_calls=num_plan_calls)
    if extra_draft_responses:
        markers[_DRAFT_MARKER].extend(extra_draft_responses)
    if extra_synth_responses:
        markers[_SYNTHESIS_MARKER].extend(extra_synth_responses)

    llm = FakeLLMBackend(by_marker=markers)
    mcp = FakeMCPClient(
        tools=["search.fact_check"],
        responses={"search.fact_check": lambda _args: _FACT_CHECK_PAYLOAD},
    )
    sandbox = FakeSandbox(
        default=ExecutionResult(
            stdout=json.dumps(_SANDBOX_FORMATTED_PAYLOAD),
            stderr="",
            exit_code=0,
            provider="fake",
        )
    )

    if permission_registry is None:
        permission_registry = PermissionRegistry()
        permission_registry.register(
            "*", lambda _ctx: PermissionResult.allow("acceptance default"),
        )

    return AgentLoop(
        llm_backend=llm,
        mcp_client=mcp,
        permission_registry=permission_registry,
        checkpoint_store=FilesystemCheckpointStore(
            base_dir=tmp_path / "checkpoints"
        ),
        default_mcp_server="search",
        sandbox=sandbox,
    )


def _poll(
    client: TestClient,
    task_id: str,
    *,
    timeout: float = 8.0,
    poll_interval: float = 0.02,
) -> Dict[str, Any]:
    """Poll the session endpoint until terminal or 403."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/agent/sessions/{task_id}")
        if resp.status_code == 403:
            return {"_status_code": 403, **resp.json()}
        if resp.status_code == 404:
            return {"_status_code": 404, **resp.json()}
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in ("done", "done_graded", "error"):
            return body
        time.sleep(poll_interval)
    raise AssertionError(
        f"Timed out waiting for task {task_id} to terminate"
    )


def _hash_final_state(state_dict: Dict[str, Any]) -> str:
    """Stable hash of the load-bearing slice of the final state.

    The full GraphState dict carries timestamps and per-turn iteration
    counts that are NOT the same across two independent runs (one of
    them is a replay). We canonicalise to the slice the acceptance
    criterion is asserting on: terminal state, final answer, and
    step-result payloads.
    """

    canonical = {
        "current_state": state_dict["current_state"],
        "final_answer": state_dict.get("final_answer"),
        "step_results": state_dict.get("step_results"),
    }
    payload = json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_router_state():
    agent_router.set_default_loop(None)
    agent_router.clear_runtime_state()
    yield
    agent_router.set_default_loop(None)
    agent_router.clear_runtime_state()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(agent_router.router)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# THE ACCEPTANCE TEST
# ---------------------------------------------------------------------------


def test_phase_1_3_acceptance_multi_step_with_checkpoint_replay_and_permission_gate(
    client, tmp_path,
):
    """Phase 1.3 acceptance: multi-step run, replay, permission gate.

    This is the canonical end-to-end test that proves the FastAPI agent
    surface satisfies the implementation plan's Phase 1.3 criteria. It
    is intentionally one comprehensive test rather than a sweep of
    micro-tests because the criteria themselves are interlocked.
    """

    # -------------------------------------------------------------------
    # (1) Original run: 4 steps drive to DONE.
    # -------------------------------------------------------------------

    loop = _build_loop(tmp_path)
    agent_router.set_default_loop(loop)

    task = (
        "draft a one-pager, fact-check the claims, output a structured "
        "report"
    )
    run_resp = client.post("/api/agent/run", json={"task": task})
    assert run_resp.status_code == 200, run_resp.text
    run_body = run_resp.json()
    original_task_id = run_body["task_id"]
    assert run_body["status"] == "running"

    final = _poll(client, original_task_id)
    assert final["status"] == "done", (
        f"expected DONE, got {final['status']}: {final}"
    )

    final_state = final["state"]
    assert (
        final_state["current_state"] == AgentState.DONE.value
    ), "loop must reach DONE"

    # The final answer is the synthesise step's output by convention.
    assert final_state["final_answer"] == _FINAL_REPORT, (
        f"final answer mismatch: {final_state['final_answer']!r}"
    )

    # Every step succeeded.
    plan = final_state["plan"]
    assert len(plan) == 4
    statuses = [step["status"] for step in plan]
    assert statuses == ["SUCCEEDED"] * 4, statuses
    # The step_results map carries the per-step outputs.
    step_results = final_state["step_results"]
    assert step_results["draft"] == _DRAFT_TEXT
    # FakeMCPClient returns a raw dict; the loop's coercion passes
    # dict / list / scalar results through unchanged. The fact-check
    # payload carries the verified claims.
    assert step_results["fact_check"] == _FACT_CHECK_PAYLOAD
    # Sandbox output is the ExecutionResult.to_dict() shape.
    assert "stdout" in step_results["format"]
    assert step_results["format"]["exit_code"] == 0
    assert step_results["synthesize"] == _FINAL_REPORT

    # The MCP server saw the fact_check call against the right name.
    mcp_calls = loop._mcp.call_log
    assert any(c["name"] == "search.fact_check" for c in mcp_calls)

    # The sandbox saw one Python execution.
    assert len(loop._sandbox.call_log) == 1
    assert loop._sandbox.call_log[0]["language"] == "python"

    # -------------------------------------------------------------------
    # (2) Checkpoint count: at least one per state transition for the plan steps.
    # -------------------------------------------------------------------

    checkpoints = final["checkpoints"]
    assert len(checkpoints) >= 4, (
        f"expected >= 4 checkpoints (one per state transition for the "
        f"plan steps), got {len(checkpoints)}: {checkpoints}"
    )
    # Sanity: the checkpoint indices are 0..N-1.
    assert checkpoints == list(range(len(checkpoints)))

    # -------------------------------------------------------------------
    # (3) Replay from checkpoint 2 reproduces the same final state hash.
    # -------------------------------------------------------------------

    # Build a fresh loop with the SAME canned responses so the replay
    # is deterministic. We pass num_plan_calls=2 so the planner can be
    # invoked again — the replay from a mid-run checkpoint resumes from
    # PLAN or EXECUTE depending on where checkpoint 2 falls.
    replay_loop = _build_loop(
        tmp_path,
        num_plan_calls=2,
        extra_draft_responses=[_DRAFT_TEXT],
        extra_synth_responses=[_FINAL_REPORT],
    )
    # Re-use the same checkpoint base directory so the replay can find
    # the original task's stream.
    replay_loop._checkpoints = loop.checkpoint_store
    agent_router.set_default_loop(replay_loop)

    replay_resp = client.post(
        f"/api/agent/sessions/{original_task_id}/replay",
        json={"from_checkpoint": 2},
    )
    assert replay_resp.status_code == 200
    replay_body = replay_resp.json()
    new_task_id = replay_body["task_id"]
    assert new_task_id != original_task_id

    replay_final = _poll(client, new_task_id)
    assert replay_final["status"] == "done", (
        f"replay did not reach DONE: {replay_final}"
    )
    replay_state = replay_final["state"]

    original_hash = _hash_final_state(final_state)
    replay_hash = _hash_final_state(replay_state)
    assert original_hash == replay_hash, (
        f"replay final state hash differs from original.\n"
        f"  original={original_hash}\n"
        f"  replay  ={replay_hash}\n"
        f"  original.final_answer={final_state['final_answer']!r}\n"
        f"  replay.final_answer  ={replay_state['final_answer']!r}\n"
    )

    # -------------------------------------------------------------------
    # (4) Permission gate violation: HTTP 403 with structured error body.
    # -------------------------------------------------------------------

    # Fresh tmp_path so the denied run's checkpoints don't collide with
    # the previous loops' streams.
    denied_dir = tmp_path / "denied"
    denied_dir.mkdir()

    deny_registry = PermissionRegistry()
    # Explicit deny for search.fact_check; allow everything else.
    deny_registry.register(
        "search.fact_check",
        lambda _ctx: PermissionResult.deny(
            "policy: search.fact_check is denied for the acceptance scenario"
        ),
    )
    deny_registry.register(
        "*", lambda _ctx: PermissionResult.allow("acceptance default"),
    )

    denied_loop = _build_loop(
        denied_dir,
        num_plan_calls=5,  # plenty for the loop to keep replanning into the same denial
        permission_registry=deny_registry,
        extra_draft_responses=[_DRAFT_TEXT] * 4,
        extra_synth_responses=[_FINAL_REPORT] * 4,
    )
    agent_router.set_default_loop(denied_loop)

    denied_run_resp = client.post("/api/agent/run", json={"task": task})
    assert denied_run_resp.status_code == 200
    denied_task_id = denied_run_resp.json()["task_id"]

    # Poll until the loop terminates and the endpoint returns 403.
    deadline = time.monotonic() + 8.0
    final_403_body: Dict[str, Any] = {}
    saw_403 = False
    while time.monotonic() < deadline:
        resp = client.get(f"/api/agent/sessions/{denied_task_id}")
        if resp.status_code == 403:
            final_403_body = resp.json()
            saw_403 = True
            break
        time.sleep(0.02)
    assert saw_403, (
        f"expected 403 from permission-gate violation; never saw one "
        f"within timeout."
    )
    detail = final_403_body["detail"]
    assert detail["error"] == "permission_denied"
    assert detail["tool"] == "search.fact_check"
    assert "denied for the acceptance scenario" in detail["reason"]
    assert detail["task_id"] == denied_task_id
