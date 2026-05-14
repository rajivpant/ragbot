"""Tests for the ``ragbot agent`` CLI subgroup (Phase 4 Agent C).

The CLI exposes three commands for inspecting and replaying durable
agent-loop sessions:

  * ``ragbot agent replay <task_id>`` — reload a checkpoint, re-drive
    the loop, print the final state plus a stable hash; optional
    determinism check against an existing checkpoint.
  * ``ragbot agent list-sessions`` — recent task ids in mtime order.
  * ``ragbot agent checkpoints <task_id>`` — one-line summary per
    checkpoint index.

Tests run the CLI by importing ``src/ragbot.py`` as a script-loaded
module (the package ``src/ragbot/`` shadows the script's name on a
normal import) and dispatching via ``sys.argv``. The checkpoint store
points at a tmp directory via ``SYNTHESIS_AGENT_CHECKPOINT_DIR`` and
the LLM backend is stubbed so the CLI is hermetic.

The final test invokes the eval runner end-to-end on the regression
cases to verify that the harness picks up ``tests/evals/regressions/``
and the determinism case passes.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Make ``src/`` importable, mirroring the other test modules.
_REPO_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
)
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)


from synthesis_engine.agent import (  # noqa: E402
    ActionType,
    AgentState,
    ContextBlock,
    FilesystemCheckpointStore,
    GraphState,
    PlanStep,
    StepStatus,
)


# ---------------------------------------------------------------------------
# Fake LLM backend used by the replay CLI
# ---------------------------------------------------------------------------


@dataclass
class _FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class _FakeLLMBackend:
    """Pre-canned-response LLM backend keyed by the user-text marker.

    The replay CLI re-drives the loop, so the planner / replanner may
    be re-invoked depending on which checkpoint we resume from. The
    fake recognises a small set of markers (PLAN, REPLAN) so a single
    backend instance can serve every CLI invocation in a test.
    """

    backend_name = "fake"

    def __init__(self, *, plan_json: str, replan_json: Optional[str] = None) -> None:
        self._plan_json = plan_json
        self._replan_json = replan_json or plan_json
        self.calls: List[Any] = []

    def complete(self, request: Any) -> _FakeLLMResponse:
        self.calls.append(request)
        text = self._extract_user_text(request)
        if "Replan" in text or "REPLAN" in text or "previous plan" in text.lower():
            return _FakeLLMResponse(text=self._replan_json)
        return _FakeLLMResponse(text=self._plan_json)

    def healthcheck(self) -> Dict[str, Any]:
        return {"backend": self.backend_name, "ok": True}

    @staticmethod
    def _extract_user_text(request: Any) -> str:
        msgs = (
            getattr(request, "messages", None)
            if not isinstance(request, dict)
            else request.get("messages")
        )
        if not msgs:
            return ""
        out = []
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "user":
                out.append(str(m.get("content", "")))
        return "\n".join(out)


def _plan_json_for_summarise() -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "step_id": "s1",
                    "action_type": "LLM_CALL",
                    "target": "summarise",
                    "inputs": {"prompt": "say hello"},
                    "description": "Produce a one-line greeting.",
                }
            ]
        }
    )


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_module():
    """Import ``src/ragbot.py`` as a unique module name.

    Mirrors the pattern in tests/test_skills_cli.py — the package
    ``src/ragbot/`` shadows the script's name on a normal ``import
    ragbot``. We load the script by file path under a private module
    name and cache the result on the fixture function.
    """
    script_path = os.path.join(_REPO_SRC, "ragbot.py")
    spec = importlib.util.spec_from_file_location(
        "ragbot_cli_script_for_agent_replay", script_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["ragbot_cli_script_for_agent_replay"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checkpoint_root(tmp_path, monkeypatch) -> Path:
    """Tmp checkpoint directory exposed via SYNTHESIS_AGENT_CHECKPOINT_DIR."""
    root = tmp_path / "agent-checkpoints"
    root.mkdir()
    monkeypatch.setenv("SYNTHESIS_AGENT_CHECKPOINT_DIR", str(root))
    return root


@pytest.fixture
def fake_backend(monkeypatch) -> _FakeLLMBackend:
    """Install a fake LLM backend that the CLI's get_llm_backend() returns."""
    backend = _FakeLLMBackend(plan_json=_plan_json_for_summarise())
    from synthesis_engine import llm as llm_module

    monkeypatch.setattr(
        llm_module, "get_llm_backend", lambda refresh=False: backend,
    )
    return backend


