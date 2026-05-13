"""Data classes describing a parsed Agent Skill."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# Matches a path containing the segment
# ``/workspaces/<W>/synthesis-skills-<W>/...`` where the two ``<W>`` values
# are identical (verified at match time, not by backreference, so we keep
# the regex simple and case-insensitive).
_WORKSPACE_SCOPE_RE = re.compile(
    r"(?:^|/)workspaces/(?P<ws>[^/]+)/synthesis-skills-(?P<inner>[^/]+)(?:/|$)",
    re.IGNORECASE,
)


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


@dataclass(frozen=True)
class SkillScope:
    """Visibility scope of a parsed Skill.

    A skill is either universal (visible from every workspace) or scoped to
    one-or-more specific workspaces. The two states are encoded explicitly:

    * ``universal=True``  → ``workspaces`` is ignored. The skill is visible
                            from any workspace run.
    * ``universal=False`` → ``workspaces`` enumerates the workspace names
                            this skill is visible from. Empty workspaces
                            with ``universal=False`` is treated as
                            "scoped to nothing" (invisible everywhere); the
                            constructors below normalise this away.
    """

    universal: bool = True
    workspaces: Tuple[str, ...] = ()

    # -- Constructors -------------------------------------------------------

    @classmethod
    def universal_scope(cls) -> "SkillScope":
        """Shorthand for the all-workspaces sentinel value."""
        return cls(universal=True, workspaces=())

    @classmethod
    def for_workspaces(cls, names: Tuple[str, ...]) -> "SkillScope":
        """Construct a scope for a non-empty tuple of workspace names.

        Names are deduplicated case-sensitively and ordered by first
        occurrence. An empty tuple collapses to universal (it would
        otherwise mean "visible nowhere" — a degenerate state we never
        want to emit from discovery).
        """
        seen: List[str] = []
        for raw in names:
            if not raw:
                continue
            name = str(raw).strip()
            if not name:
                continue
            if name not in seen:
                seen.append(name)
        if not seen:
            return cls.universal_scope()
        return cls(universal=False, workspaces=tuple(seen))

    @classmethod
    def from_path_convention(cls, path: str) -> "SkillScope":
        """Infer scope from a skill's absolute path.

        Convention: a skill whose path includes the segment
        ``workspaces/<W>/synthesis-skills-<W>/`` (case-insensitive) is
        scoped to workspace ``<W>``. Any other path is universal.

        The inner directory name (``synthesis-skills-<W>``) must end with
        the same workspace token as the enclosing ``workspaces/<W>/``
        directory. Mismatched names (e.g. a stray
        ``synthesis-skills-other`` under ``workspaces/acme-user/``) are
        treated as universal — we won't guess intent.

        Identity-aware override: when ``<W>`` is declared as personal
        in ``~/.synthesis/identity.yaml`` (via the
        :func:`synthesis_engine.identity.get_personal_workspaces` helper),
        the scope collapses to universal. Personal workspaces house the
        operator's own skills that are used across every workspace, so
        the path convention's "workspace-scoped" default does not apply
        to them.
        """
        if not path:
            return cls.universal_scope()
        normalized = path.replace("\\", "/")
        for match in _WORKSPACE_SCOPE_RE.finditer(normalized):
            ws = match.group("ws").lower()
            inner = match.group("inner").lower()
            if ws == inner:
                # Lazy import to avoid a hard dep on the identity module
                # at the top of skills/model.py (keeps imports minimal).
                from ..identity import is_personal_workspace
                if is_personal_workspace(match.group("ws")):
                    return cls.universal_scope()
                return cls.for_workspaces((match.group("ws"),))
        return cls.universal_scope()

    @classmethod
    def from_frontmatter(
        cls,
        value: Any,
        fallback: Optional["SkillScope"] = None,
    ) -> "SkillScope":
        """Normalise a ``scope:`` frontmatter value into a SkillScope.

        Accepted forms:

        * Missing / ``None``  → returns ``fallback`` (or universal).
        * ``"universal"``     → universal scope.
        * ``"workspace-a"``   → scoped to ``workspace-a``.
        * ``[a, b]``          → scoped to ``a`` and ``b``.
        * ``{universal: True}`` → universal.
        * ``{workspaces: [a, b]}`` → scoped to ``a`` and ``b``.
        * ``{workspaces: [a, b], universal: False}`` → same.
        * ``{workspaces: [], universal: True}`` → universal.

        Any other shape (number, malformed mapping, empty string list,
        etc.) is treated as missing and falls back. A scope value that
        explicitly says ``universal: True`` always wins over a
        workspace-suggestive path, which is how authors override path
        convention.
        """
        fb = fallback if fallback is not None else cls.universal_scope()

        if value is None:
            return fb

        # Single string: "universal" or a workspace name.
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return fb
            if token.lower() == "universal":
                return cls.universal_scope()
            return cls.for_workspaces((token,))

        # List of workspace names.
        if isinstance(value, (list, tuple)):
            names = tuple(str(v).strip() for v in value if str(v).strip())
            if not names:
                return fb
            # Special-case the literal ['universal'] list.
            if len(names) == 1 and names[0].lower() == "universal":
                return cls.universal_scope()
            return cls.for_workspaces(names)

        # Mapping: { universal: ..., workspaces: [...] }.
        if isinstance(value, dict):
            universal_flag = value.get("universal")
            workspaces_raw = value.get("workspaces") or ()
            if isinstance(workspaces_raw, str):
                workspaces_raw = (workspaces_raw,)
            workspaces_norm = tuple(
                str(v).strip() for v in workspaces_raw if str(v).strip()
            )
            # Explicit universal=True wins regardless of workspaces.
            if universal_flag is True:
                return cls.universal_scope()
            if universal_flag is False and workspaces_norm:
                return cls.for_workspaces(workspaces_norm)
            # Mapping with only workspaces present and no flag.
            if workspaces_norm:
                return cls.for_workspaces(workspaces_norm)
            # Mapping with universal=False and no workspaces is malformed;
            # honour the explicit override anyway by falling back to fb.
            return fb

        # Anything else: treat as missing.
        return fb

    # -- Queries ------------------------------------------------------------

    def visible_from(self, chain: Tuple[str, ...]) -> bool:
        """Return True when this scope is visible from any workspace in ``chain``.

        Universal scopes are visible from every chain (including the empty
        one). Otherwise we require at least one of the scope's workspaces
        to appear in the chain.
        """
        if self.universal:
            return True
        if not self.workspaces:
            return False
        chain_set = set(chain)
        return any(ws in chain_set for ws in self.workspaces)


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
        scope:          Visibility scope (universal vs. workspace-restricted).
                        Set at parse time from explicit frontmatter when
                        present, else inferred from the skill's path.
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
    scope: SkillScope = field(default_factory=SkillScope.universal_scope)
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
