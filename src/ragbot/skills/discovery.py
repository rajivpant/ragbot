"""Skill directory discovery.

Skills live at conventional locations and inside ai-knowledge repos. This
module walks those locations and returns parsed :class:`Skill` objects.

Discovery sources, in order (later entries override earlier ones on
name collision):

    1. Synthesis-engineering shared install: ``~/.synthesis/skills/``.
    2. Claude Code private skills:           ``~/.claude/skills/``.
    3. Plugin-installed skills:              ``~/.claude/plugins/cache/<vendor>/skills/``.
    4. Per-workspace skills declared via the compile-config (callers pass
       a list of explicit roots).

Within each root we treat any direct subdirectory containing ``SKILL.md``
as a skill. Nested layouts under those subdirectories are inspected by
``parser.parse_skill``.
"""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .model import Skill
from .parser import parse_skill

logger = logging.getLogger(__name__)


DEFAULT_SKILL_ROOTS = (
    str(Path.home() / ".synthesis" / "skills"),
    str(Path.home() / ".claude" / "skills"),
)


# Glob for plugin-installed skills. We resolve at runtime because vendor
# directories vary by installation.
_PLUGIN_SKILL_GLOB = str(Path.home() / ".claude" / "plugins" / "cache" / "*" / "skills")


def resolve_skill_roots(extra: Optional[Iterable[str]] = None) -> List[str]:
    """Return the absolute, existing roots that will be scanned for skills.

    ``extra`` may include user- or workspace-supplied paths from the
    compile-config. Roots are deduplicated while preserving order.
    """

    candidates: List[str] = []
    candidates.extend(DEFAULT_SKILL_ROOTS)
    candidates.extend(glob.glob(_PLUGIN_SKILL_GLOB))
    if extra:
        candidates.extend(os.path.expanduser(p) for p in extra)

    seen: set = set()
    resolved: List[str] = []
    for root in candidates:
        abs_root = os.path.abspath(os.path.expanduser(root))
        if abs_root in seen:
            continue
        seen.add(abs_root)
        if os.path.isdir(abs_root):
            resolved.append(abs_root)
    return resolved


def discover_skills_in_root(root: str) -> List[Skill]:
    """Parse every skill directory directly under ``root``."""

    if not os.path.isdir(root):
        return []
    skills: List[Skill] = []
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if not os.path.isdir(full):
            continue
        # Skip dot-prefixed and clearly-not-a-skill dirs.
        if entry.startswith("."):
            continue
        skill = parse_skill(full)
        if skill is not None:
            skills.append(skill)
    return skills


def discover_skills(
    roots: Optional[Iterable[str]] = None,
    extra: Optional[Iterable[str]] = None,
) -> List[Skill]:
    """Discover skills across the given roots (or defaults).

    When ``roots`` is None, the default chain (``DEFAULT_SKILL_ROOTS`` +
    plugin glob + ``extra``) is used. On name collision later roots win,
    matching the override semantics documented in the module docstring.

    When ``RAGBOT_DEMO=1`` is set and ``roots`` is None, only the
    bundled demo skills directory is scanned. This keeps demo screenshots
    free of any real skill names that happen to be installed on the host.
    """

    # Demo mode short-circuit. Honour explicit ``roots`` (so tests can
    # bypass demo) but otherwise replace the default chain entirely.
    if roots is None:
        from ..demo import is_demo_mode, demo_skills_path

        if is_demo_mode():
            demo_path = demo_skills_path()
            targets = [str(demo_path)] if demo_path is not None else []
        else:
            targets = resolve_skill_roots(extra=extra)
    else:
        targets = [os.path.abspath(os.path.expanduser(r)) for r in roots]

    by_name: Dict[str, Skill] = {}
    for root in targets:
        for skill in discover_skills_in_root(root):
            existing = by_name.get(skill.name)
            if existing is not None:
                logger.debug(
                    "Skill %s overridden: %s → %s",
                    skill.name, existing.path, skill.path,
                )
            by_name[skill.name] = skill

    return sorted(by_name.values(), key=lambda s: s.name)
