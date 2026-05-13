"""Three-tier progressive-disclosure skill loader.

This module is the bridge between the parsed :class:`Skill` objects
produced by ``synthesis_engine.skills.parser`` and the agent loop's
execution layer. The loader implements Anthropic's progressive-disclosure
pattern so token budgets stay small:

    Tier 1 — system-prompt fragment. One line per active skill: name and
             description. ~20 tokens per skill. Loaded once per session.

    Tier 2 — full SKILL.md body. Loaded only when the agent decides to
             activate a skill. The body, declared tools, and any
             pre-loaded context blocks come along.

    Tier 3 — bundled scripts. Loaded only when the agent calls a
             specific tool whose script needs to run. Bytes-only; the
             caller decides how to execute them.

The loader caches Tier-2 activations via an LRU keyed by skill name. The
Tier-1 render is cheap and rebuilt on demand; Tier-3 loads are not
cached because scripts can be large and one tool-call per session is the
common case.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from .model import Skill, SkillFile, SkillFileKind, SkillTool

logger = logging.getLogger(__name__)


# Default Tier-2 cache size. The agent loop activates O(skills) per
# session, not O(turns), so even a small LRU absorbs the realistic load.
_TIER2_CACHE_DEFAULT_SIZE = 64


# ---------------------------------------------------------------------------
# Activated-skill dataclass
# ---------------------------------------------------------------------------


@dataclass
class ActivatedSkill:
    """The Tier-2 view of a skill once the agent has chosen to activate it.

    Attributes:
        skill:             The original parsed Skill object — kept as a
                           back-reference so callers can reach the
                           file list, frontmatter, etc. without a second
                           lookup.
        body_markdown:     The SKILL.md body with frontmatter stripped.
                           Wired into the agent's system prompt as the
                           skill's instructions.
        tools:             The list of :class:`SkillTool` the skill
                           declared. Empty when the skill has no tools.
        pre_loaded_context: Free-form context blocks the skill author
                            declared under ``pre_loaded_context:`` in
                            frontmatter. The runtime appends these to
                            the agent's retrieved-context list when the
                            skill activates so the LLM sees them on the
                            same plane as RAG hits. Each entry has at
                            least a ``"text"`` key; ``"source"`` and
                            ``"provenance"`` are optional.
    """

    skill: Skill
    body_markdown: str = ""
    tools: List[SkillTool] = field(default_factory=list)
    pre_loaded_context: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SkillNotFoundError(KeyError):
    """Raised when a skill name is not in the loader's active set."""


class ScriptNotFoundError(FileNotFoundError):
    """Raised when a Tier-3 script load resolves to a missing file."""