def _run_cli(cli_module, argv: List[str], monkeypatch) -> int:
    """Invoke ragbot.main with the supplied argv. Returns the exit code."""
    monkeypatch.setattr(sys, "argv", ["ragbot"] + argv)
    return cli_module.main() or 0


def _seed_completed_task(checkpoint_root: Path, task_id: str) -> None:
    """Write a small synthetic checkpoint stream so the CLI has data.

    Three checkpoints land on disk: post-INIT, mid-EXECUTE, terminal-DONE.
    The shape mirrors what a real ``AgentLoop.run()`` produces but is
    written directly to disk so tests don't need to drive the loop end-
    to-end just to set up state for the CLI.
    """
    store = FilesystemCheckpointStore(base_dir=checkpoint_root)
    state = GraphState(
        task_id=task_id,
        original_task="cli replay fixture task",
        current_state=AgentState.PLAN,
        max_iterations=10,
    )
    state.add_turn(AgentState.PLAN, "INIT done; 0 context block(s) retrieved.")
    asyncio.run(store.save(state))

    state.plan = [
        PlanStep(
            step_id="s1",
            action_type=ActionType.LLM_CALL,
            target="summarise",
            inputs={"prompt": "say hello"},
            description="Produce a one-line greeting.",
            status=StepStatus.SUCCEEDED,
            output="hello, world",
        )
    ]
    state.step_results = {"s1": "hello, world"}
    state.current_state = AgentState.EVALUATE
    state.iteration_count = 1
    state.add_turn(AgentState.EVALUATE, "EXECUTE step s1 succeeded")
    asyncio.run(store.save(state))

    state.current_state = AgentState.DONE
    state.iteration_count = 2
    state.final_answer = "hello, world"
    state.add_turn(AgentState.DONE, "EVALUATE: all steps complete.")
    asyncio.run(store.save(state))


