"""Register Ragbot's demo-mode filters with the substrate.

Imported for its side effects from :mod:`ragbot.__init__`. The substrate
(``synthesis_engine``) exposes a small discovery-filter registry; this
module is where Ragbot — as the runtime — installs the two filters that
implement ``RAGBOT_DEMO=1``.

The filters are dynamic by design: they read :func:`is_demo_mode` at
call time, not at import time. That lets pytest's ``monkeypatch.setenv``
flip demo mode on and off across test cases without requiring a fresh
process or a re-import. The cost is one cheap env-var read per
discovery call, which is negligible.

Architecture note: this module is the SINGLE place where Ragbot
short-circuits substrate discovery. If a future Ragbot feature needs to
intercept discovery, it should either extend these filters or — more
likely — register an additional named scope. Keeping the registration
centralised here means the layer boundary stays auditable: a grep for
``set_discovery_filter`` in ragbot/ should return only this file.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesis_engine.discovery import (
    SCOPE_SKILL_ROOTS,
    SCOPE_WORKSPACES,
    set_discovery_filter,
)

from .demo import (
    DEMO_WORKSPACE_NAME,
    demo_skills_path,
    demo_workspace_path,
    is_demo_mode,
)


def _workspaces_filter() -> Optional[Dict[str, str]]:
    """Return the demo-only workspace index when demo mode is active.

    Returning ``None`` signals "no override; let the substrate use its
    normal full-discovery chain."
    """
    if not is_demo_mode():
        return None
    path = demo_workspace_path()
    if path is None:
        # Demo mode is on but the bundled directory is missing. Return an
        # empty dict (not None) so the substrate still treats this as an
        # override — the screenshot/evaluator backstop must hold even
        # when the demo bundle is broken.
        return {}
    return {DEMO_WORKSPACE_NAME: str(path)}


def _skill_roots_filter() -> Optional[List[str]]:
    """Return the bundled-skill roots when demo mode is active.

    Returning ``None`` signals "no override; let the substrate scan the
    normal skill-root chain."

    Demo mode isolates USER-installed skills (workspace-scoped collections,
    operator's private skill repo, plugin-installed skills) from the
    evaluator's view so the demo shows a known-clean state. The bundled
    starter pack — the universal-scope skills that ship with the substrate
    out of the box — is INCLUDED in demo mode because it is part of "what
    Ragbot v3.4 ships with," not part of the operator's content. Pairing
    the starter pack with the demo's own ``demo/skills/`` directory gives
    evaluators a realistic view of the skill surface a new user sees.
    """
    if not is_demo_mode():
        return None
    # Lazy import keeps the demo-registration module's import surface
    # narrow (ragbot/_demo_registration → synthesis_engine.skills imports
    # would otherwise cycle through ragbot's __init__).
    from synthesis_engine.skills.starter_pack import starter_pack_root

    roots: List[str] = [starter_pack_root()]
    path = demo_skills_path()
    if path is not None:
        roots.append(str(path))
    return roots


set_discovery_filter(SCOPE_WORKSPACES, _workspaces_filter)
set_discovery_filter(SCOPE_SKILL_ROOTS, _skill_roots_filter)
