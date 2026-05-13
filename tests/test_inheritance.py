"""Tests for the substrate-level workspace inheritance module.

Covers the public API of ``synthesis_engine.inheritance``: YAML config
round-trips, discovery via the personal-repo conventions, inheritance-chain
traversal (linear and diamond), cycle detection, string-vs-list
``inherits_from`` normalization, dependency resolution, git clone-vs-pull
selection, and the ``ensure_repos_available`` reporting structure.
"""

from __future__ import annotations

import os
import subprocess

import pytest
import yaml

from synthesis_engine.inheritance import (
    clone_or_pull_repo,
    create_default_inheritance_config,
    ensure_repos_available,
    find_inheritance_config,
    get_inheritance_chain,
    get_project_config,
    get_repo_source_path,
    load_inheritance_config,
    resolve_dependencies,
)


# ---------------------------------------------------------------------------
# load_inheritance_config
# ---------------------------------------------------------------------------


class TestLoadInheritanceConfig:
    def test_happy_path_round_trips_yaml(self, tmp_path):
        config_path = tmp_path / "my-projects.yaml"
        original = {
            "version": 1,
            "projects": {
                "personal": {"inherits_from": ["root"]},
                "root": {"inherits_from": []},
            },
        }
        config_path.write_text(yaml.safe_dump(original))

        loaded = load_inheritance_config(str(config_path))
        assert loaded == original

    def test_missing_file_raises_filenotfounderror(self, tmp_path):
        missing = tmp_path / "does-not-exist.yaml"
        with pytest.raises(FileNotFoundError):
            load_inheritance_config(str(missing))


# ---------------------------------------------------------------------------
# find_inheritance_config
# ---------------------------------------------------------------------------


class TestFindInheritanceConfig:
    def test_discovers_at_repo_root(self, tmp_path):
        repo = tmp_path / "ai-knowledge-personal"
        repo.mkdir()
        config_path = repo / "my-projects.yaml"
        config_path.write_text("projects: {}\n")

        found = find_inheritance_config(str(repo))
        assert found == str(config_path)

    def test_discovers_under_source_directory_as_fallback(self, tmp_path):
        repo = tmp_path / "ai-knowledge-personal"
        source = repo / "source"
        source.mkdir(parents=True)
        config_path = source / "my-projects.yaml"
        config_path.write_text("projects: {}\n")

        found = find_inheritance_config(str(repo))
        assert found == str(config_path)

    def test_returns_none_when_neither_present(self, tmp_path):
        repo = tmp_path / "ai-knowledge-personal"
        repo.mkdir()
        assert find_inheritance_config(str(repo)) is None


# ---------------------------------------------------------------------------
# get_project_config
# ---------------------------------------------------------------------------


class TestGetProjectConfig:
    def test_returns_known_project_dict(self):
        config = {
            "projects": {
                "personal": {"inherits_from": ["root"], "repo": "ai-knowledge-personal"},
            }
        }
        assert get_project_config("personal", config) == {
            "inherits_from": ["root"],
            "repo": "ai-knowledge-personal",
        }

    def test_returns_empty_dict_for_unknown_project(self):
        assert get_project_config("does-not-exist", {"projects": {}}) == {}


# ---------------------------------------------------------------------------
# get_inheritance_chain
# ---------------------------------------------------------------------------


