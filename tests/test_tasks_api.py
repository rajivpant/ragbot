"""Tests for the FastAPI tasks router.

Mounts the tasks router on a tiny FastAPI app per test, exercises each
endpoint end-to-end with the FastAPI TestClient, and uses tmp_path-
backed managers + schedule stores so nothing leaks between tests.

Coverage:

  * GET /api/tasks lists tasks; state filter works; unknown filter 400s.
  * GET /api/tasks/{id} returns 404 for an unknown id.
  * GET /api/tasks/{id} returns the record + transition history.
  * POST /api/tasks/{id}/cancel flips state to cancelled.
  * GET /api/tasks/schedules returns configured schedules.
  * POST /api/tasks/schedules/{id}/enable + /disable flip the flag.
  * Enable / disable on an unknown schedule returns 404.

Placeholder workspace name (``example-workspace``) is used in
schedule args where relevant.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.routers import tasks as tasks_router  # noqa: E402
from synthesis_engine.tasks import (  # noqa: E402
    BackgroundTaskManager,
    TaskState,
)
from synthesis_engine.tasks.manager import TaskCancelled  # noqa: E402
from synthesis_engine.tasks.scheduler import ScheduleStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_router_state():
    tasks_router.clear_runtime_state()
    yield
    tasks_router.clear_runtime_state()


@pytest.fixture
def app_client(tmp_path):
    """Mount the router on a fresh FastAPI app per test."""
    manager = BackgroundTaskManager(state_dir=tmp_path / "tasks")
    tasks_router.set_default_manager(manager)
    yaml_path = tmp_path / "schedules.yaml"
    yaml_path.write_text("schedules: []\n")
    tasks_router.set_schedule_store(ScheduleStore(path=yaml_path))
    app = FastAPI()
    app.include_router(tasks_router.router)
    with TestClient(app) as client:
        yield client, manager, yaml_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_schedules(path: Path, entries: List[Dict[str, Any]]) -> None:
    import yaml

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schedules": entries}, f, sort_keys=False)


def _run_task_to_completion(
    manager: BackgroundTaskManager, *, name: str = "example-task",
) -> str:
    async def _body(_record):
        return "ok"

    async def _drive() -> str:
        handle = manager.start_task(name, _body)
        await handle.await_result()
        return handle.task_id

    return asyncio.run(_drive())


# ---------------------------------------------------------------------------
# Tests — tasks endpoints
# ---------------------------------------------------------------------------


def test_list_tasks_returns_empty_initially(app_client):
    client, _manager, _yaml = app_client
    response = client.get("/api/tasks")
    assert response.status_code == 200
    body = response.json()
    assert body == {"tasks": []}


def test_list_tasks_returns_executed_task(app_client):
    client, manager, _yaml = app_client
    task_id = _run_task_to_completion(manager)
    response = client.get("/api/tasks")
    assert response.status_code == 200
    body = response.json()
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["id"] == task_id
    assert body["tasks"][0]["state"] == TaskState.SUCCEEDED


def test_list_tasks_filter_by_state(app_client):
    client, manager, _yaml = app_client

    async def _ok(_record):
        return "ok"

    async def _bad(_record):
        raise RuntimeError("kaboom")

    async def _drive():
        a = manager.start_task("example-ok", _ok)
        b = manager.start_task("example-bad", _bad)
        await a.await_result()
        await b.await_result()
        return a.task_id, b.task_id

    a_id, b_id = asyncio.run(_drive())

    succeeded = client.get("/api/tasks", params={"state": TaskState.SUCCEEDED})
    failed = client.get("/api/tasks", params={"state": TaskState.FAILED})
    assert succeeded.status_code == 200 and len(succeeded.json()["tasks"]) == 1
    assert succeeded.json()["tasks"][0]["id"] == a_id
    assert failed.status_code == 200 and len(failed.json()["tasks"]) == 1
    assert failed.json()["tasks"][0]["id"] == b_id


def test_list_tasks_invalid_state_returns_400(app_client):
    client, _m, _y = app_client
    response = client.get("/api/tasks", params={"state": "no-such-state"})
    assert response.status_code == 400


def test_get_task_unknown_returns_404(app_client):
    client, _m, _y = app_client
    response = client.get("/api/tasks/does-not-exist")
    assert response.status_code == 404


def test_get_task_returns_record_and_history(app_client):
    client, manager, _y = app_client
    task_id = _run_task_to_completion(manager)
    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["record"]["id"] == task_id
    assert body["record"]["state"] == TaskState.SUCCEEDED
    assert len(body["history"]) >= 2
    assert body["history"][0]["event"] == "started"
    assert body["history"][-1]["event"] == TaskState.SUCCEEDED


def test_cancel_endpoint_flips_state_for_cooperating_task(app_client):
    """Cancellation request lands; cooperating task exits in cancelled state."""
    client, manager, _y = app_client

    async def _drive() -> Dict[str, Any]:
        started = asyncio.Event()

        async def _body(record):
            started.set()
            for _ in range(200):
                await asyncio.sleep(0.005)
                if record.cancellation_requested:
                    raise TaskCancelled("api requested cancel")
            return "should not see"

        handle = manager.start_task("example-cancel", _body)
        await started.wait()
        # Cancel via the HTTP endpoint, then await the result.
        cancel_resp = client.post(f"/api/tasks/{handle.task_id}/cancel")
        result_record = await handle.await_result()
        return {
            "cancel_resp": cancel_resp.json(),
            "cancel_status_code": cancel_resp.status_code,
            "final_state": result_record.state,
            "task_id": handle.task_id,
        }

    out = asyncio.run(_drive())
    assert out["cancel_status_code"] == 200
    assert out["cancel_resp"]["accepted"] is True
    assert out["final_state"] == TaskState.CANCELLED


def test_cancel_unknown_task_returns_404(app_client):
    client, _m, _y = app_client
    response = client.post("/api/tasks/does-not-exist/cancel")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — schedule endpoints
# ---------------------------------------------------------------------------


def test_list_schedules_returns_entries(app_client):
    client, _m, yaml_path = app_client
    _write_schedules(
        yaml_path,
        [
            {
                "id": "nightly-consolidation",
                "cron": "0 3 * * *",
                "task": "memory.consolidate_recent_idle",
                "args": {
                    "idle_threshold_hours": 4,
                    "workspace": "example-workspace",
                },
                "enabled": True,
            }
        ],
    )
    response = client.get("/api/tasks/schedules")
    assert response.status_code == 200
    body = response.json()
    assert len(body["schedules"]) == 1
    s = body["schedules"][0]
    assert s["id"] == "nightly-consolidation"
    assert s["enabled"] is True
    assert s["args"]["workspace"] == "example-workspace"


def test_enable_schedule_flips_to_true(app_client):
    client, _m, yaml_path = app_client
    _write_schedules(
        yaml_path,
        [
            {
                "id": "example-heartbeat",
                "cron": "*/5 * * * *",
                "task": "tasks.heartbeat",
                "enabled": False,
            }
        ],
    )
    response = client.post("/api/tasks/schedules/example-heartbeat/enable")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "example-heartbeat"
    assert body["enabled"] is True
    schedules = ScheduleStore(path=yaml_path).load()
    assert schedules[0].enabled is True


def test_disable_schedule_flips_to_false(app_client):
    client, _m, yaml_path = app_client
    _write_schedules(
        yaml_path,
        [
            {
                "id": "example-heartbeat",
                "cron": "*/5 * * * *",
                "task": "tasks.heartbeat",
                "enabled": True,
            }
        ],
    )
    response = client.post("/api/tasks/schedules/example-heartbeat/disable")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    schedules = ScheduleStore(path=yaml_path).load()
    assert schedules[0].enabled is False


def test_enable_unknown_schedule_returns_404(app_client):
    client, _m, _yaml = app_client
    response = client.post("/api/tasks/schedules/no-such-schedule/enable")
    assert response.status_code == 404
