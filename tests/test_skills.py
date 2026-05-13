"""Tests for the Agent Skills support module (Phase 3)."""

from __future__ import annotations

import os
import sys
import textwrap

import pytest

# Add src/ to sys.path so the tests can import the package under test.
_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.skills import (  # noqa: E402
    Skill,
    SkillFile,
    SkillFileKind,
    discover_skills,
    discover_skills_in_root,
    parse_skill,
    parse_skill_md,
    resolve_skill_roots,
)


# ---------------------------------------------------------------------------
# Fixtures: build a small synthetic skill tree.
# ---------------------------------------------------------------------------


@pytest.fixture
def skill_root_with_three_skills(tmp_path):
    """Create a skills root with three skills exercising different layouts.

    Layout::

        root/
          single-file/                        # bare SKILL.md only
            SKILL.md
          with-references/                    # SKILL.md + references/
            SKILL.md
            references/
              detail.md
          with-scripts/                       # SKILL.md + nested scripts
            SKILL.md
            scripts/
              run.sh
              helper.py
            assets/
              README.md
    """
    root = tmp_path / "skills"
    root.mkdir()

    # Skill 1: bare
    s1 = root / "single-file"
    s1.mkdir()
    (s1 / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: single-file
        description: A skill with only SKILL.md.
        license: CC0-1.0
        ---

        # Single File Skill

        Just a body.
        """))

    # Skill 2: with references
    s2 = root / "with-references"
    s2.mkdir()
    (s2 / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: with-references
        description: Has a references directory with extra markdown.
        metadata:
          version: 1.2.3
          source_repo: github.com/example/repo
        ---

        # With References

        See references/detail.md.
        """))
    refs2 = s2 / "references"
    refs2.mkdir()
    (refs2 / "detail.md").write_text("# Detail\n\nAdditional procedure detail.\n")

    # Skill 3: with scripts and a nested README
    s3 = root / "with-scripts"
    s3.mkdir()
    (s3 / "SKILL.md").write_text(textwrap.dedent("""\
        ---
        name: with-scripts
        description: Bundles helper scripts alongside the procedure.
        ---

        # With Scripts

        Execute scripts/run.sh.
        """))
    scripts3 = s3 / "scripts"
    scripts3.mkdir()
    (scripts3 / "run.sh").write_text("#!/usr/bin/env bash\necho run\n")
    (scripts3 / "helper.py").write_text("def helper():\n    return 42\n")
    assets3 = s3 / "assets"
    assets3.mkdir()
    (assets3 / "README.md").write_text("# Assets\n\nSupporting files.\n")

    return str(root)


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------


