"""Tests for the FastAPI agent-loop router.

Round 4c of Phase 1 exposes the agent loop through HTTP. The router is
defined in ``src/api/routers/agent.py``; this module exercises it end-to-
end with the FastAPI TestClient and the same Fake substrates the
``test_agent_loop`` / ``test_agent_capabilities`` modules use, so no real
LLM or external service calls happen.

Coverage:

  1. POST /run returns 200 with a task_id and status=running.
  2. GET /sessions/{task_id} surfaces the GraphState once the background
     loop reaches DONE.
  3. GET /sessions/<missing> returns 404.
  4. POST /sessions/{task_id}/replay returns a new task id.
  5. GET /sessions/{new_task_id}/checkpoints/{n} returns the Nth
     checkpoint of the replayed task.
  6. Permission denied surfaces as HTTP 403 with the structured body.
  7. Replay reproduces the original final state (deterministic fakes).
  8. The API state shape is identical to GraphState.to_dict().
  9. Two concurrent POST /run requests both complete with distinct ids.
 10. max_iterations cap honored — task transitions to ERROR.
 11. Rubric path drives to DONE_GRADED.
 12. No-rubric path stops at DONE.

The fixture pattern installs a fresh process-singleton AgentLoop with
FakeLLMBackend (pre-canned plan + step outputs) and FakeMCPClient. Each
test uses ``tmp_path`` for the checkpoint store so tests are hermetic.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
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

from fastapi.testclient import TestClient  # noqa: E402

from synthesis_engine.agent import (  # noqa: E402
    AgentLoop,
    AgentState,
    FilesystemCheckpointStore,
    PermissionRegistry,
    PermissionResult,
    SelfGrader,
)

# Router module — imported after sys.path is set up.
from api.routers import agent as agent_router  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes (mirrored from test_agent_loop / test_agent_capabilities)
# ---------------------------------------------------------------------------


@dataclass
class FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class FakeLLMBackend:
    """LLM backend that returns pre-canned responses.

    Two scripting modes: ``scripted`` is a flat queue; ``by_marker`` is a
    per-marker queue keyed by a substring of the user message so PLAN /
    GRADE prompts can return distinct responses without relying on call
    order.
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
        for marker, responses in self._by_marker.items():
            if marker in user_text and responses:
                return FakeLLMResponse(
                    text=responses.pop(0), model=_request_model(request),
                )
        if self._scripted:
            return FakeLLMResponse(
                text=self._scripted.pop(0), model=_request_model(request),
            )
        raise AssertionError(
            f"FakeLLMBackend: no scripted response for request "
            f"(user_text={user_text[:120]!r})"
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
    """In-memory MCP-like client with canned per-tool responses."""

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


# ---------------------------------------------------------------------------
# Canned plan JSON
# ---------------------------------------------------------------------------


def _trivial_plan_json(target: str = "summarise") -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "s1",
                    "action_type": "TOOL_CALL",
                    "target": target,
                    "inputs": {"text": "hello"},
                    "description": f"Call {target}.",
                }
            ]
        }
    )


def _five_step_plan_json() -> str:
    """Plan that needs ~10 transitions; used to test max_iterations cap."""
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": f"s{i}",
                    "action_type": "TOOL_CALL",
                    "target": "summarise",
                    "inputs": {"i": i},
                    "description": f"step {i}",
                }
                for i in range(5)
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


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _install_loop(
    *,
    tmp_path,
    llm_responses: Optional[List[str]] = None,
    by_marker: Optional[Dict[str, List[str]]] = None,
    mcp_tools: Optional[List[str]] = None,
    mcp_responses: Optional[Dict[str, Callable[[Dict[str, Any]], Any]]] = None,
    permission_registry: Optional[PermissionRegistry] = None,
    max_iterations: int = 30,
    grader: Optional[SelfGrader] = None,
    llm_backend: Optional[FakeLLMBackend] = None,
) -> AgentLoop:
    """Build an AgentLoop wired to Fake substrates and install it on the router.

    Returns the loop so individual tests can reach in for assertions
    against the fakes (e.g., ``loop._mcp.call_log``).
    """

    if llm_backend is None:
        llm_backend = FakeLLMBackend(
            scripted=llm_responses, by_marker=by_marker,
        )
    mcp = FakeMCPClient(
        tools=mcp_tools or ["summarise"], responses=mcp_responses or {},
    )

    registry = permission_registry
    if registry is None:
        registry = PermissionRegistry()
        registry.register(
            "*", lambda _ctx: PermissionResult.allow("test-permissive"),
        )

    loop = AgentLoop(
        llm_backend=llm_backend,
        mcp_client=mcp,
        permission_registry=registry,
        checkpoint_store=FilesystemCheckpointStore(
            base_dir=tmp_path / "checkpoints"
        ),
        default_mcp_server="local",
        max_iterations=max_iterations,
        grader=grader,
    )
    agent_router.set_default_loop(loop)
    return loop


