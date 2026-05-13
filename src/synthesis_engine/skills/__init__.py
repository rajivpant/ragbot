"""Agent Skills support for Ragbot.

This module discovers, parses, and exposes Agent Skills (directories
containing a SKILL.md entry point) so the compiler and RAG indexer can
consume them as first-class content alongside (or instead of) legacy
runbooks.

A "skill" is a directory of files. The minimum is a single ``SKILL.md`` at
the directory root. Many skills add ``references/`` for additional
markdown, and a few include scripts or sub-tools.

Public API:

    discover_skills(roots)            -> List[Skill]
    parse_skill(directory)            -> Skill | None
    DEFAULT_SKILL_ROOTS               -> tuple of conventional roots
    Skill, SkillFile                  -> data classes

The compiler and indexer consume Skill objects directly; they do not need
to know about discovery internals.
"""

from __future__ import annotations

from .discovery import (
    DEFAULT_SKILL_ROOTS,
    discover_skills,
    discover_skills_in_root,
    get_skills_for_workspace,
    resolve_skill_roots,
)
from .model import Skill, SkillFile, SkillFileKind, SkillScope
from .parser import parse_skill, parse_skill_md

__all__ = [
    "DEFAULT_SKILL_ROOTS",
    "Skill",
    "SkillFile",
    "SkillFileKind",
    "SkillScope",
    "discover_skills",
    "discover_skills_in_root",
    "get_skills_for_workspace",
    "parse_skill",
    "parse_skill_md",
    "resolve_skill_roots",
]