class ScriptPathError(ValueError):
    """Raised when a script-relative path attempts to escape the skill root."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class SkillLoader:
    """Three-tier loader over a set of active :class:`Skill` objects.

    The loader is a lightweight value-object built once per session.
    Callers pass the filtered list of skills they want available — the
    standard path is::

        skills = get_skills_for_workspace("acme-news")
        loader = SkillLoader(skills)

    On a fresh session the agent embeds ``loader.tier_1_system_prompt()``
    in its system message. When the agent decides to engage a skill it
    calls ``loader.activate(name)`` to pull the full body. When the
    agent invokes one of that skill's tools — and the tool declares a
    bundled script — the runtime calls ``loader.load_script(name, path)``
    to read the bytes.
    """

    def __init__(
        self,
        active_skills: List[Skill],
        *,
        cache_size: int = _TIER2_CACHE_DEFAULT_SIZE,
    ) -> None:
        if not isinstance(active_skills, list):
            active_skills = list(active_skills)
        self._skills: Dict[str, Skill] = {}
        for skill in active_skills:
            # Later entries overwrite earlier ones, matching the
            # discovery layer's name-collision policy.
            self._skills[skill.name] = skill

        # Tier-2 activation cache. ``functools.lru_cache`` requires a
        # hashable arg; we wrap a bound method so the LRU is per-instance.
        self._activate_cached = lru_cache(maxsize=cache_size)(
            self._activate_uncached
        )

    # ----- accessors --------------------------------------------------------

    @property
    def active_skills(self) -> List[Skill]:
        """Return the active skills in deterministic (name-sorted) order."""
        return sorted(self._skills.values(), key=lambda s: s.name)

    def has_skill(self, name: str) -> bool:
        return name in self._skills

    def get_skill(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise SkillNotFoundError(
                f"Skill {name!r} is not in the loader's active set. "
                f"Active skills: {sorted(self._skills)}"
            ) from exc

    # ----- Tier 1 -----------------------------------------------------------

    def tier_1_system_prompt(self) -> str:
        """Render the Tier-1 system-prompt fragment.

        One line per active skill: ``- <name>: <description>``. The
        description is rendered as one line — multi-line descriptions
        are joined on spaces so the prompt stays tabular. Skills
        without a description still emit their name so the agent can
        choose to activate and read the body.

        Returns an empty string when no skills are active so the caller
        can concatenate unconditionally.
        """

        if not self._skills:
            return ""
        lines: List[str] = ["Available skills:"]
        for skill in self.active_skills:
            description = " ".join(
                (skill.description or "").split()
            ) or "(no description)"
            lines.append(f"- {skill.name}: {description}")
        return "\n".join(lines)

    # ----- Tier 2 -----------------------------------------------------------

    def activate(self, skill_name: str) -> ActivatedSkill:
        """Tier-2 load: return the full activated view of one skill.

        Cached per loader instance. The cache key is the skill name; a
        skill whose underlying file changes between calls in the same
        session is intentionally not picked up — sessions are short and
        re-parsing on every activation would defeat the point of the
        three-tier design. Tests that need to bust the cache call
        ``loader.invalidate_cache()``.
        """

        if skill_name not in self._skills:
            raise SkillNotFoundError(
                f"Cannot activate unknown skill {skill_name!r}. "
                f"Active skills: {sorted(self._skills)}"
            )
        return self._activate_cached(skill_name)

    def _activate_uncached(self, skill_name: str) -> ActivatedSkill:
        skill = self._skills[skill_name]
        # The Skill parser already stripped frontmatter; the body is the
        # canonical Tier-2 payload.
        body = skill.body or _read_skill_md_body(skill)
        pre_loaded_context = _normalise_pre_loaded_context(
            skill.frontmatter.get("pre_loaded_context")
        )
        return ActivatedSkill(
            skill=skill,
            body_markdown=body,
            tools=list(skill.tools),
            pre_loaded_context=pre_loaded_context,
        )

    def invalidate_cache(self) -> None:
        """Drop every cached Tier-2 activation. Mostly a test hook."""
        self._activate_cached.cache_clear()

    def cache_info(self) -> Any:
        """Return the underlying LRU's cache info (hits, misses, ...)."""
        return self._activate_cached.cache_info()

    # ----- Tier 3 -----------------------------------------------------------

    def load_script(self, skill_name: str, script_relative_path: str) -> bytes:
        """Tier-3 load: return raw bytes of a bundled script.

        The relative path is normalised against the skill root; any
        attempt to escape the root (``../`` traversal, absolute path,
        non-POSIX separators that resolve outside the directory) raises
        :class:`ScriptPathError`. Missing files raise
        :class:`ScriptNotFoundError`. The byte payload is returned
        as-is so the caller decides whether to decode, exec in a
        sandbox, or hand to a subprocess.
        """

        skill = self.get_skill(skill_name)
        absolute = _resolve_script_path(skill.path, script_relative_path)

        if not os.path.isfile(absolute):
            raise ScriptNotFoundError(
                f"Script {script_relative_path!r} not found under skill "
                f"{skill_name!r} at {skill.path!r}."
            )
        with open(absolute, "rb") as f:
            return f.read()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_script_path(skill_root: str, relative: str) -> str:
    """Resolve a script-relative path under ``skill_root`` safely.

    Rejects absolute paths, ``..``-only paths, and any path that
    normalises outside the skill root. Mixed Windows separators are
    normalised to POSIX before the safety check.
    """

    if not relative:
        raise ScriptPathError(
            "Script relative path must be a non-empty string."
        )
    normalised = relative.replace("\\", "/").strip()
    if normalised.startswith("/"):
        raise ScriptPathError(
            f"Script path {relative!r} must be relative to the skill root."
        )
    skill_root_abs = os.path.abspath(skill_root)
    candidate = os.path.abspath(os.path.join(skill_root_abs, normalised))
    # ``commonpath`` raises on mixed drives; in our world both paths share
    # the same root so this is fine. The startswith check uses a trailing
    # separator so ``/skills/foo`` does not accidentally match
    # ``/skills/foobar``.
    sep = os.sep
    if not (
        candidate == skill_root_abs
        or candidate.startswith(skill_root_abs + sep)
    ):
        raise ScriptPathError(
            f"Script path {relative!r} escapes the skill root "
            f"{skill_root!r}."
        )
    return candidate


