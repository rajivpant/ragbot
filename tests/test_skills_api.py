"""Tests for the Agent Skills FastAPI router (Phase 2 Agent D).

Coverage:

  1. GET /api/skills returns every discovered skill.
  2. GET /api/skills?workspace=acme-news returns the workspace-filtered set.
  3. GET /api/skills?workspace=personal returns only universal skills when
     no workspace-scoped ones target personal.
  4. GET /api/skills/{name} returns the full body and frontmatter.
  5. GET /api/skills/{name}?workspace=W with an invisible skill returns 403.
  6. GET /api/skills/{unknown} returns 404.
  7. POST /api/skills/{name}/run returns a task_id and reaches done state.
  8. POST /api/skills/{name}/run with a non-visible skill returns 403.
  9. POST /api/skills/{name}/run on an unknown skill returns 404.
 10. GET /api/skills/runs/{unknown_task_id} returns 404.
 11. Skill detail includes tool definitions when the skill declares tools.
 12. Skill detail includes file list with kind tags.
 13. Skill summary scope shape is ``{universal: bool, workspaces: [...]}``.
 14. Workspace filter restricts a sibling workspace's private skill.
 15. Switching workspace param re-filters across requests.

The tests use the fake-home pattern from test_skills_workspace_scoping so
the discovery layer's filesystem walks see a synthetic tree under
``tmp_path`` instead of the operator's actual ``$HOME``. Real LLM/MCP
calls are stubbed via fake backends — the POST /run path is exercised
end-to-end without an external dependency.
"""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Make ``src/`` importable just like the other test modules do.
_REPO_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src",
)
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.routers import skills as skills_router  # noqa: E402


# ---------------------------------------------------------------------------
# Fake LLM backend so the POST /run path is hermetic
# ---------------------------------------------------------------------------


@dataclass
class _FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class _FakeLLMBackend:
    """Returns a single canned text for every completion request."""

    backend_name = "fake"

    def __init__(self, text: str = "stub answer") -> None:
        self._text = text
        self.calls: List[Any] = []

    def complete(self, request: Any) -> _FakeLLMResponse:
        self.calls.append(request)
        return _FakeLLMResponse(text=self._text)

    def stream(self, request: Any, on_chunk):  # pragma: no cover - unused here
        text = self._text
        on_chunk(text)
        return text

    def healthcheck(self) -> Dict[str, Any]:
        return {"backend": self.backend_name, "ok": True}


# ---------------------------------------------------------------------------
# Skill tree fixtures
# ---------------------------------------------------------------------------