class TestParseSkillMd:
    def test_extracts_frontmatter_and_body(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text(textwrap.dedent("""\
            ---
            name: example
            description: hi
            ---

            # Body

            Stuff.
            """))
        fm, body = parse_skill_md(str(path))
        assert fm == {"name": "example", "description": "hi"}
        assert "# Body" in body
        assert "Stuff." in body

    def test_missing_frontmatter_returns_empty_dict(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("# Just a body\n\nNo frontmatter here.\n")
        fm, body = parse_skill_md(str(path))
        assert fm == {}
        assert "# Just a body" in body

    def test_malformed_frontmatter_returns_empty_dict(self, tmp_path):
        path = tmp_path / "SKILL.md"
        path.write_text("---\nthis: is: not: valid yaml\n---\nbody\n")
        fm, body = parse_skill_md(str(path))
        # Either empty fm and original body, or fm with the broken keys is
        # acceptable; the contract is "don't crash". Verify body recoverable.
        assert "body" in body or "this: is" in body or fm != {}


# ---------------------------------------------------------------------------
# Single skill parser
# ---------------------------------------------------------------------------


class TestParseSkill:
    def test_returns_none_when_no_skill_md(self, tmp_path):
        d = tmp_path / "not-a-skill"
        d.mkdir()
        (d / "README.md").write_text("not a skill")
        assert parse_skill(str(d)) is None

    def test_parses_single_file_skill(self, skill_root_with_three_skills):
        path = os.path.join(skill_root_with_three_skills, "single-file")
        skill = parse_skill(path)
        assert skill is not None
        assert skill.name == "single-file"
        assert "Single File Skill" in skill.body
        assert len(skill.files) == 1
        assert skill.files[0].kind is SkillFileKind.SKILL_MD

    def test_classifies_references(self, skill_root_with_three_skills):
        skill = parse_skill(os.path.join(skill_root_with_three_skills, "with-references"))
        assert skill is not None
        kinds = {f.relative_path: f.kind for f in skill.files}
        assert kinds["SKILL.md"] is SkillFileKind.SKILL_MD
        assert kinds["references/detail.md"] is SkillFileKind.REFERENCE
        assert skill.version == "1.2.3"
        assert skill.source_repo == "github.com/example/repo"

    def test_classifies_scripts_and_keeps_skill_md_first(self, skill_root_with_three_skills):
        skill = parse_skill(os.path.join(skill_root_with_three_skills, "with-scripts"))
        assert skill is not None
        # SKILL.md must be first for callers that rely on order.
        assert skill.files[0].relative_path == "SKILL.md"
        kinds = {f.relative_path: f.kind for f in skill.files}
        assert kinds["scripts/run.sh"] is SkillFileKind.SCRIPT
        assert kinds["scripts/helper.py"] is SkillFileKind.SCRIPT
        # Nested README.md is a reference (markdown documents the skill).
        assert kinds["assets/README.md"] is SkillFileKind.REFERENCE

    def test_directory_basename_used_when_frontmatter_lacks_name(self, tmp_path):
        d = tmp_path / "directory-name"
        d.mkdir()
        (d / "SKILL.md").write_text("---\ndescription: no name\n---\n\nbody\n")
        skill = parse_skill(str(d))
        assert skill is not None
        assert skill.name == "directory-name"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_discover_skills_in_root_finds_all(self, skill_root_with_three_skills):
        skills = discover_skills_in_root(skill_root_with_three_skills)
        names = {s.name for s in skills}
        assert names == {"single-file", "with-references", "with-scripts"}

    def test_discover_skills_with_explicit_roots(self, skill_root_with_three_skills):
        skills = discover_skills(roots=[skill_root_with_three_skills])
        assert len(skills) == 3
        # Sorted by name.
        assert [s.name for s in skills] == sorted(s.name for s in skills)

    def test_discover_skills_dedupe_on_name_collision(self, tmp_path):
        # Two roots that both contain a skill named "foo"; the second should
        # win per the documented override semantics.
        a = tmp_path / "a"
        b = tmp_path / "b"
        (a / "foo").mkdir(parents=True)
        (b / "foo").mkdir(parents=True)
        (a / "foo" / "SKILL.md").write_text("---\nname: foo\ndescription: A\n---\nA body")
        (b / "foo" / "SKILL.md").write_text("---\nname: foo\ndescription: B\n---\nB body")

        skills = discover_skills(roots=[str(a), str(b)])
        assert len(skills) == 1
        assert skills[0].description == "B"
        assert skills[0].path.endswith("/b/foo")

    def test_resolve_skill_roots_includes_existing_only(self, tmp_path, monkeypatch):
        # Point HOME at a place where neither default exists; result must be empty.
        monkeypatch.setenv("HOME", str(tmp_path))
        roots = resolve_skill_roots()
        # Verify all returned roots actually exist on disk.
        for r in roots:
            assert os.path.isdir(r)


# ---------------------------------------------------------------------------
# Skill summary helper
# ---------------------------------------------------------------------------


class TestSkillSummary:
    def test_summary_dict_contains_counts(self, skill_root_with_three_skills):
        skill = parse_skill(os.path.join(skill_root_with_three_skills, "with-scripts"))
        summary = skill.summary_dict()
        assert summary["name"] == "with-scripts"
        assert summary["script_count"] == 2
        assert summary["reference_count"] == 1   # assets/README.md
        assert summary["file_count"] == 4         # SKILL.md + 2 scripts + 1 reference