def _poll_until_terminal(
    client: TestClient,
    task_id: str,
    *,
    timeout: float = 5.0,
    poll_interval: float = 0.02,
    expected_status_codes: tuple = (200,),
) -> Dict[str, Any]:
    """Poll GET /sessions/{task_id} until the status is terminal.

    Returns the final response body. Raises if the timeout elapses
    before the loop reaches a terminal state.
    """

    deadline = time.monotonic() + timeout
    last_body: Dict[str, Any] = {}
    last_status = 0
    while time.monotonic() < deadline:
        resp = client.get(f"/api/agent/sessions/{task_id}")
        last_status = resp.status_code
        if resp.status_code in (403, 404):
            return {"_status_code": resp.status_code, **resp.json()}
        assert resp.status_code in expected_status_codes, (
            f"unexpected status {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        last_body = body
        if body["status"] in ("done", "done_graded", "error"):
            return body
        time.sleep(poll_interval)
    raise AssertionError(
        f"Timed out waiting for task {task_id} to terminate; "
        f"last_status={last_status}, last_body={last_body}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_router_state():
    """Ensure each test starts with a clean process-singleton AgentLoop."""

    agent_router.set_default_loop(None)
    agent_router.clear_runtime_state()
    yield
    agent_router.set_default_loop(None)
    agent_router.clear_runtime_state()


@pytest.fixture
def client():
    """FastAPI TestClient bound to the agent router.

    The router is mounted on a tiny FastAPI app per test rather than the
    full ``api.main`` app so test isolation is clean and unrelated
    routers cannot pollute discovery (e.g., the mcp router building a
    real ``~/.synthesis/mcp.yaml`` client).
    """

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(agent_router.router)
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_post_run_returns_task_id_and_running_status(client, tmp_path):
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "ok"}},
    )

    response = client.post(
        "/api/agent/run", json={"task": "summarise something"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "task_id" in body and body["task_id"]
    assert body["status"] == "running"


def test_get_session_returns_state_after_done(client, tmp_path):
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "deterministic"}},
    )

    response = client.post(
        "/api/agent/run", json={"task": "summarise it"},
    )
    task_id = response.json()["task_id"]
    final = _poll_until_terminal(client, task_id)

    assert final["status"] == "done"
    assert final["state"]["current_state"] == AgentState.DONE.value
    assert "deterministic" in (final["state"]["final_answer"] or "")
    # The endpoint also surfaces the checkpoint index list.
    assert isinstance(final["checkpoints"], list)
    assert len(final["checkpoints"]) >= 3


def test_get_session_missing_returns_404(client, tmp_path):
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "ok"}},
    )

    response = client.get("/api/agent/sessions/this-task-id-does-not-exist")
    assert response.status_code == 404


def test_replay_creates_new_task_id(client, tmp_path):
    loop = _install_loop(
        tmp_path=tmp_path,
        # Original plan plus a second copy for the replayed run, since
        # the replay restarts from checkpoint 1 (post-INIT) which means
        # it still needs to ask the planner for a plan.
        llm_responses=[_trivial_plan_json(), _trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "stable answer"}},
    )

    run_resp = client.post(
        "/api/agent/run", json={"task": "replayable task"},
    )
    original_id = run_resp.json()["task_id"]
    final_original = _poll_until_terminal(client, original_id)
    assert final_original["status"] == "done"

    # Replay from the first checkpoint of the original run.
    replay_resp = client.post(
        f"/api/agent/sessions/{original_id}/replay",
        json={"from_checkpoint": 1},
    )
    assert replay_resp.status_code == 200
    replay_body = replay_resp.json()
    new_id = replay_body["task_id"]
    assert new_id and new_id != original_id
    assert replay_body["status"] == "running"

    final_replay = _poll_until_terminal(client, new_id)
    assert final_replay["status"] == "done"
    # Loop reference quiets the unused-warning while making the
    # MCP-call assertion explicit: both runs invoked summarise.
    summarise_calls = [c for c in loop._mcp.call_log if c["name"] == "summarise"]
    assert len(summarise_calls) >= 2


