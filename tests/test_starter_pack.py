"""Tests for the bundled starter-pack of universal skills (Phase 2 Agent C).

The starter pack ships five universal skills under
``src/synthesis_engine/skills/starter_pack/``. These tests verify that:

* Each SKILL.md parses cleanly through the existing parser.
* Each skill is universally scoped via explicit frontmatter.
* Skills declaring ``tools:`` expose the declarations on the parsed Skill.
* ``list_starter_skill_paths()`` enumerates exactly the expected five.
* ``discover_skills_in_root(starter_pack_root)`` finds all five.
* ``get_skills_for_workspace("acme-news")`` returns all five via the
  default discovery chain — and does not return them duplicated even
  though both the starter pack and any other roots may surface them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Set

import pytest

# Add src/ to sys.path so the tests can import the package under test.
_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.skills import (  # noqa: E402
    Skill,
    discover_skills,
    discover_skills_in_root,
    get_skills_for_workspace,
    parse_skill,
)
from synthesis_engine.skills.starter_pack import (  # noqa: E402
    list_starter_skill_paths,
    starter_pack_root,
)


# The canonical five names the pack ships.
EXPECTED_NAMES: Set[str] = {
    "workspace-search-with-citations",
    "draft-and-revise",
    "fact-check-claims",
    "summarize-document",
    "agent-self-review",
}

# Skills declared to expose a ``tools:`` array in their frontmatter.
SKILLS_WITH_TOOLS: Set[str] = {
    "workspace-search-with-citations",
    "fact-check-claims",
}


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch) -> Path:
    """Isolate ``Path.home()`` so the discovery chain does not pull in
    the operator's real skills, and write a minimal identity declaring
    ``acme-user`` as a personal workspace.

    The starter pack is bundled inside the source tree, so it is found
    regardless of the home-directory layout. The test workspace
    ``acme-news`` is not declared as personal — that is the realistic
    shape for verifying universal scope routing.
    """
    home = tmp_path / "fakehome"
    home.mkdir()
    (home / ".synthesis" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / "workspaces" / "acme-user" / "synthesis-skills").mkdir(parents=True)

    identity = home / ".synthesis" / "identity.yaml"
    identity.write_text("personal_workspaces:\n  - acme-user\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("SYNTHESIS_IDENTITY_CONFIG", str(identity))
    return home


# ---------------------------------------------------------------------------
# Per-skill parse tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("skill_name", sorted(EXPECTED_NAMES))
class TestEachStarterSkillParses:
    def test_parses_without_errors(self, skill_name: str) -> None:
        path = os.path.join(starter_pack_root(), skill_name)
        skill = parse_skill(path)
        assert skill is not None, f"parse_skill returned None for {skill_name}"
        assert skill.name == skill_name

    def test_scope_is_universal(self, skill_name: str) -> None:
        path = os.path.join(starter_pack_root(), skill_name)
        skill = parse_skill(path)
        assert skill is not None
        assert skill.scope.universal is True, (
            f"{skill_name} should have universal scope; got "
            f"universal={skill.scope.universal}, workspaces={skill.scope.workspaces}"
        )
        assert skill.scope.workspaces == ()

    def test_description_and_body_are_non_empty(self, skill_name: str) -> None:
        path = os.path.join(starter_pack_root(), skill_name)
        skill = parse_skill(path)
        assert skill is not None
        assert skill.description.strip(), f"{skill_name} has empty description"
        assert skill.body.strip(), f"{skill_name} has empty body"
        # Body should be substantive, not a stub.
        assert len(skill.body) > 500, (
            f"{skill_name} body is suspiciously short "
            f"({len(skill.body)} chars); starter-pack skills must be real."
        )


class TestSkillsWithTools:
    """Skills that declare ``tools:`` in frontmatter must surface them."""

    @pytest.mark.parametrize("skill_name", sorted(SKILLS_WITH_TOOLS))
    def test_tools_list_exposed_on_frontmatter(self, skill_name: str) -> None:
        path = os.path.join(starter_pack_root(), skill_name)
        skill = parse_skill(path)
        assert skill is not None
        tools = skill.frontmatter.get("tools")
        assert isinstance(tools, list), (
            f"{skill_name} expected list under tools:; got {type(tools).__name__}"
        )
        assert len(tools) >= 1, f"{skill_name} declares tools: but list is empty"
        for tool in tools:
            assert isinstance(tool, dict), f"{skill_name} tool entry is not a mapping"
            assert tool.get("name"), f"{skill_name} tool entry missing name"
            assert tool.get("description"), (
                f"{skill_name} tool {tool.get('name')!r} missing description"
            )
            # Each declared tool should specify an input_schema; this is
            # the contract downstream agent runtimes consume.
            assert tool.get("input_schema"), (
                f"{skill_name} tool {tool.get('name')!r} missing input_schema"
            )


# ---------------------------------------------------------------------------
# Discovery wiring
# ---------------------------------------------------------------------------


class TestListStarterSkillPaths:
    def test_returns_exactly_five_paths(self) -> None:
        paths = list_starter_skill_paths()
        assert len(paths) == 5, f"Expected 5 starter skills, got {len(paths)}"

    def test_each_returned_path_exists_with_skill_md(self) -> None:
        paths = list_starter_skill_paths()
        for p in paths:
            assert os.path.isdir(p), f"Returned path is not a directory: {p}"
            assert os.path.isfile(os.path.join(p, "SKILL.md")), (
                f"Returned path lacks SKILL.md: {p}"
            )

    def test_returned_paths_match_expected_names(self) -> None:
        paths = list_starter_skill_paths()
        names = {os.path.basename(p) for p in paths}
        assert names == EXPECTED_NAMES


class TestDiscoverSkillsInStarterPackRoot:
    def test_all_five_discovered_from_pack_root(self) -> None:
        skills = discover_skills_in_root(starter_pack_root())
        names = {s.name for s in skills}
        assert names == EXPECTED_NAMES

    def test_all_five_are_universal(self) -> None:
        skills = discover_skills_in_root(starter_pack_root())
        for skill in skills:
            assert skill.scope.universal is True, (
                f"{skill.name} discovered with non-universal scope: "
                f"{skill.scope}"
            )


# ---------------------------------------------------------------------------
# Workspace-scoped retrieval surfaces the pack
# ---------------------------------------------------------------------------


class TestGetSkillsForWorkspaceIncludesStarterPack:
    def test_all_five_visible_to_acme_news(self, fake_home: Path) -> None:
        """An ordinary (non-personal) workspace must see every starter
        skill via universal scope, without needing any installed roots.
        """
        skills = get_skills_for_workspace("acme-news", inheritance_config={})
        names = {s.name for s in skills}
        for expected in EXPECTED_NAMES:
            assert expected in names, (
                f"Starter skill {expected!r} not visible from acme-news; "
                f"got {sorted(names)}"
            )

    def test_starter_skills_not_duplicated_when_chain_runs(
        self, fake_home: Path
    ) -> None:
        """Discovery walks the starter pack as one of several roots. The
        result must not contain duplicates even if the same name would
        otherwise show up twice (e.g., starter pack plus a hypothetical
        operator-installed copy).
        """
        skills = get_skills_for_workspace("acme-news", inheritance_config={})
        names_list = [s.name for s in skills]
        # Each name appears exactly once.
        for name in EXPECTED_NAMES:
            assert names_list.count(name) == 1, (
                f"Starter skill {name!r} appears {names_list.count(name)} "
                f"times in the workspace view; expected 1"
            )

    def test_default_discovery_finds_starter_pack(self, fake_home: Path) -> None:
        """Even with no skills planted in any operator-installed root,
        ``discover_skills()`` returns the starter pack because the pack
        is part of the default chain.
        """
        skills = discover_skills()
        names = {s.name for s in skills}
        for expected in EXPECTED_NAMES:
            assert expected in names, (
                f"Default discovery did not surface starter skill "
                f"{expected!r}; got {sorted(names)}"
            )
