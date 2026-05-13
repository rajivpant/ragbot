"""Tests for the workspace-scoped `ragbot skills` CLI subcommands (Phase 2 Agent D).

Coverage:

  1. Bare `ragbot skills list` prints every discovered skill with scope.
  2. `ragbot skills list --workspace acme-news` filters to the workspace's
     visible set (universal + acme-news-scoped).
  3. `ragbot skills list --workspace beta-media` shows beta-media's
     skills but not acme-news's.
  4. `ragbot skills list -v` preserves the legacy verbose layout and adds
     the scope tag.
  5. `ragbot skills list --workspace personal` shows universal-only when
     no workspace-scoped skills target personal.
  6. `ragbot skills run universal-shared --workspace acme-news` activates
     and prints the LLM response (fake backend).
  7. `ragbot skills run beta-private --workspace acme-news` refuses with
     a clear error and exits non-zero.
  8. `ragbot skills run no-such-skill --workspace acme-news` refuses with
     a "not visible" error.
  9. `ragbot skills run universal-shared --input KEY=value` parses inputs.
 10. `ragbot skills run universal-shared --file path` reads the file and
     binds its contents to the ``file`` input.

The tests run the CLI by importing ``ragbot.main`` and dispatching via
``sys.argv``. Discovery is patched to a synthetic tree under tmp_path so
no real ``$HOME`` is touched. LLM calls go through a fake backend so the
suite is hermetic.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Fake LLM backend
# ---------------------------------------------------------------------------


@dataclass
class _FakeLLMResponse:
    text: str
    model: str = "fake-model"
    backend: str = "fake"
    finish_reason: Optional[str] = "stop"
    usage: Dict[str, int] = field(default_factory=dict)


class _FakeLLMBackend:
    backend_name = "fake"

    def __init__(self, text: str = "stub-cli-answer") -> None:
        self._text = text
        self.calls: List[Any] = []

    def complete(self, request: Any) -> _FakeLLMResponse:
        self.calls.append(request)
        return _FakeLLMResponse(text=self._text)

    def stream(self, request: Any, on_chunk):  # pragma: no cover - unused
        on_chunk(self._text)
        return self._text

    def healthcheck(self) -> Dict[str, Any]:
        return {"backend": self.backend_name, "ok": True}


# ---------------------------------------------------------------------------
# Skill tree fixture
# ---------------------------------------------------------------------------


def _write_skill(
    root: Path,
    name: str,
    description: str = "",
    frontmatter_extra: str = "",
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    body = (
        "---\n"
        f"name: {name}\n"
        f"description: {description or 'cli fixture skill'}\n"
        f"{frontmatter_extra}"
        "---\n\n"
        f"# {name}\n\nbody for {name}.\n"
    )
    (skill_dir / "SKILL.md").write_text(body)
    return skill_dir


@pytest.fixture
def skills_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".synthesis").mkdir()
    identity = home / ".synthesis" / "identity.yaml"
    identity.write_text("personal_workspaces:\n  - acme-user\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", str(identity))

    (home / ".synthesis" / "skills").mkdir(parents=True, exist_ok=True)
    _write_skill(
        home / ".synthesis" / "skills",
        "universal-shared",
        description="Universal CLI skill.",
    )

    (home / "workspaces" / "acme-user" / "synthesis-skills").mkdir(parents=True)
    _write_skill(
        home / "workspaces" / "acme-user" / "synthesis-skills",
        "personal-cli-helper",
        description="Personal-workspace helper, universal via identity.",
    )

    (home / "workspaces" / "acme-news" / "synthesis-skills-acme-news").mkdir(
        parents=True,
    )
    _write_skill(
        home / "workspaces" / "acme-news" / "synthesis-skills-acme-news",
        "news-only-skill",
        description="acme-news-scoped CLI skill.",
    )

    (home / "workspaces" / "beta-media" / "synthesis-skills-beta-media").mkdir(
        parents=True,
    )
    _write_skill(
        home / "workspaces" / "beta-media" / "synthesis-skills-beta-media",
        "beta-private",
        description="beta-media-scoped CLI skill.",
    )

    return home


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    backend = _FakeLLMBackend(text="stub-cli-answer")
    from synthesis_engine import llm as llm_module

    monkeypatch.setattr(
        llm_module, "get_llm_backend", lambda refresh=False: backend,
    )
    return backend


# ---------------------------------------------------------------------------
# CLI runner helper
# ---------------------------------------------------------------------------


def _load_cli_module():
    """Import the ``src/ragbot.py`` CLI script under a unique module name.

    The package ``src/ragbot/`` shadows the script's name on a normal
    import, so we load it by file path. Cached on the module attribute
    so repeated calls reuse one module instance — pytest fixtures only
    monkeypatch the runtime, not the imports.
    """
    import importlib.util

    cached = getattr(_load_cli_module, "_module", None)
    if cached is not None:
        return cached
    script_path = os.path.join(_REPO_SRC, "ragbot.py")
    spec = importlib.util.spec_from_file_location("ragbot_cli_script", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ragbot_cli_script"] = module
    spec.loader.exec_module(module)
    _load_cli_module._module = module
    return module


def _run_cli(argv: List[str], monkeypatch) -> int:
    """Invoke the ragbot CLI's ``main()`` with the supplied argv.

    Returns the exit code from ``main()``. Subprocess invocation would
    be slower and would lose the in-test monkeypatches that point
    ``Path.home`` at the synthetic tree.
    """
    monkeypatch.setattr(sys, "argv", ["ragbot"] + argv)
    ragbot_cli = _load_cli_module()
    return ragbot_cli.main() or 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_list_bare_shows_every_skill(skills_home, capsys, monkeypatch):
    rc = _run_cli(["skills", "list"], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    assert "universal-shared" in out
    assert "personal-cli-helper" in out
    assert "news-only-skill" in out
    assert "beta-private" in out
    # The default table layout shows scope tags.
    assert "universal" in out
    assert "workspace:acme-news" in out
    assert "workspace:beta-media" in out


def test_cli_list_workspace_filter_acme_news(skills_home, capsys, monkeypatch):
    rc = _run_cli(
        ["skills", "list", "--workspace", "acme-news"], monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "universal-shared" in out
    assert "personal-cli-helper" in out
    assert "news-only-skill" in out
    # beta-private must NOT leak across workspace boundaries.
    assert "beta-private" not in out
    assert "visible from workspace 'acme-news'" in out


def test_cli_list_workspace_filter_beta_media(skills_home, capsys, monkeypatch):
    rc = _run_cli(
        ["skills", "list", "--workspace", "beta-media"], monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "universal-shared" in out
    assert "beta-private" in out
    assert "news-only-skill" not in out


def test_cli_list_verbose_preserves_legacy_layout(
    skills_home, capsys, monkeypatch,
):
    rc = _run_cli(["skills", "list", "-v"], monkeypatch)
    assert rc == 0
    out = capsys.readouterr().out
    # Verbose layout includes the scope tag inline.
    assert "[universal]" in out
    assert "[workspace:acme-news]" in out
    # And the per-skill description block.
    assert "Universal CLI skill." in out


def test_cli_list_workspace_personal_only_universal(
    skills_home, capsys, monkeypatch,
):
    rc = _run_cli(
        ["skills", "list", "--workspace", "personal"], monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "universal-shared" in out
    assert "personal-cli-helper" in out
    assert "news-only-skill" not in out
    assert "beta-private" not in out


def test_cli_run_universal_skill_emits_answer(
    skills_home, capsys, monkeypatch,
):
    rc = _run_cli(
        [
            "skills", "run", "universal-shared",
            "--workspace", "acme-news",
            "--input", "topic=climate",
        ],
        monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "stub-cli-answer" in out


def test_cli_run_refuses_invisible_skill(skills_home, capsys, monkeypatch):
    rc = _run_cli(
        [
            "skills", "run", "beta-private",
            "--workspace", "acme-news",
        ],
        monkeypatch,
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "beta-private" in err
    assert "not visible" in err.lower() or "not visible from workspace" in err


def test_cli_run_refuses_unknown_skill(skills_home, capsys, monkeypatch):
    rc = _run_cli(
        [
            "skills", "run", "no-such-skill",
            "--workspace", "acme-news",
        ],
        monkeypatch,
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "no-such-skill" in err


def test_cli_run_parses_input_kv_pairs(
    skills_home, capsys, monkeypatch, _stub_llm,
):
    rc = _run_cli(
        [
            "skills", "run", "universal-shared",
            "--workspace", "acme-news",
            "--input", "topic=climate",
            "--input", "count=3",
            "--input", "tags=[\"a\",\"b\"]",
        ],
        monkeypatch,
    )
    assert rc == 0
    # The backend was called once; inspect the request body.
    assert len(_stub_llm.calls) == 1
    msg_content = _stub_llm.calls[0].messages[0]["content"]
    # JSON-parsed inputs land in the prompt body.
    assert "climate" in msg_content
    # Numeric is parsed as a number, not a string-quoted token.
    assert "\"count\": 3" in msg_content
    # List was parsed as JSON.
    assert "\"tags\": [" in msg_content


def test_cli_run_reads_file_input(
    skills_home, tmp_path, capsys, monkeypatch, _stub_llm,
):
    file_path = tmp_path / "input.txt"
    file_path.write_text("contents of the input file")
    rc = _run_cli(
        [
            "skills", "run", "universal-shared",
            "--workspace", "acme-news",
            "--file", str(file_path),
        ],
        monkeypatch,
    )
    assert rc == 0
    assert len(_stub_llm.calls) == 1
    msg_content = _stub_llm.calls[0].messages[0]["content"]
    assert "contents of the input file" in msg_content


def test_cli_run_universal_skill_without_workspace_works(
    skills_home, capsys, monkeypatch,
):
    """A bare `ragbot skills run universal-shared` (no --workspace) runs
    against the universal-only chain and still finds universal skills."""
    rc = _run_cli(
        ["skills", "run", "universal-shared"],
        monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "stub-cli-answer" in out


def test_cli_list_no_match_message(skills_home, capsys, monkeypatch):
    """A workspace with no visible skills emits a clear empty-list message.

    We point the discovery layer at a workspace that has neither a per-
    workspace skill collection nor any inherited universals — by
    arranging the synthetic tree such that the `solo` workspace has no
    matching `synthesis-skills-solo` and there are no universals visible
    here.

    The fixture's universal skills (under ~/.synthesis/skills and the
    identity-aware personal-skills root) are still visible from every
    workspace, so we expect a non-zero count. Confirm the output prints
    the workspace-scoped header instead of the all-workspaces header.
    """
    rc = _run_cli(
        ["skills", "list", "--workspace", "solo-workspace"], monkeypatch,
    )
    assert rc == 0
    out = capsys.readouterr().out
    # Workspace-scoped header includes the workspace name.
    assert "visible from workspace 'solo-workspace'" in out
    # Universal skills appear regardless of workspace.
    assert "universal-shared" in out


def test_cli_list_help_documents_run_subcommand(monkeypatch, capsys):
    """The `ragbot skills --help` output advertises the new run subcommand."""
    monkeypatch.setattr(sys, "argv", ["ragbot", "skills", "--help"])
    ragbot_cli = _load_cli_module()

    # argparse exits with 0 after printing help; capture the SystemExit.
    with pytest.raises(SystemExit) as exc:
        ragbot_cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "run" in out


def test_cli_run_help_documents_flags(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["ragbot", "skills", "run", "--help"])
    ragbot_cli = _load_cli_module()

    with pytest.raises(SystemExit) as exc:
        ragbot_cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--workspace" in out
    assert "--input" in out
    assert "--file" in out