def test_get_specific_checkpoint(client, tmp_path):
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "ok"}},
    )

    run_resp = client.post(
        "/api/agent/run", json={"task": "checkpoint test"},
    )
    task_id = run_resp.json()["task_id"]
    final = _poll_until_terminal(client, task_id)
    assert final["status"] == "done"

    # Read the first checkpoint (post-INIT seed).
    ckpt_resp = client.get(
        f"/api/agent/sessions/{task_id}/checkpoints/0",
    )
    assert ckpt_resp.status_code == 200
    body = ckpt_resp.json()
    assert body["task_id"] == task_id
    assert body["checkpoint"] == 0
    assert body["state"]["task_id"] == task_id

    # 404 on an out-of-range checkpoint.
    miss = client.get(
        f"/api/agent/sessions/{task_id}/checkpoints/999",
    )
    assert miss.status_code == 404


def test_permission_denied_returns_403_with_structured_body(client, tmp_path):
    """A plan that calls a denied tool surfaces 403 with the structured error."""

    registry = PermissionRegistry()
    registry.register(
        "dangerous_tool",
        lambda _ctx: PermissionResult.deny("policy: explicit deny for test"),
    )

    plan = _trivial_plan_json(target="dangerous_tool")
    # Provide enough plan responses so all three replan attempts also
    # hit the denied tool; the loop then transitions to ERROR after
    # exhausting the replan budget.
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[plan, plan, plan, plan, plan],
        mcp_tools=["dangerous_tool"],
        mcp_responses={"dangerous_tool": lambda args: {"text": "boom"}},
        permission_registry=registry,
    )

    run_resp = client.post(
        "/api/agent/run", json={"task": "do dangerous thing"},
    )
    task_id = run_resp.json()["task_id"]

    # Poll: when the loop terminates with a permission-denied chain the
    # GET endpoint returns 403 directly.
    deadline = time.monotonic() + 5.0
    final_status = None
    final_body: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        resp = client.get(f"/api/agent/sessions/{task_id}")
        if resp.status_code == 403:
            final_status = 403
            final_body = resp.json()
            break
        # Otherwise it's still 200/running — keep waiting.
        time.sleep(0.02)
    assert final_status == 403, (
        f"expected eventual 403 from permission-denied chain, "
        f"got body={final_body}"
    )
    detail = final_body["detail"]
    assert detail["error"] == "permission_denied"
    assert detail["tool"] == "dangerous_tool"
    assert "policy" in detail["reason"]
    assert detail["task_id"] == task_id


def test_replay_reproduces_final_state_with_deterministic_fakes(
    client, tmp_path,
):
    """Replay from a mid-run checkpoint reproduces the original final state."""

    # The deterministic LLM script supplies the same plan to both the
    # original run and the replay.
    deterministic_plan = _trivial_plan_json()
    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[deterministic_plan, deterministic_plan],
        mcp_responses={
            "summarise": lambda args: {"text": "stable-deterministic"},
        },
    )

    original = client.post(
        "/api/agent/run", json={"task": "deterministic replay"},
    )
    original_id = original.json()["task_id"]
    final_original = _poll_until_terminal(client, original_id)
    original_state = final_original["state"]

    # Pick a mid-run checkpoint. We use index 1 (post-INIT) — the
    # replay re-runs PLAN/EXECUTE/EVALUATE from that point.
    replay_resp = client.post(
        f"/api/agent/sessions/{original_id}/replay",
        json={"from_checkpoint": 1},
    )
    new_id = replay_resp.json()["task_id"]
    final_replay = _poll_until_terminal(client, new_id)
    replay_state = final_replay["state"]

    # The final answers must match — deterministic fakes guarantee it.
    assert replay_state["final_answer"] == original_state["final_answer"]
    # Step outputs match.
    assert replay_state["step_results"] == original_state["step_results"]
    # Terminal state matches.
    assert replay_state["current_state"] == original_state["current_state"]


def test_api_state_shape_matches_graphstate_to_dict(client, tmp_path):
    """The 'state' field in GET /sessions is bit-identical to GraphState.to_dict()."""

    loop = _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "ok"}},
    )

    run_resp = client.post(
        "/api/agent/run", json={"task": "shape test"},
    )
    task_id = run_resp.json()["task_id"]
    final = _poll_until_terminal(client, task_id)
    api_state = final["state"]

    # Pull the same state from the underlying store and compare.
    raw_state = asyncio.get_event_loop().run_until_complete(
        loop.checkpoint_store.load(task_id, final["checkpoints"][-1])
    )
    direct = raw_state.to_dict()

    # The JSON round-trip through the API canonicalises some values
    # (e.g., floats), so we compare by JSON equality, not Python ==.
    assert json.loads(json.dumps(api_state)) == json.loads(
        json.dumps(direct)
    )


