"""Synthesis-engineering identity configuration.

The substrate needs a small amount of identity-aware data — specifically,
the list of workspace names that are "the operator's own" versus
"workspaces shared with others." A personal workspace's `synthesis-skills-<W>/`
directory contains skills the operator uses across every workspace, so
those skills should be universal in scope. A non-personal workspace's
`synthesis-skills-<W>/` directory contains skills shared with collaborators
on that workspace, so those skills should be scoped to that workspace.

This module reads identity from `~/.synthesis/identity.yaml`:

```yaml
# ~/.synthesis/identity.yaml
personal_workspaces:
  - acme-user          # the operator's own identity workspace name(s)
```

The file is optional. When missing, the substrate behaves as if no
personal workspaces are declared — every `synthesis-skills-<W>/`
directory is treated as workspace-scoped per the path convention.

The config is read on demand (no module-level cache) so changes take
effect on the next discovery pass. For high-frequency callers, wrap
with `functools.lru_cache` on a millisecond-bucket if needed.

Path override: callers may pass an explicit path or set the
`SYNTHESIS_IDENTITY_CONFIG` environment variable to point at a
different file. Test suites rely on this to avoid touching the
operator's real config.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a hard dep
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


DEFAULT_IDENTITY_PATH = Path.home() / ".synthesis" / "identity.yaml"


def _resolve_path(explicit: Optional[str]) -> Path:
    """Return the identity-config path, honoring env override + explicit arg."""
    if explicit:
        return Path(os.path.expanduser(explicit))
    env_override = os.environ.get("SYNTHESIS_IDENTITY_CONFIG")
    if env_override:
        return Path(os.path.expanduser(env_override))
    return DEFAULT_IDENTITY_PATH


def get_personal_workspaces(config_path: Optional[str] = None) -> List[str]:
    """Return the list of workspace names declared as the operator's own.

    Parameters
    ----------
    config_path:
        Optional explicit path to an identity YAML file. When omitted,
        consults ``$SYNTHESIS_IDENTITY_CONFIG`` then falls back to
        ``~/.synthesis/identity.yaml``.

    Returns
    -------
    A list of workspace name strings. Empty list when the config is
    missing, malformed, lacks the field, or PyYAML is unavailable.
    Whitespace-only entries are dropped; duplicates are removed in
    first-occurrence order.
    """
    path = _resolve_path(config_path)
    if not path.is_file():
        return []
    if yaml is None:  # pragma: no cover - PyYAML is in requirements
        return []
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError) as exc:
        logger.warning(
            "Failed to read identity config at %s: %s",
            path, exc,
        )
        return []

    if not isinstance(data, dict):
        return []
    raw = data.get("personal_workspaces") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []

    seen: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.append(name)
    return seen


def is_personal_workspace(
    workspace_name: str,
    config_path: Optional[str] = None,
) -> bool:
    """Return True if ``workspace_name`` is declared as personal."""
    if not workspace_name:
        return False
    return workspace_name in get_personal_workspaces(config_path=config_path)


__all__ = [
    "DEFAULT_IDENTITY_PATH",
    "get_personal_workspaces",
    "is_personal_workspace",
]
