"""Data classes describing a parsed Agent Skill."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillFileKind(str, Enum):
    """Categorisation used by the indexer and compiler.

    The kind influences how a file is presented to downstream consumers:

    * ``skill_md``       — the canonical entry point (one per skill).
    * ``reference``      — markdown under ``references/`` or otherwise nested
                           markdown that documents the skill in detail.
    * ``script``         — executable file (Python, shell, JS, etc.).
    * ``other``          — any other text artifact (configs, sample data).
    """

    SKILL_MD = "skill_md"
    REFERENCE = "reference"
    SCRIPT = "script"
    OTHER = "other"


@dataclass
class SkillFile:
    """A single file inside a skill directory."""

    relative_path: str   # path relative to the skill root, POSIX style
    absolute_path: str
    kind: SkillFileKind
    content: str = ""    # populated for indexable text files; empty for binaries
    is_text: bool = True


@dataclass
class Skill:
    """A parsed Agent Skill.

    Attributes:
        name:           Skill identifier (directory name and frontmatter name
                        if present; the latter wins when they disagree).
        path:           Absolute path to the skill root directory.
        skill_md_path:  Absolute path to the SKILL.md file.
        description:    From SKILL.md frontmatter (or empty string if missing).
        body:           SKILL.md body, with the YAML frontmatter stripped.
        frontmatter:    Full parsed frontmatter dict (description, license,
                        metadata, depends_on, etc.).
        files:          All files in the skill tree (SKILL.md, references,
                        scripts, others). The list always includes the
                        SKILL.md itself first.
    """

    name: str
    path: str
    skill_md_path: str
    description: str = ""
    body: str = ""
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    files: List[SkillFile] = field(default_factory=list)

    @property
    def references(self) -> List[SkillFile]:
        return [f for f in self.files if f.kind is SkillFileKind.REFERENCE]

    @property
    def scripts(self) -> List[SkillFile]:
        return [f for f in self.files if f.kind is SkillFileKind.SCRIPT]

    @property
    def other_files(self) -> List[SkillFile]:
        return [f for f in self.files if f.kind is SkillFileKind.OTHER]

    @property
    def triggers(self) -> List[str]:
        """Convenience accessor — Anthropic's convention is to put trigger
        phrases in either the description or a dedicated 'triggers' / 'when'
        field. Surface whatever is present, normalised to a list."""

        trig = self.frontmatter.get("triggers") or self.frontmatter.get("when")
        if not trig:
            return []
        if isinstance(trig, list):
            return [str(t) for t in trig]
        return [str(trig)]

    @property
    def version(self) -> Optional[str]:
        meta = self.frontmatter.get("metadata") or {}
        if isinstance(meta, dict):
            v = meta.get("version")
            if v is not None:
                return str(v)
        # Some older skills store version at the top level.
        v = self.frontmatter.get("version")
        return str(v) if v is not None else None

    @property
    def source_repo(self) -> Optional[str]:
        meta = self.frontmatter.get("metadata") or {}
        if isinstance(meta, dict):
            v = meta.get("source_repo")
            if v:
                return str(v)
        return None

    def summary_dict(self) -> Dict[str, Any]:
        """Compact dict used by ``ragbot skills list``."""

        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "description": self.description,
            "file_count": len(self.files),
            "reference_count": len(self.references),
            "script_count": len(self.scripts),
        }