def test_concurrent_post_run_produces_distinct_task_ids(client, tmp_path):
    """Two POST /run requests in quick succession both complete distinctly."""

    # The LLM returns two trivial plans; the MCP responder serves both
    # task strings without sharing state.
    plan = _trivial_plan_json()
    _install_loop(
        tmp_path=tmp_path,
        # Two PLAN calls, one per task.
        llm_responses=[plan, plan],
        mcp_responses={"summarise": lambda args: {"text": f"answer for {args}"}},
    )

    r1 = client.post(
        "/api/agent/run", json={"task": "first concurrent task"},
    )
    r2 = client.post(
        "/api/agent/run", json={"task": "second concurrent task"},
    )
    id1 = r1.json()["task_id"]
    id2 = r2.json()["task_id"]
    assert id1 != id2

    # Both must reach DONE; their task descriptions are preserved.
    final1 = _poll_until_terminal(client, id1)
    final2 = _poll_until_terminal(client, id2)
    assert final1["status"] == "done"
    assert final2["status"] == "done"
    assert final1["state"]["original_task"] == "first concurrent task"
    assert final2["state"]["original_task"] == "second concurrent task"
    # No cross-contamination of task ids inside the state objects.
    assert final1["state"]["task_id"] == id1
    assert final2["state"]["task_id"] == id2


def test_max_iterations_cap_drives_to_error(client, tmp_path):
    """A plan that cannot finish within max_iterations transitions to ERROR."""

    _install_loop(
        tmp_path=tmp_path,
        # Five-step plan, but max_iterations=2 means the loop runs out.
        llm_responses=[_five_step_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "ok"}},
        max_iterations=2,
    )

    run_resp = client.post(
        "/api/agent/run",
        json={"task": "five-step task", "max_iterations": 2},
    )
    task_id = run_resp.json()["task_id"]
    final = _poll_until_terminal(client, task_id)
    assert final["status"] == "error"
    assert final["state"]["current_state"] == AgentState.ERROR.value
    assert "max_iterations" in (final["state"]["error_message"] or "")


def test_rubric_path_drives_to_done_graded(client, tmp_path):
    """POST /run with a rubric drives the loop through GRADE to DONE_GRADED."""

    plan = _trivial_plan_json()
    # by_marker beats scripted: AGENT_FINAL_ANSWER is the grader prompt
    # marker, AVAILABLE_TOOLS is the planner's marker. The grader
    # returns a high score so the loop transitions to DONE_GRADED.
    backend = FakeLLMBackend(
        by_marker={
            "AGENT_FINAL_ANSWER": [_grader_pass_json(0.95)],
            "AVAILABLE_TOOLS": [plan],
        }
    )
    grader = SelfGrader(llm_backend=backend, max_revision_rounds=2)
    _install_loop(
        tmp_path=tmp_path,
        mcp_responses={"summarise": lambda args: {"text": "great answer"}},
        grader=grader,
        llm_backend=backend,
    )

    run_resp = client.post(
        "/api/agent/run",
        json={
            "task": "graded task",
            "rubric": "answer must mention 'great'",
        },
    )
    task_id = run_resp.json()["task_id"]
    final = _poll_until_terminal(client, task_id, timeout=8.0)
    assert final["status"] == "done_graded"
    assert (
        final["state"]["current_state"] == AgentState.DONE_GRADED.value
    )
    grading = final["state"]["metadata"]["grading"]
    assert grading["passed"] is True


def test_no_rubric_path_stops_at_done(client, tmp_path):
    """Without a rubric the loop stops at DONE (Round 4a behaviour preserved)."""

    _install_loop(
        tmp_path=tmp_path,
        llm_responses=[_trivial_plan_json()],
        mcp_responses={"summarise": lambda args: {"text": "no grade"}},
    )

    run_resp = client.post(
        "/api/agent/run", json={"task": "ungraded task"},
    )
    task_id = run_resp.json()["task_id"]
    final = _poll_until_terminal(client, task_id)
    assert final["status"] == "done"
    assert final["state"]["current_state"] == AgentState.DONE.value
    # GRADE state must NOT appear in the turn history.
    states_visited = [
        t["state"] for t in final["state"]["turn_history"]
    ]
    assert AgentState.GRADE.value not in states_visited
    assert AgentState.DONE_GRADED.value not in states_visited


def test_run_without_installed_loop_returns_503(client, tmp_path):
    """When no AgentLoop is installed the router refuses requests with 503."""

    # No _install_loop() call here; the autouse fixture cleared the
    # singleton, so the router must refuse.
    response = client.post(
        "/api/agent/run", json={"task": "no loop installed"},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
