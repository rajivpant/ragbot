"""Skill directory discovery.

Skills live at conventional locations and inside ai-knowledge repos. This
module walks those locations and returns parsed :class:`Skill` objects.

Discovery sources, in order (later entries override earlier ones on
name collision):

    1. Synthesis-engineering shared install:  ``~/.synthesis/skills/``.
    2. Claude Code private skills:            ``~/.claude/skills/``.
    3. Plugin-installed skills:               ``~/.claude/plugins/cache/<vendor>/skills/``.
    4. Per-personal-workspace open-source checkout, one per workspace
       declared in ``~/.synthesis/identity.yaml`` under
       ``personal_workspaces``:                ``~/workspaces/<personal>/synthesis-skills/``.
    5. Per-workspace skill collections (glob): ``~/workspaces/<W>/synthesis-skills-<W>/``.
       Scope is workspace-derived; when ``<W>`` is in ``personal_workspaces``
       the identity-aware path convention collapses the scope to universal.
    6. Caller-supplied extra roots (compile-config, tests, ...).

Within each root we treat any direct subdirectory containing ``SKILL.md``
as a skill. Nested layouts under those subdirectories are inspected by
``parser.parse_skill``.

Workspace-scoped discovery
--------------------------

Skills carry a :class:`SkillScope`. The default chain returns every skill
regardless of scope (used by ``ragbot skills list``). Runtimes wanting a
workspace-filtered view call :func:`get_skills_for_workspace`, which
applies the inheritance chain from ``my-projects.yaml`` so a workspace
inherits its parents' visible skills.
"""

from __future__ import annotations

import glob
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..discovery import SCOPE_SKILL_ROOTS, apply_discovery_filter
from ..inheritance import (
    find_inheritance_config,
    get_inheritance_chain,
    load_inheritance_config,
)
from .model import Skill, SkillScope
from .parser import parse_skill

logger = logging.getLogger(__name__)


def _default_skill_roots() -> Tuple[str, ...]:
    """Compute the default skill-root chain against the current ``Path.home()``.

    Materialised as a function (rather than a module-level constant) so
    that tests can monkeypatch ``Path.home`` and still get the expected
    layout. The exported :data:`DEFAULT_SKILL_ROOTS` constant remains
    available for callers that want a frozen list at import time.

    The chain consists of:

    1. Synthesis-engineering shared install      ``~/.synthesis/skills/``
    2. Claude Code private skills                ``~/.claude/skills/``
    3. Per-personal-workspace open-source clones derived from
       ``~/.synthesis/identity.yaml`` (one entry per workspace declared
       under ``personal_workspaces``)

    Per-workspace skill collections at
    ``~/workspaces/<W>/synthesis-skills-<W>/`` are picked up by the
    workspace glob (see :func:`_expand_workspace_globs`), not by this
    chain; the identity-aware path-convention rule in
    :class:`SkillScope.from_path_convention` decides whether each one is
    universal (for personal workspaces) or workspace-scoped.
    """
    from ..identity import get_personal_workspaces  # lazy: avoid import cycle

    home = Path.home()
    chain: List[str] = [
        str(home / ".synthesis" / "skills"),
        str(home / ".claude" / "skills"),
    ]
    for personal in get_personal_workspaces():
        # The open-source synthesis-skills repo cloned under the
        # operator's workspace (no ``-<workspace>`` suffix) holds
        # universally-scoped skills.
        chain.append(str(home / "workspaces" / personal / "synthesis-skills"))
    return tuple(chain)


DEFAULT_SKILL_ROOTS = _default_skill_roots()


# Glob for plugin-installed skills. We resolve at runtime because vendor
# directories vary by installation.
def _plugin_skill_glob() -> str:
    return str(Path.home() / ".claude" / "plugins" / "cache" / "*" / "skills")


# Glob for per-workspace skill collections. The directory-name pattern is
# significant: a skills root under ``~/workspaces/<W>/synthesis-skills-<W>/``
# is taken as scoped to workspace ``<W>``. Matched at runtime via glob.
def _workspace_skill_glob() -> str:
    return str(Path.home() / "workspaces" / "*" / "synthesis-skills-*")


_PLUGIN_SKILL_GLOB = _plugin_skill_glob()


def _expand_workspace_globs() -> List[str]:
    """Expand the per-workspace skill-glob and filter to matching pairs.

    The glob ``~/workspaces/*/synthesis-skills-*/`` would otherwise admit
    mismatched pairs (e.g. ``~/workspaces/<W>/synthesis-skills-other``).
    The directory-name pattern is significant for scope inference, so we
    only emit roots whose inner directory ends with the workspace token.
    A symmetric path like ``~/workspaces/<W>/synthesis-skills-<W>``
    survives the filter; everything else is dropped.
    """
    home = Path.home()
    base = home / "workspaces"
    if not base.is_dir():
        return []
    matches: List[str] = []
    for entry in glob.glob(str(home / "workspaces" / "*" / "synthesis-skills-*")):
        path = Path(entry)
        if not path.is_dir():
            continue
        workspace_name = path.parent.name
        inner = path.name
        expected = f"synthesis-skills-{workspace_name}"
        if inner.lower() == expected.lower():
            matches.append(str(path))
    return matches


