"""Permission gate registry for the agent's tool router.

Every tool dispatch passes through :func:`check_permission` before it
runs. The registry holds per-tool gate functions; tools without an
explicit gate fall through to a pattern-based default that auto-allows
read-only operations and denies state-changing operations until they are
explicitly registered.

Design notes:

* Permission decisions are returned as a :class:`PermissionResult` so
  the caller can distinguish "deny — explain to the user" from "deny —
  prompt the user for confirmation". The agent loop renders the former
  into the step error; the latter is a hook the loop currently surfaces
  but does not block on (Round 4b will wire interactive confirmation).

* The default rule set is intentionally conservative. Anything that
  looks like a write, shell, or HTTP-POST operation is denied with a
  message asking the operator to register an explicit gate. The same
  applies to unknown tool names with no obvious read-only signal.

* Multiple gates can be registered for one tool; they are evaluated in
  registration order and the first non-ALLOW result wins. This lets
  callers stack a "redact secrets" gate in front of a "is this user
  allowed" gate without coupling them.
"""

from __future__ import annotations

import fnmatch
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolCallContext:
    """The data a gate sees when deciding allow/deny.

    Carries the tool name, the proposed argument dict, an optional
    server id (for MCP-style routing), the originating task id, and a
    free-form metadata bag for higher-level callers (workspace, user,
    session, etc.).
    """

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    server_id: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionResult:
    """A gate's verdict on one tool call.

    Attributes:
        allowed: True iff the call may proceed.
        reason: Human-readable explanation. Required when ``allowed`` is
            False; optional but recommended when True (e.g., for audit).
        requires_user_confirmation: True iff the gate wants a user to
            confirm before the call runs. When True, ``allowed`` is
            False — the caller treats this as a soft deny that can be
            overridden by an out-of-band confirmation step.
    """

    allowed: bool
    reason: str = ""
    requires_user_confirmation: bool = False

    # ------- factories -----------------------------------------------------

    @classmethod
    def allow(cls, reason: str = "") -> "PermissionResult":
        return cls(allowed=True, reason=reason)

    @classmethod
    def deny(cls, reason: str) -> "PermissionResult":
        return cls(allowed=False, reason=reason)

    @classmethod
    def prompt(cls, reason: str) -> "PermissionResult":
        return cls(
            allowed=False,
            reason=reason,
            requires_user_confirmation=True,
        )


# ---------------------------------------------------------------------------
# Gate signature
# ---------------------------------------------------------------------------


PermissionGate = Callable[[ToolCallContext], PermissionResult]


# ---------------------------------------------------------------------------
# Default patterns
# ---------------------------------------------------------------------------


# Tool-name globs that auto-ALLOW. Order is significant only for clarity;
# any match grants permission. These patterns are matched against the
# bare tool name (without server prefix) and the qualified
# ``server::tool`` form.
_READ_ONLY_PATTERNS: List[str] = [
    "*.read*",
    "*.list*",
    "*.get*",
    "*.find*",
    "*.search*",
    "*.describe*",
    "*.info*",
    "*.head*",
    "*.stat*",
    "*.peek*",
    "*.inspect*",
    "read_*",
    "list_*",
    "get_*",
    "find_*",
    "search_*",
    "describe_*",
    "info_*",
    "head_*",
    "stat_*",
    "peek_*",
    "inspect_*",
]


# Tool-name globs that auto-DENY without an explicit gate. These cover
# obvious state-mutators; everything else falls through to the
# "unknown — register an explicit gate" branch.
_WRITE_PATTERNS: List[str] = [
    "*.write*",
    "*.create*",
    "*.update*",
    "*.delete*",
    "*.remove*",
    "*.rm*",
    "*.put*",
    "*.post*",
    "*.exec*",
    "*.run_shell*",
    "*.run_command*",
    "*.shell*",
    "*.unlink*",
    "write_*",
    "create_*",
    "update_*",
    "delete_*",
    "remove_*",
    "rm_*",
    "put_*",
    "post_*",
    "exec_*",
    "run_shell*",
    "run_command*",
    "shell_*",
    "unlink_*",
]


