"""Tests for synthesis_engine.identity — substrate identity config loader."""

from __future__ import annotations

import textwrap

import pytest

from synthesis_engine.identity import (
    DEFAULT_IDENTITY_PATH,
    get_personal_workspaces,
    is_personal_workspace,
)


def _write_config(tmp_path, body: str) -> str:
    path = tmp_path / "identity.yaml"
    path.write_text(textwrap.dedent(body))
    return str(path)


def test_missing_config_returns_empty(tmp_path):
    missing = tmp_path / "nope.yaml"
    assert get_personal_workspaces(str(missing)) == []
    assert is_personal_workspace("acme-user", str(missing)) is False


def test_well_formed_config_returns_list(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - acme-user
          - beta-user
        """,
    )
    assert get_personal_workspaces(cfg) == ["acme-user", "beta-user"]
    assert is_personal_workspace("acme-user", cfg) is True
    assert is_personal_workspace("beta-user", cfg) is True
    assert is_personal_workspace("acme-news", cfg) is False


def test_single_string_normalises_to_one_element_list(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces: solo
        """,
    )
    assert get_personal_workspaces(cfg) == ["solo"]


def test_missing_field_returns_empty(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        other_field: value
        """,
    )
    assert get_personal_workspaces(cfg) == []


def test_malformed_yaml_returns_empty(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("this is: not [closed properly")
    assert get_personal_workspaces(str(path)) == []


def test_duplicates_are_removed_in_first_occurrence_order(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - acme-user
          - beta-user
          - acme-user
          - acme-user
        """,
    )
    assert get_personal_workspaces(cfg) == ["acme-user", "beta-user"]


def test_whitespace_and_empty_entries_dropped(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - "  acme-user  "
          - ""
          - "   "
        """,
    )
    assert get_personal_workspaces(cfg) == ["acme-user"]


def test_non_string_entries_dropped(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - acme-user
          - 42
          - null
          - {nested: object}
        """,
    )
    assert get_personal_workspaces(cfg) == ["acme-user"]


def test_env_override_takes_precedence(tmp_path, monkeypatch):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - via-env
        """,
    )
    monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", cfg)
    # Explicit None should fall through to the env var.
    assert get_personal_workspaces() == ["via-env"]


def test_explicit_path_beats_env_override(tmp_path, monkeypatch):
    env_cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - via-env
        """,
    )
    arg_cfg = tmp_path / "arg.yaml"
    arg_cfg.write_text(
        textwrap.dedent(
            """
            personal_workspaces:
              - via-arg
            """
        )
    )
    monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", env_cfg)
    assert get_personal_workspaces(str(arg_cfg)) == ["via-arg"]


def test_default_path_lives_in_synthesis_home():
    assert str(DEFAULT_IDENTITY_PATH).endswith("/.synthesis/identity.yaml")


def test_empty_workspace_name_is_not_personal(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        personal_workspaces:
          - acme-user
        """,
    )
    assert is_personal_workspace("", cfg) is False