def resolve_skill_roots(extra: Optional[Iterable[str]] = None) -> List[str]:
    """Return the absolute, existing roots that will be scanned for skills.

    ``extra`` may include user- or workspace-supplied paths from the
    compile-config. Roots are deduplicated while preserving order.

    The chain is computed against the live ``Path.home()`` on each call so
    tests can monkeypatch the home directory.
    """

    candidates: List[str] = []
    # Recompute defaults each call so monkeypatched homes are honoured.
    candidates.extend(_default_skill_roots())
    candidates.extend(glob.glob(_plugin_skill_glob()))
    candidates.extend(_expand_workspace_globs())
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

    Runtimes can override the default chain by registering a filter for
    the ``"skill_roots"`` scope via
    :func:`synthesis_engine.discovery.set_discovery_filter`. When such a
    filter is active and returns a non-None list, that list replaces the
    default chain. ``roots`` (explicit caller argument) always wins over
    any registered filter; tests use this to bypass runtime overrides.
    """

    if roots is not None:
        targets = [os.path.abspath(os.path.expanduser(r)) for r in roots]
    else:
        # Default chain, possibly overridden by a runtime-registered filter.
        default_targets = resolve_skill_roots(extra=extra)
        targets = apply_discovery_filter(SCOPE_SKILL_ROOTS, default_targets)

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


def _resolve_personal_repo_path() -> Optional[str]:
    """Locate the personal AI-Knowledge repo containing ``my-projects.yaml``.

    Convention is ``~/workspaces/<personal>/ai-knowledge-<personal>/``. The
    personal workspace name varies by operator; we glob and return the
    first match whose ``my-projects.yaml`` is present.

    Returns the absolute repo path on success, ``None`` when no candidate
    is found. The caller treats ``None`` as "no inheritance config; fall
    back to a single-workspace chain."
    """
    home = Path.home()
    workspaces_root = home / "workspaces"
    if not workspaces_root.is_dir():
        return None
    for entry in sorted(workspaces_root.iterdir()):
        if not entry.is_dir():
            continue
        candidate = entry / f"ai-knowledge-{entry.name}"
        if candidate.is_dir() and find_inheritance_config(str(candidate)):
            return str(candidate)
    return None


def _resolve_inheritance_chain(
    workspace_name: str,
    inheritance_config: Optional[Dict[str, Any]],
) -> Tuple[str, ...]:
    """Build the inheritance chain for ``workspace_name``.

    When ``inheritance_config`` is provided, it is used directly. When
    ``None``, we try to locate ``my-projects.yaml`` in the conventional
    personal-repo path. If neither yields a chain, we fall back to the
    single-workspace chain ``(workspace_name,)`` so the filter still
    works in tests and on systems without my-projects.yaml.

    The returned chain always includes ``workspace_name`` itself.
    """
    if inheritance_config is None:
        personal_repo = _resolve_personal_repo_path()
        if personal_repo is not None:
            config_path = find_inheritance_config(personal_repo)
            if config_path:
                try:
                    inheritance_config = load_inheritance_config(config_path)
                except Exception as exc:  # pragma: no cover - rare, logged
                    logger.warning(
                        "Could not load inheritance config at %s: %s",
                        config_path, exc,
                    )
                    inheritance_config = None

    if not inheritance_config:
        return (workspace_name,)

    try:
        chain = get_inheritance_chain(workspace_name, inheritance_config)
    except ValueError as exc:
        # Circular dependency or other config error. Surface a warning and
        # fall back to a single-workspace chain so the caller still gets
        # something useful instead of a crash.
        logger.warning(
            "Inheritance chain for %s could not be resolved: %s",
            workspace_name, exc,
        )
        return (workspace_name,)

    if workspace_name not in chain:
        # Workspace not declared in my-projects.yaml — include it anyway so
        # workspace-scoped skills under that name remain visible.
        chain = list(chain) + [workspace_name]

    return tuple(chain)


def get_skills_for_workspace(
    workspace_name: str,
    *,
    inheritance_config: Optional[Dict[str, Any]] = None,
    extra_roots: Optional[Iterable[str]] = None,
) -> List[Skill]:
    """Return the skills visible from a given workspace.

    A skill is visible when:

    * its scope is universal (``skill.scope.universal == True``); or
    * its scope's workspace list intersects the workspace's inheritance
      chain (the workspace itself plus every ancestor declared in
      ``my-projects.yaml``).

    The function does not re-scan the filesystem beyond what
    :func:`discover_skills` already does — scope tagging happens at parse
    time, so filtering is a pure in-memory pass.

    Args:
        workspace_name: The workspace to filter for. Required.
        inheritance_config: Optional pre-loaded my-projects.yaml mapping.
            When omitted, the function tries to locate one in the
            conventional personal-repo path and falls back to a
            single-workspace chain if none is found.
        extra_roots: Additional skill roots passed through to
            :func:`discover_skills`.

    Returns:
        A list of :class:`Skill` objects sorted by name. Name collisions
        follow the same later-wins semantics as :func:`discover_skills`.
    """
    chain = _resolve_inheritance_chain(workspace_name, inheritance_config)
    all_skills = discover_skills(extra=extra_roots)
    return [s for s in all_skills if s.scope.visible_from(chain)]