def _seed_divergent_checkpoint(checkpoint_root: Path, task_id: str) -> None:
    """Seed a checkpoint stream whose middle checkpoint M differs from the
    replay's natural state at M.

    The strategy: write checkpoint 1 with a deliberately wrong
    final_answer / step_results so the replay (which re-drives PLAN/
    EXECUTE/EVALUATE with the fake backend) produces a different
    state. The CLI's ``--against-checkpoint`` comparison should then
    report DIVERGENT.
    """
    store = FilesystemCheckpointStore(base_dir=checkpoint_root)
    state = GraphState(
        task_id=task_id,
        original_task="divergent replay fixture",
        current_state=AgentState.PLAN,
        max_iterations=10,
    )
    state.add_turn(AgentState.PLAN, "INIT done.")
    asyncio.run(store.save(state))

    # Checkpoint 1: a "stale" state whose step_results differ from
    # what the replay will produce.
    state.plan = [
        PlanStep(
            step_id="s1",
            action_type=ActionType.LLM_CALL,
            target="summarise",
            inputs={"prompt": "say hello"},
            status=StepStatus.SUCCEEDED,
            output="STALE answer",
        )
    ]
    state.step_results = {"s1": "STALE answer"}
    state.current_state = AgentState.DONE
    state.final_answer = "STALE answer"
    state.iteration_count = 2
    state.add_turn(AgentState.DONE, "stale terminal")
    asyncio.run(store.save(state))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_replay_returns_final_state_and_hash(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """``ragbot agent replay <task_id>`` prints the final state and hash."""
    _seed_completed_task(checkpoint_root, "task-replay-basic")

    rc = _run_cli(cli_module, ["agent", "replay", "task-replay-basic"], monkeypatch)
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "task-replay-basic" in out
    assert "State hash:" in out
    # The hash is sha256 hex — 64 lowercase hex chars.
    hash_match = re.search(r"State hash:\s+([0-9a-f]{64})", out)
    assert hash_match, f"expected sha256 hash in output: {out}"


def test_replay_from_checkpoint_loads_specific_index(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """``--from-checkpoint N`` resumes from the given checkpoint."""
    _seed_completed_task(checkpoint_root, "task-replay-from-cp")

    rc = _run_cli(
        cli_module,
        ["agent", "replay", "task-replay-from-cp", "--from-checkpoint", "1"],
        monkeypatch,
    )
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "Replayed from:    checkpoint 1" in out


def test_replay_against_checkpoint_reports_divergent(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """A divergent checkpoint M surfaces ``DIVERGENT`` and the divergent fields."""
    _seed_divergent_checkpoint(checkpoint_root, "task-divergent")

    rc = _run_cli(
        cli_module,
        [
            "agent", "replay", "task-divergent",
            "--from-checkpoint", "0",
            "--against-checkpoint", "1",
        ],
        monkeypatch,
    )
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "Determinism:      DIVERGENT" in out
    assert "Divergent fields:" in out


def test_replay_against_checkpoint_reports_identical(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """An unchanged checkpoint M surfaces ``IDENTICAL``."""
    _seed_completed_task(checkpoint_root, "task-identical")

    rc = _run_cli(
        cli_module,
        [
            "agent", "replay", "task-identical",
            "--from-checkpoint", "2",  # already-terminal checkpoint
            "--against-checkpoint", "2",
        ],
        monkeypatch,
    )
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "Determinism:      IDENTICAL" in out
    assert "DIVERGENT" not in out


def test_replay_show_trace_includes_turn_history(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """``--show-trace`` prints the post-replay turn_history."""
    _seed_completed_task(checkpoint_root, "task-show-trace")

    rc = _run_cli(
        cli_module,
        ["agent", "replay", "task-show-trace", "--show-trace"],
        monkeypatch,
    )
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "Turn history:" in out
    # The seeded state's first turn record summary is in turn_history.
    assert "INIT done" in out or "context block(s)" in out


def test_replay_save_output_writes_json(
    cli_module, checkpoint_root, fake_backend, tmp_path, capsys, monkeypatch,
):
    """``--save-output PATH`` writes the full final-state JSON to PATH."""
    _seed_completed_task(checkpoint_root, "task-save-output")
    out_path = tmp_path / "final_state.json"

    rc = _run_cli(
        cli_module,
        [
            "agent", "replay", "task-save-output",
            "--save-output", str(out_path),
        ],
        monkeypatch,
    )
    capsys.readouterr()

    assert rc == 0
    assert out_path.exists()
    payload = json.loads(out_path.read_text("utf-8"))
    assert payload["task_id"] == "task-save-output"
    assert payload["current_state"] in {
        AgentState.DONE.value, AgentState.DONE_GRADED.value,
    }


def test_list_sessions_returns_recent_task_ids(
    cli_module, checkpoint_root, capsys, monkeypatch,
):
    """``agent list-sessions`` lists task ids most-recent first."""
    # Seed three tasks with controlled mtimes.
    _seed_completed_task(checkpoint_root, "task-oldest")
    time.sleep(0.01)
    _seed_completed_task(checkpoint_root, "task-middle")
    time.sleep(0.01)
    _seed_completed_task(checkpoint_root, "task-newest")

    rc = _run_cli(cli_module, ["agent", "list-sessions"], monkeypatch)
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    for tid in ("task-oldest", "task-middle", "task-newest"):
        assert tid in out, f"missing task id {tid} in output"
    # Most-recent first ordering.
    idx_newest = out.index("task-newest")
    idx_oldest = out.index("task-oldest")
    assert idx_newest < idx_oldest


def test_checkpoints_lists_indices_with_summaries(
    cli_module, checkpoint_root, capsys, monkeypatch,
):
    """``agent checkpoints <task_id>`` prints idx, state, iter, plan-count, summary."""
    _seed_completed_task(checkpoint_root, "task-checkpoints-list")

    rc = _run_cli(
        cli_module,
        ["agent", "checkpoints", "task-checkpoints-list"], monkeypatch,
    )
    out = capsys.readouterr().out

    assert rc == 0, f"exit code {rc}; output: {out}"
    assert "task-checkpoints-list" in out
    assert "Checkpoints: 3" in out
    # Header row.
    assert "STATE" in out and "PLAN" in out
    # Three checkpoint rows are visible (idx 0, 1, 2 — the seeded stream).
    for idx in ("   0", "   1", "   2"):
        assert idx in out, f"missing index row {idx!r} in output"


def test_replay_missing_task_id_returns_clear_error(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """``replay`` of an unknown task id returns a clear error and exit 1."""
    rc = _run_cli(
        cli_module,
        ["agent", "replay", "no-such-task-id"], monkeypatch,
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert "no checkpoints found" in captured.err.lower() \
        or "no checkpoints found" in captured.out.lower()
    assert "no-such-task-id" in (captured.err + captured.out)


def test_list_sessions_empty_store(
    cli_module, checkpoint_root, capsys, monkeypatch,
):
    """``list-sessions`` on an empty store prints a clear no-op message."""
    rc = _run_cli(cli_module, ["agent", "list-sessions"], monkeypatch)
    out = capsys.readouterr().out

    assert rc == 0
    assert "No agent sessions" in out


def test_eval_runner_loads_regression_cases():
    """The eval runner discovers cases under tests/evals/regressions/."""
    from tests.evals.runner import load_cases

    cases = load_cases()
    regression_cases = [c for c in cases if c.is_regression]
    assert len(regression_cases) >= 5
    ids = {c.id for c in regression_cases}
    assert "regression_replay_reproduces_final_state_hash" in ids
    assert "regression_subagent_dispatch_max_parallel_violation" in ids
    assert "regression_sandbox_disabled_actionable_error" in ids
    assert "regression_permission_deny_blocks_tool_call" in ids
    assert "regression_cross_workspace_air_gapped_isolation" in ids


def test_replay_determinism_regression_case_passes_end_to_end():
    """The replay-determinism regression case passes against its inline_response."""
    from tests.evals.runner import load_cases, run_case

    cases = load_cases(filter_substring="replay_reproduces_final_state_hash")
    assert len(cases) == 1
    result = run_case(cases[0])
    assert result.passed, f"determinism regression case failed: {result.detail}"
    assert result.score == 1.0
    assert result.is_regression


def test_replay_against_checkpoint_invalid_index_errors(
    cli_module, checkpoint_root, fake_backend, capsys, monkeypatch,
):
    """``--against-checkpoint`` with an out-of-range index returns a clear error."""
    _seed_completed_task(checkpoint_root, "task-invalid-against")

    rc = _run_cli(
        cli_module,
        [
            "agent", "replay", "task-invalid-against",
            "--against-checkpoint", "999",
        ],
        monkeypatch,
    )
    captured = capsys.readouterr()

    assert rc == 1
    err_blob = (captured.err + captured.out).lower()
    assert "not found" in err_blob or "does not exist" in err_blob


def test_checkpoints_missing_task_id_returns_clear_error(
    cli_module, checkpoint_root, capsys, monkeypatch,
):
    """``checkpoints <task_id>`` on an unknown task id surfaces a clear error."""
    rc = _run_cli(
        cli_module,
        ["agent", "checkpoints", "no-such-task"], monkeypatch,
    )
    captured = capsys.readouterr()

    assert rc == 1
    err_blob = (captured.err + captured.out).lower()
    assert "no checkpoints found" in err_blob