def _read_skill_md_body(skill: Skill) -> str:
    """Re-read the SKILL.md body when the parsed Skill has none cached.

    The standard parser populates ``Skill.body`` at parse time, so this
    helper exists only as a defensive backstop for callers that
    constructed a Skill object directly without going through
    ``parser.parse_skill``.
    """

    skill_md: Optional[SkillFile] = None
    for sf in skill.files:
        if sf.kind is SkillFileKind.SKILL_MD:
            skill_md = sf
            break
    if skill_md is None or not skill_md.content:
        return ""
    # Strip frontmatter the same way the parser does. We do not import
    # the parser's private helper to keep this module's dependency
    # surface minimal; the duplication is small and well-bounded.
    text = skill_md.content
    if text.startswith("---"):
        rest = text[3:]
        end = rest.find("\n---")
        if end != -1:
            text = rest[end + len("\n---"):]
            if text.startswith("\n"):
                text = text[1:]
    return text.strip()


def _normalise_pre_loaded_context(value: Any) -> List[Dict[str, Any]]:
    """Coerce a ``pre_loaded_context:`` frontmatter value into a list of dicts.

    Accepts:

    * A list of strings (each becomes ``{"text": str, "source": "skill"}``)
    * A list of dicts (each must have a ``"text"`` key; other keys pass
      through).
    * Anything else is dropped with a warning.
    """

    if not value:
        return []
    if not isinstance(value, list):
        logger.warning(
            "SKILL.md 'pre_loaded_context' must be a list; got %r.",
            type(value),
        )
        return []
    out: List[Dict[str, Any]] = []
    for idx, entry in enumerate(value):
        if isinstance(entry, str):
            out.append({"text": entry, "source": "skill"})
            continue
        if isinstance(entry, dict):
            text = entry.get("text")
            if not text:
                logger.warning(
                    "SKILL.md pre_loaded_context[%d] missing 'text'; "
                    "skipping.",
                    idx,
                )
                continue
            normalised: Dict[str, Any] = {"text": str(text)}
            if "source" in entry:
                normalised["source"] = str(entry["source"])
            else:
                normalised["source"] = "skill"
            if "provenance" in entry and isinstance(
                entry["provenance"], dict
            ):
                normalised["provenance"] = dict(entry["provenance"])
            out.append(normalised)
            continue
        logger.warning(
            "SKILL.md pre_loaded_context[%d] must be a string or mapping; "
            "skipping.",
            idx,
        )
    return out


__all__ = [
    "ActivatedSkill",
    "ScriptNotFoundError",
    "ScriptPathError",
    "SkillLoader",
    "SkillNotFoundError",
]