class TestGetInheritanceChain:
    def test_linear_chain_returns_parent_first_order(self):
        config = {
            "projects": {
                "A": {"inherits_from": ["B"]},
                "B": {"inherits_from": ["C"]},
                "C": {"inherits_from": ["root"]},
                "root": {"inherits_from": []},
            }
        }
        chain = get_inheritance_chain("A", config)
        assert chain == ["root", "C", "B", "A"]

    def test_diamond_inheritance_preserves_order_and_dedupes(self):
        # A inherits from B and C; B and C both inherit from D.
        # The chain must include D before B and C, and not duplicate D.
        config = {
            "projects": {
                "A": {"inherits_from": ["B", "C"]},
                "B": {"inherits_from": ["D"]},
                "C": {"inherits_from": ["D"]},
                "D": {"inherits_from": []},
            }
        }
        chain = get_inheritance_chain("A", config)
        # D must appear once, before B and C; A is last.
        assert chain.count("D") == 1
        assert chain.index("D") < chain.index("B")
        assert chain.index("D") < chain.index("C")
        assert chain[-1] == "A"

    def test_circular_dependency_raises_valueerror(self):
        config = {
            "projects": {
                "A": {"inherits_from": ["B"]},
                "B": {"inherits_from": ["A"]},
            }
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            get_inheritance_chain("A", config)

    def test_string_inherits_from_is_normalized_to_list(self):
        # Older configs use a plain string for `inherits_from`.
        config = {
            "projects": {
                "child": {"inherits_from": "parent"},
                "parent": {"inherits_from": []},
            }
        }
        chain = get_inheritance_chain("child", config)
        assert chain == ["parent", "child"]


# ---------------------------------------------------------------------------
# resolve_dependencies
# ---------------------------------------------------------------------------


class TestResolveDependencies:
    def test_returns_name_repo_local_path_and_config(self, tmp_path):
        config = {
            "projects": {
                "child": {
                    "inherits_from": ["parent"],
                    "repo": "custom-child-repo",
                    "local_path": str(tmp_path / "child"),
                },
                "parent": {
                    "inherits_from": [],
                    # No `repo` — should fall back to `ai-knowledge-{name}`.
                    "local_path": str(tmp_path / "parent"),
                },
            }
        }
        deps = resolve_dependencies("child", config)
        assert len(deps) == 2

        parent_dep, child_dep = deps  # Parent first, child last.
        assert parent_dep["name"] == "parent"
        assert parent_dep["repo"] == "ai-knowledge-parent"
        assert parent_dep["local_path"] == str(tmp_path / "parent")
        assert parent_dep["config"] == config["projects"]["parent"]

        assert child_dep["name"] == "child"
        assert child_dep["repo"] == "custom-child-repo"
        assert child_dep["local_path"] == str(tmp_path / "child")
        assert child_dep["config"] == config["projects"]["child"]


# ---------------------------------------------------------------------------
# clone_or_pull_repo
# ---------------------------------------------------------------------------


class TestCloneOrPullRepo:
    def test_existing_path_triggers_git_pull(self, tmp_path, mocker):
        existing = tmp_path / "existing-repo"
        existing.mkdir()
        run_mock = mocker.patch("synthesis_engine.inheritance.subprocess.run")

        result = clone_or_pull_repo(
            "https://example.invalid/repo.git", str(existing), quiet=True
        )

        assert result is True
        run_mock.assert_called_once()
        args, kwargs = run_mock.call_args
        invoked = args[0]
        assert invoked[0] == "git"
        assert invoked[1] == "pull"
        assert "--quiet" in invoked
        assert kwargs.get("cwd") == str(existing)
        assert kwargs.get("check") is True

    def test_missing_path_triggers_git_clone(self, tmp_path, mocker):
        target = tmp_path / "nested" / "new-repo"
        run_mock = mocker.patch("synthesis_engine.inheritance.subprocess.run")

        result = clone_or_pull_repo(
            "https://example.invalid/repo.git", str(target), quiet=True
        )

        assert result is True
        run_mock.assert_called_once()
        invoked = run_mock.call_args[0][0]
        assert invoked[0] == "git"
        assert invoked[1] == "clone"
        assert "https://example.invalid/repo.git" in invoked
        assert str(target) in invoked
        # Parent directory must have been created before clone.
        assert target.parent.is_dir()

    def test_failure_returns_false(self, tmp_path, mocker):
        existing = tmp_path / "existing-repo"
        existing.mkdir()
        mocker.patch(
            "synthesis_engine.inheritance.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["git", "pull"]),
        )
        result = clone_or_pull_repo(
            "https://example.invalid/repo.git", str(existing)
        )
        assert result is False


# ---------------------------------------------------------------------------
# ensure_repos_available
# ---------------------------------------------------------------------------


class TestEnsureReposAvailable:
    def test_reports_existing_paths_as_available(self, tmp_path):
        existing = tmp_path / "ai-knowledge-personal"
        existing.mkdir()

        dependencies = [
            {
                "name": "personal",
                "repo": "ai-knowledge-personal",
                "local_path": str(existing),
                "config": {},
            }
        ]
        result = ensure_repos_available(dependencies, str(tmp_path))

        assert result["success"] is True
        assert result["missing"] == []
        assert result["errors"] == []
        assert result["available"] == [{"name": "personal", "path": str(existing)}]

    def test_reports_missing_when_no_path_and_no_github_user(self, tmp_path):
        dependencies = [
            {
                "name": "ghost",
                "repo": "ai-knowledge-ghost",
                "local_path": None,
                "config": {},
            }
        ]
        result = ensure_repos_available(dependencies, str(tmp_path))

        assert result["success"] is False
        assert result["missing"] == ["ghost"]
        assert len(result["errors"]) == 1
        assert "Repo not found" in result["errors"][0]
        assert result["available"] == []

    def test_clones_when_missing_path_and_github_user_supplied(self, tmp_path, mocker):
        target = tmp_path / "ai-knowledge-ghost"
        clone_mock = mocker.patch(
            "synthesis_engine.inheritance.clone_or_pull_repo",
            return_value=True,
        )
        # The clone is mocked to succeed; ensure_repos_available then checks
        # back via os.path.exists in the available branch, which it won't
        # because the mock did not actually create the directory. So the
        # success-with-clone path here is verified by inspecting the mock and
        # by the fact that ensure_repos_available adds to `available` based on
        # the clone's return value, not by re-checking the filesystem.
        dependencies = [
            {
                "name": "ghost",
                "repo": "ai-knowledge-ghost",
                "local_path": str(target),
                "config": {},
            }
        ]
        result = ensure_repos_available(
            dependencies, str(tmp_path), github_user="example-org"
        )

        # The mock was invoked with a constructed GitHub URL.
        clone_mock.assert_called_once()
        invoked_url = clone_mock.call_args[0][0]
        assert invoked_url == "https://github.com/example-org/ai-knowledge-ghost.git"
        assert result["available"] == [{"name": "ghost", "path": str(target)}]
        assert result["success"] is True


# ---------------------------------------------------------------------------
# get_repo_source_path + create_default_inheritance_config
# ---------------------------------------------------------------------------


class TestRepoSourcePathAndDefaultConfig:
    def test_get_repo_source_path_returns_source_subdir(self):
        assert get_repo_source_path("/repos/ai-knowledge-personal") == os.path.join(
            "/repos/ai-knowledge-personal", "source"
        )

    def test_create_default_inheritance_config_scans_directories(self, tmp_path):
        base = tmp_path / "ai-knowledge"
        base.mkdir()
        (base / "ai-knowledge-personal").mkdir()
        (base / "ai-knowledge-example-client").mkdir()
        (base / "unrelated-dir").mkdir()  # Should be skipped.

        config = create_default_inheritance_config(
            str(base / "ai-knowledge-personal"), str(base)
        )

        assert config["version"] == 1
        assert "projects" in config
        assert set(config["projects"].keys()) == {"personal", "example-client"}
        assert config["projects"]["personal"]["local_path"] == str(
            base / "ai-knowledge-personal"
        )
        assert config["projects"]["personal"]["inherits_from"] == []

    def test_create_default_inheritance_config_with_missing_base(self, tmp_path):
        # Nonexistent base path leaves the projects map empty.
        config = create_default_inheritance_config(
            str(tmp_path / "personal"), str(tmp_path / "does-not-exist")
        )
        assert config["projects"] == {}
