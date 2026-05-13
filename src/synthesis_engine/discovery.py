"""Pluggable discovery filters for synthesis-engine substrate.

The substrate's discovery paths (workspaces, skills, and any future kind)
default to scanning every conventional source on the host. Some runtimes
need to override that — for example, Ragbot's demo mode must restrict
discovery to a bundled, sanitized workspace so screenshots never leak
real names. Earlier substrate code reached up into ``ragbot.demo`` to do
this short-circuit; that was a layer violation and is gone.

This module provides a small registration API the runtime calls at
import time. The substrate consults it without ever importing the
runtime. The default — no filter registered — preserves the substrate's
normal full-discovery behavior.

Public API
----------
``set_discovery_filter(scope, filter_fn)``
    Register a filter for a named discovery scope. ``filter_fn`` is a
    zero-argument callable returning the override result for that scope.
    Returning ``None`` means "no override; use the default discovery
    result." Re-registering the same scope replaces the prior filter.

``clear_discovery_filter(scope)``
    Remove a registered filter. Useful in tests.

``get_active_filter(scope)``
    Inspect the currently registered filter for a scope. Returns the
    callable or ``None``. Intended for debugging and tests.

``apply_discovery_filter(scope, default)``
    Substrate-side helper. Calls the registered filter for ``scope`` (if
    any) and returns its result; otherwise returns ``default``. When the
    filter returns ``None``, ``default`` is returned. This is the single
    consultation point — discovery functions in ``workspaces`` and
    ``skills.discovery`` use it.

Conventional scope names
------------------------
``"workspaces"``
    The result type matches ``resolve_repo_index``: ``Dict[str, str]``
    mapping workspace_name → absolute repo path.

``"skill_roots"``
    The result type matches ``resolve_skill_roots``: ``List[str]`` of
    absolute skill-root paths to scan.

Runtimes are free to add their own scope keys for their own filter
points. Scope keys are namespaced by convention — keep them stable.

Concurrency
-----------
Registration is intended to happen once at import time. The registry is
a simple dict guarded by a lock so concurrent reads during discovery and
the (rare) write at import are safe.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

# Filter callable: takes no arguments, returns either an override value
# or None (meaning "no override; use the default"). The return type is
# scope-specific; the substrate caller knows what shape to expect.
DiscoveryFilter = Callable[[], Any]

_filters: Dict[str, DiscoveryFilter] = {}
_lock = threading.Lock()


def set_discovery_filter(scope: str, filter_fn: DiscoveryFilter) -> None:
    """Register a filter for a named discovery scope.

    The filter is a zero-argument callable returning the override value
    for the scope, or ``None`` to fall back to the substrate's default.
    Re-registering the same scope replaces the prior filter.
    """
    if not callable(filter_fn):
        raise TypeError(
            f"filter_fn for scope {scope!r} must be callable; got {type(filter_fn).__name__}"
        )
    with _lock:
        _filters[scope] = filter_fn


def clear_discovery_filter(scope: str) -> None:
    """Remove a registered filter for ``scope``. No-op if none is registered."""
    with _lock:
        _filters.pop(scope, None)


def get_active_filter(scope: str) -> Optional[DiscoveryFilter]:
    """Return the registered filter callable for ``scope``, or None."""
    with _lock:
        return _filters.get(scope)


def apply_discovery_filter(scope: str, default: Any) -> Any:
    """Apply the registered filter for ``scope``; return ``default`` if none.

    This is the substrate-side consultation point. The discovery
    functions call this with the result they would have returned and the
    scope key they belong to. When a filter is registered and it returns
    a non-None value, that value is returned to the caller; otherwise
    ``default`` is returned untouched.
    """
    with _lock:
        filter_fn = _filters.get(scope)
    if filter_fn is None:
        return default
    result = filter_fn()
    if result is None:
        return default
    return result


# Conventional scope names. Defined as module-level constants so callers
# don't repeat string literals and typos surface as AttributeError.
SCOPE_WORKSPACES = "workspaces"
SCOPE_SKILL_ROOTS = "skill_roots"
