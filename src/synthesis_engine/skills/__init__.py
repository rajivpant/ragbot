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
from .loader import (
    ActivatedSkill,
    ScriptNotFoundError,
    ScriptPathError,
    SkillLoader,
    SkillNotFoundError,
)
from .model import Skill, SkillFile, SkillFileKind, SkillScope, SkillTool
from .parser import parse_skill, parse_skill_md
from .runtime import (
    SKILL_TOOL_PREFIX,
    SKILL_TOOL_SEPARATOR,
    SkillRuntime,
    ToolScriptExecutor,
    make_skill_tool_target,
    parse_skill_tool_target,
)

__all__ = [
    "ActivatedSkill",
    "DEFAULT_SKILL_ROOTS",
    "SKILL_TOOL_PREFIX",
    "SKILL_TOOL_SEPARATOR",
    "ScriptNotFoundError",
    "ScriptPathError",
    "Skill",
    "SkillFile",
    "SkillFileKind",
    "SkillLoader",
    "SkillNotFoundError",
    "SkillRuntime",
    "SkillScope",
    "SkillTool",
    "ToolScriptExecutor",
    "discover_skills",
    "discover_skills_in_root",
    "get_skills_for_workspace",
    "make_skill_tool_target",
    "parse_skill",
    "parse_skill_md",
    "parse_skill_tool_target",
    "resolve_skill_roots",
]