def _matches_any(name: str, patterns: List[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatchcase(name, pattern):
            return True
    return False


def default_gate(context: ToolCallContext) -> PermissionResult:
    """The default fallthrough gate.

    Read-only patterns auto-ALLOW. Write/shell/HTTP-POST patterns
    auto-DENY with a message asking the operator to register an
    explicit gate. Unknown tools also DENY by default — fail-closed.
    """

    name = context.tool_name
    qualified = (
        f"{context.server_id}::{name}" if context.server_id else name
    )

    # Read-only patterns win over write patterns; a "get_write_status"
    # tool stays allowed because the verb is GET.
    if _matches_any(name, _READ_ONLY_PATTERNS) or _matches_any(
        qualified, _READ_ONLY_PATTERNS
    ):
        return PermissionResult.allow(
            "Read-only operation matched the default allowlist pattern."
        )

    if _matches_any(name, _WRITE_PATTERNS) or _matches_any(
        qualified, _WRITE_PATTERNS
    ):
        return PermissionResult.deny(
            f"Tool {qualified!r} matches a state-changing pattern; "
            "register an explicit permission gate to allow it."
        )

    return PermissionResult.deny(
        f"Tool {qualified!r} has no permission gate registered; "
        "fail-closed default applies. Call register_permission() with "
        "an explicit gate to enable it."
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class PermissionRegistry:
    """Per-process registry of permission gates.

    The registry is thread-safe (a single lock guards register/unregister
    and the lookup copy). Gates are stored per tool name; the same
    tool may have multiple gates which evaluate in registration order
    until one returns a non-ALLOW verdict (or all return ALLOW).
    """

    def __init__(self) -> None:
        self._gates: Dict[str, List[PermissionGate]] = {}
        self._lock = threading.RLock()

    # ----- registration -----------------------------------------------------

    def register(self, tool_name: str, gate: PermissionGate) -> None:
        """Append a gate for ``tool_name``.

        ``tool_name`` may be a literal name (e.g., ``"fs.read_file"``)
        or a glob with ``*`` (e.g., ``"fs.*"``). Glob matching applies
        at check-time; literal names take precedence over globs.
        """
        with self._lock:
            self._gates.setdefault(tool_name, []).append(gate)

    def unregister(self, tool_name: str) -> None:
        """Drop all gates for ``tool_name``."""
        with self._lock:
            self._gates.pop(tool_name, None)

    def clear(self) -> None:
        """Drop every registered gate (test hook)."""
        with self._lock:
            self._gates.clear()

    # ----- evaluation -------------------------------------------------------

    def check(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        context: Optional[ToolCallContext] = None,
        server_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> PermissionResult:
        """Evaluate every applicable gate and return the verdict.

        Literal-name gates are evaluated first, then any glob gates that
        match. The first non-ALLOW result wins; if every gate returns
        ALLOW the call is allowed. When no gate matches, the default
        fallthrough gate runs.
        """

        ctx = context or ToolCallContext(
            tool_name=tool_name,
            arguments=dict(arguments or {}),
            server_id=server_id,
            task_id=task_id,
        )

        # Copy the registry's gate list under the lock; gate functions
        # themselves run outside the lock so a gate that does I/O does
        # not block concurrent registration.
        with self._lock:
            literal = list(self._gates.get(tool_name, []))
            glob_entries: List[PermissionGate] = []
            for registered_name, gates in self._gates.items():
                if registered_name == tool_name:
                    continue
                if "*" in registered_name and fnmatch.fnmatchcase(
                    tool_name, registered_name
                ):
                    glob_entries.extend(gates)

        ordered: List[PermissionGate] = literal + glob_entries

        if not ordered:
            return default_gate(ctx)

        for gate in ordered:
            verdict = gate(ctx)
            if not verdict.allowed:
                return verdict
        return PermissionResult.allow(
            f"All {len(ordered)} registered gate(s) allowed the call."
        )


# ---------------------------------------------------------------------------
# Module-level default registry + convenience wrappers
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY: PermissionRegistry = PermissionRegistry()


def get_default_registry() -> PermissionRegistry:
    """Return the process-wide default registry.

    Callers that want isolation (tests, parallel sessions) construct a
    fresh :class:`PermissionRegistry` and pass it into the agent loop
    directly.
    """
    return _DEFAULT_REGISTRY


def register_permission(tool_name: str, gate: PermissionGate) -> None:
    """Register ``gate`` for ``tool_name`` on the default registry."""
    _DEFAULT_REGISTRY.register(tool_name, gate)


def check_permission(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    context: Optional[ToolCallContext] = None,
    *,
    registry: Optional[PermissionRegistry] = None,
    server_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> PermissionResult:
    """Convenience: evaluate ``tool_name`` against the default registry."""
    target = registry or _DEFAULT_REGISTRY
    return target.check(
        tool_name,
        arguments,
        context=context,
        server_id=server_id,
        task_id=task_id,
    )


__all__ = [
    "PermissionGate",
    "PermissionRegistry",
    "PermissionResult",
    "ToolCallContext",
    "check_permission",
    "default_gate",
    "get_default_registry",
    "register_permission",
]