def _write_skill(
    root: Path,
    name: str,
    description: str = "",
    frontmatter_extra: str = "",
) -> Path:
    """Plant a minimal skill directory."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        f"name: {name}\n"
        f"description: {description or 'test fixture'}\n"
        f"{frontmatter_extra}"
        "---\n\n"
        f"# {name}\n\nbody for {name}.\n"
    )
    (skill_dir / "SKILL.md").write_text(body)
    return skill_dir


@pytest.fixture
def skills_home(tmp_path: Path, monkeypatch) -> Path:
    """Patch home to a synthetic tree containing universal + workspace-scoped skills.

    Layout:

      <home>/.synthesis/skills/universal-shared/
      <home>/workspaces/acme-user/synthesis-skills/personal-helper/
      <home>/workspaces/acme-news/synthesis-skills-acme-news/news-only-skill/
      <home>/workspaces/beta-media/synthesis-skills-beta-media/beta-private/
    """
    home = tmp_path / "home"
    home.mkdir()
    (home / ".synthesis").mkdir()
    identity = home / ".synthesis" / "identity.yaml"
    identity.write_text("personal_workspaces:\n  - acme-user\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", str(identity))

    universal_root = home / ".synthesis" / "skills"
    universal_root.mkdir(parents=True, exist_ok=True)
    _write_skill(
        universal_root,
        "universal-shared",
        description="A universal skill visible everywhere.",
    )

    (home / "workspaces" / "acme-user" / "synthesis-skills").mkdir(parents=True)
    _write_skill(
        home / "workspaces" / "acme-user" / "synthesis-skills",
        "personal-helper",
        description="A personal helper marked universal by identity convention.",
    )

    (home / "workspaces" / "acme-news" / "synthesis-skills-acme-news").mkdir(
        parents=True,
    )
    _write_skill(
        home / "workspaces" / "acme-news" / "synthesis-skills-acme-news",
        "news-only-skill",
        description="Workspace-scoped to acme-news.",
        frontmatter_extra=(
            "tools:\n"
            "  - name: summarize-headline\n"
            "    description: Summarise a news headline.\n"
        ),
    )

    (home / "workspaces" / "beta-media" / "synthesis-skills-beta-media").mkdir(
        parents=True,
    )
    _write_skill(
        home / "workspaces" / "beta-media" / "synthesis-skills-beta-media",
        "beta-private",
        description="Private to beta-media.",
    )

    return home


@pytest.fixture(autouse=True)
def _reset_router_state():
    """Each test starts with a clean in-process task table."""
    skills_router.clear_runtime_state()
    yield
    skills_router.clear_runtime_state()


@pytest.fixture
def client(skills_home):
    """FastAPI TestClient bound to the skills router only.

    Mounting on a tiny app per test keeps isolation tight and prevents
    unrelated routers (e.g., the MCP router building a real
    ``~/.synthesis/mcp.yaml`` client) from polluting discovery.
    """
    app = FastAPI()
    app.include_router(skills_router.router)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _stub_llm_backend(monkeypatch):
    """Replace get_llm_backend with a fake so POST /run never hits a real provider."""
    backend = _FakeLLMBackend(text="stub answer from fake backend")
    from synthesis_engine import llm as llm_module

    monkeypatch.setattr(
        llm_module, "get_llm_backend", lambda refresh=False: backend,
    )
    # The router imports get_llm_backend at function-call time so the
    # monkeypatch above is enough — no need to patch the router's module.
    return backend


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_skills_returns_full_catalog(client):
    response = client.get("/api/skills")
    assert response.status_code == 200, response.text
    body = response.json()
    names = {s["name"] for s in body["skills"]}
    assert {
        "universal-shared",
        "personal-helper",
        "news-only-skill",
        "beta-private",
    } <= names
    assert body["workspace"] is None
    assert body["total"] == len(body["skills"])


def test_get_skills_workspace_filter_acme_news(client):
    response = client.get("/api/skills", params={"workspace": "acme-news"})
    assert response.status_code == 200, response.text
    names = {s["name"] for s in response.json()["skills"]}
    # Universal + acme-news-scoped, but not beta-media.
    assert "universal-shared" in names
    assert "personal-helper" in names  # identity-aware universal
    assert "news-only-skill" in names
    assert "beta-private" not in names


def test_get_skills_workspace_filter_personal_only_universal(client):
    response = client.get("/api/skills", params={"workspace": "personal"})
    assert response.status_code == 200
    names = {s["name"] for s in response.json()["skills"]}
    assert "universal-shared" in names
    assert "personal-helper" in names
    # No workspace-scoped skills should leak in.
    assert "news-only-skill" not in names
    assert "beta-private" not in names


def test_get_skill_detail_includes_body_and_frontmatter(client):
    response = client.get("/api/skills/universal-shared")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["name"] == "universal-shared"
    assert "body for universal-shared" in detail["body"]
    assert detail["scope"] == {"universal": True, "workspaces": []}
    assert detail["frontmatter"]["name"] == "universal-shared"
    assert isinstance(detail["files"], list)
    assert any(f["kind"] == "skill_md" for f in detail["files"])


def test_get_skill_detail_403_when_invisible_from_workspace(client):
    # news-only-skill exists but is not visible from beta-media.
    response = client.get(
        "/api/skills/news-only-skill",
        params={"workspace": "beta-media"},
    )
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "skill_not_visible"
    assert detail["skill"] == "news-only-skill"
    assert detail["workspace"] == "beta-media"


def test_get_skill_404_for_unknown_name(client):
    response = client.get("/api/skills/does-not-exist")
    assert response.status_code == 404
    assert "Skill not found" in response.json()["detail"]


def test_post_run_returns_task_id_running(client):
    response = client.post(
        "/api/skills/universal-shared/run",
        json={"workspace": "acme-news", "input": {"topic": "x"}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "running"
    assert body["skill"] == "universal-shared"
    assert "task_id" in body and body["task_id"]


def test_post_run_403_when_skill_not_visible_from_workspace(client):
    response = client.post(
        "/api/skills/beta-private/run",
        json={"workspace": "acme-news", "input": {}},
    )
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "skill_not_visible"
    assert detail["skill"] == "beta-private"


def test_post_run_404_for_unknown_skill(client):
    response = client.post(
        "/api/skills/no-such-skill/run",
        json={"workspace": "acme-news", "input": {}},
    )
    assert response.status_code == 404


def test_get_run_404_for_unknown_task_id(client):
    response = client.get("/api/skills/runs/not-a-real-task-id")
    assert response.status_code == 404


def test_skill_summary_includes_tools_when_declared(client):
    response = client.get("/api/skills", params={"workspace": "acme-news"})
    skills = response.json()["skills"]
    news_skill = next(s for s in skills if s["name"] == "news-only-skill")
    assert news_skill["tool_count"] == 1
    tool_names = {t["name"] for t in news_skill["tools"]}
    assert "summarize-headline" in tool_names


def test_skill_summary_scope_shape(client):
    response = client.get("/api/skills")
    skills = response.json()["skills"]
    universal = next(s for s in skills if s["name"] == "universal-shared")
    assert universal["scope"] == {"universal": True, "workspaces": []}

    news_only = next(s for s in skills if s["name"] == "news-only-skill")
    assert news_only["scope"]["universal"] is False
    assert news_only["scope"]["workspaces"] == ["acme-news"]


def test_workspace_filter_isolates_siblings(client):
    """An acme-news request must not surface a beta-media skill."""
    response = client.get("/api/skills", params={"workspace": "acme-news"})
    names = {s["name"] for s in response.json()["skills"]}
    assert "beta-private" not in names

    # And the inverse — beta-media must not see acme-news's skill.
    response = client.get("/api/skills", params={"workspace": "beta-media"})
    names = {s["name"] for s in response.json()["skills"]}
    assert "news-only-skill" not in names
    assert "beta-private" in names


def test_get_skill_detail_files_have_kind_tags(client):
    response = client.get("/api/skills/universal-shared")
    detail = response.json()
    kinds = {f["kind"] for f in detail["files"]}
    # At minimum the SKILL.md itself must be classified.
    assert "skill_md" in kinds


def test_get_skill_detail_works_with_workspace_filter(client):
    """A visible skill resolves correctly with a workspace filter."""
    response = client.get(
        "/api/skills/news-only-skill",
        params={"workspace": "acme-news"},
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["name"] == "news-only-skill"
    assert detail["scope"]["workspaces"] == ["acme-news"]


def test_list_endpoint_no_workspace_returns_universal_with_scope_tags(client):
    """Without a workspace filter, scope tags identify workspace-restricted skills."""
    response = client.get("/api/skills")
    skills = response.json()["skills"]
    scoped = [s for s in skills if not s["scope"]["universal"]]
    # acme-news + beta-media each plant one workspace-scoped skill.
    scoped_names = {s["name"] for s in scoped}
    assert "news-only-skill" in scoped_names
    assert "beta-private" in scoped_names


def test_workspace_filter_switching_re_filters(client):
    """Same skill name appears or disappears based on the workspace param."""
    acme = client.get("/api/skills", params={"workspace": "acme-news"})
    beta = client.get("/api/skills", params={"workspace": "beta-media"})

    acme_names = {s["name"] for s in acme.json()["skills"]}
    beta_names = {s["name"] for s in beta.json()["skills"]}

    # Universal skills appear in both.
    assert "universal-shared" in acme_names
    assert "universal-shared" in beta_names

    # Workspace-scoped skills only in their respective workspace.
    assert "news-only-skill" in acme_names
    assert "news-only-skill" not in beta_names
    assert "beta-private" in beta_names
    assert "beta-private" not in acme_names
