"""Cross-workspace confidentiality boundary enforcement.

A multi-workspace operation — a synthesis query that pulls memory from
``acme-news`` and ``acme-user``, a tool call that touches a file in
``beta-media`` while reading from ``acme-user`` — has an EFFECTIVE
confidentiality equal to the STRICTEST among the participating
workspaces. From there:

* AIR_GAPPED data must NEVER leave its workspace. Any op that mixes an
  AIR_GAPPED workspace with another workspace is denied.

* CLIENT_CONFIDENTIAL data must NEVER mix with PUBLIC data. A leak
  vector worth surfacing on the homepage of the product.

* PERSONAL + CLIENT_CONFIDENTIAL is borderline — operators routinely
  bring personal context (preferences, scratch notes) into client work,
  so the substrate allows the mix but records it in the audit log so a
  CTO can later reconstruct what touched what.

* Same-tier mixes between two workspaces of the same confidentiality
  are allowed without audit (a PUBLIC + PUBLIC join doesn't need to
  leave a trace).

The enforcement integrates with the existing PermissionRegistry from
:mod:`synthesis_engine.agent.permissions`: callers register the
:func:`cross_workspace_gate` against any tool name that performs a
multi-workspace operation, and the gate consults the per-workspace
routing policies and the rules above.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..agent.permissions import (
    PermissionGate,
    PermissionRegistry,
    PermissionResult,
    ToolCallContext,
)
from .routing import Confidentiality, RoutingPolicy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfidentialityBoundary:
    """A pairwise verdict between two workspaces.

    Returned as part of :class:`ConfidentialityCheck` so callers (audit
    log, error messages, UI surfaces) can render the exact pair that
    blocked an op.
    """

    from_workspace: str
    to_workspace: str
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ConfidentialityCheck:
    """Aggregate verdict for a cross-workspace operation.

    Attributes:
        allowed: True iff EVERY pairwise boundary allows the op.
        effective_confidentiality: max(participating_confidentialities).
            This is the policy the operation should be governed by once
            it is allowed to proceed.
        boundaries: One ConfidentialityBoundary per ordered pair.
        requires_audit: True iff the op is allowed but the substrate
            still wants a record (e.g., PERSONAL + CLIENT_CONFIDENTIAL).
        reason: Human-readable summary; suitable for surfacing to the
            user or writing to a structured log.
    """

    allowed: bool
    effective_confidentiality: Confidentiality
    boundaries: Tuple[ConfidentialityBoundary, ...]
    requires_audit: bool
    reason: str


# ---------------------------------------------------------------------------
# Pairwise rule table
# ---------------------------------------------------------------------------


def _pairwise_allowed(
    a: Confidentiality, b: Confidentiality
) -> Tuple[bool, bool, str]:
    """Return ``(allowed, requires_audit, reason)`` for one ordered pair.

    The rules:
      * AIR_GAPPED + anything-non-air_gapped → DENIED.
      * CLIENT_CONFIDENTIAL + PUBLIC → DENIED.
      * CLIENT_CONFIDENTIAL + PERSONAL → ALLOWED, requires audit.
      * Anything else → ALLOWED, no audit.
    """

    # AIR_GAPPED is exclusive — both sides must be AIR_GAPPED for the
    # mix to be allowed, and even then the operation is treated as
    # single-workspace from the substrate's point of view.
    if Confidentiality.AIR_GAPPED in (a, b) and a != b:
        return (
            False,
            False,
            "AIR_GAPPED workspace data cannot be mixed with any other "
            "workspace; route the op through the AIR_GAPPED workspace alone.",
        )

    # CLIENT_CONFIDENTIAL never mixes with PUBLIC.
    cc = Confidentiality.CLIENT_CONFIDENTIAL
    if (a == cc and b == Confidentiality.PUBLIC) or (
        b == cc and a == Confidentiality.PUBLIC
    ):
        return (
            False,
            False,
            "CLIENT_CONFIDENTIAL workspace cannot share an operation with a "
            "PUBLIC workspace.",
        )

    # CLIENT_CONFIDENTIAL + PERSONAL is borderline → allowed-with-audit.
    if {a, b} == {cc, Confidentiality.PERSONAL}:
        return (
            True,
            True,
            "PERSONAL + CLIENT_CONFIDENTIAL mix is allowed but recorded in "
            "the audit log per substrate policy.",
        )

    return (True, False, "Pair is within policy.")


# ---------------------------------------------------------------------------
# Top-level check
# ---------------------------------------------------------------------------


def check_cross_workspace_op(
    active: List[str],
    routing_policies: Dict[str, RoutingPolicy],
) -> ConfidentialityCheck:
    """Decide whether an op spanning ``active`` workspaces is allowed.

    Args:
        active: Ordered list of workspace names participating in the op.
            A single-workspace op (``len(active) == 1``) is trivially
            allowed and returns the workspace's own confidentiality.
        routing_policies: Map of workspace name → its RoutingPolicy. A
            workspace missing from this map is treated as AIR_GAPPED
            (fail-closed) and the op is denied.

    Returns:
        A :class:`ConfidentialityCheck` carrying the aggregate verdict,
        the effective confidentiality (max across participants), every
        pairwise boundary verdict, and whether an audit entry is
        required even on success.
    """

    if not active:
        return ConfidentialityCheck(
            allowed=False,
            effective_confidentiality=Confidentiality.AIR_GAPPED,
            boundaries=(),
            requires_audit=False,
            reason="No active workspaces — no operation to authorize.",
        )

    # Resolve per-workspace confidentiality; missing → AIR_GAPPED (fail-closed).
    confidentialities: Dict[str, Confidentiality] = {}
    missing: List[str] = []
    for name in active:
        policy = routing_policies.get(name)
        if policy is None:
            missing.append(name)
            confidentialities[name] = Confidentiality.AIR_GAPPED
        else:
            confidentialities[name] = policy.confidentiality

    if missing:
        logger.warning(
            "Cross-workspace op references workspaces with no loaded "
            "routing policy: %s — treating as AIR_GAPPED (fail-closed).",
            missing,
        )

    effective = max(confidentialities.values())

    # Single workspace is trivially allowed; the audit log still gets a
    # record from the upstream caller, but the boundary check has nothing
    # to evaluate.
    if len(active) == 1:
        return ConfidentialityCheck(
            allowed=True,
            effective_confidentiality=effective,
            boundaries=(),
            requires_audit=False,
            reason=f"Single-workspace op in {active[0]!r}; no boundary to evaluate.",
        )

    # Pairwise evaluation over unique ordered pairs.
    boundaries: List[ConfidentialityBoundary] = []
    any_denied = False
    any_audit = False
    deny_reasons: List[str] = []

    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            ca, cb = confidentialities[a], confidentialities[b]
            allowed, requires_audit, reason = _pairwise_allowed(ca, cb)
            boundaries.append(
                ConfidentialityBoundary(
                    from_workspace=a,
                    to_workspace=b,
                    allowed=allowed,
                    reason=reason,
                )
            )
            if not allowed:
                any_denied = True
                deny_reasons.append(f"{a} <-> {b}: {reason}")
            if requires_audit:
                any_audit = True

    if any_denied:
        return ConfidentialityCheck(
            allowed=False,
            effective_confidentiality=effective,
            boundaries=tuple(boundaries),
            requires_audit=False,
            reason="; ".join(deny_reasons),
        )

    return ConfidentialityCheck(
        allowed=True,
        effective_confidentiality=effective,
        boundaries=tuple(boundaries),
        requires_audit=any_audit,
        reason=(
            f"All {len(boundaries)} pairwise boundaries allow the op; "
            f"effective confidentiality {effective.name}."
        ),
    )


# ---------------------------------------------------------------------------
# PermissionRegistry integration
# ---------------------------------------------------------------------------


# The metadata key the agent loop is expected to populate when it
# dispatches a multi-workspace tool call. Consolidated here so callers
# don't sprinkle string literals across the codebase.
ACTIVE_WORKSPACES_METADATA_KEY = "active_workspaces"
ROUTING_POLICIES_METADATA_KEY = "routing_policies"


def cross_workspace_gate(context: ToolCallContext) -> PermissionResult:
    """Permission gate enforcing the confidentiality boundary.

    The gate reads two metadata keys from the :class:`ToolCallContext`:

    * ``active_workspaces``: ``List[str]`` of workspaces the tool call
      touches.
    * ``routing_policies``: ``Dict[str, RoutingPolicy]`` mapping each
      workspace to its loaded policy.

    A call with fewer than two distinct active workspaces is allowed
    without further checks — single-workspace ops fall through to
    whatever other gates the registry has for the tool.

    Missing metadata is treated as a programming error and the gate
    DENIES the call (fail-closed) with a clear remediation message.
    """

    active = context.metadata.get(ACTIVE_WORKSPACES_METADATA_KEY)
    if active is None or not isinstance(active, (list, tuple)):
        return PermissionResult.deny(
            "cross_workspace_gate requires "
            f"context.metadata[{ACTIVE_WORKSPACES_METADATA_KEY!r}] to be a "
            "list of workspace names."
        )

    # De-duplicate while preserving order, then short-circuit single-ws.
    seen: List[str] = []
    for name in active:
        if isinstance(name, str) and name and name not in seen:
            seen.append(name)
    if len(seen) <= 1:
        return PermissionResult.allow(
            "Single-workspace op; confidentiality boundary not engaged."
        )

    policies = context.metadata.get(ROUTING_POLICIES_METADATA_KEY)
    if not isinstance(policies, dict):
        return PermissionResult.deny(
            "cross_workspace_gate requires "
            f"context.metadata[{ROUTING_POLICIES_METADATA_KEY!r}] to be a "
            "dict of workspace -> RoutingPolicy."
        )

    check = check_cross_workspace_op(seen, policies)
    if not check.allowed:
        return PermissionResult.deny(
            f"Confidentiality boundary denied cross-workspace op: "
            f"{check.reason}"
        )

    suffix = " (audit required)" if check.requires_audit else ""
    return PermissionResult.allow(
        f"Cross-workspace op allowed under effective confidentiality "
        f"{check.effective_confidentiality.name}{suffix}."
    )


def register_cross_workspace_gate(
    registry: PermissionRegistry,
    tool_name: str = "*",
) -> None:
    """Register :func:`cross_workspace_gate` on ``registry``.

    Args:
        registry: The PermissionRegistry to install the gate on.
        tool_name: Either a literal tool name or a glob. Defaults to
            ``"*"`` so the gate fires for EVERY multi-workspace tool
            call. Single-workspace calls short-circuit inside the gate
            so the wildcard does not block ordinary single-workspace
            traffic.
    """
    registry.register(tool_name, cross_workspace_gate)


__all__ = [
    "ACTIVE_WORKSPACES_METADATA_KEY",
    "ConfidentialityBoundary",
    "ConfidentialityCheck",
    "ROUTING_POLICIES_METADATA_KEY",
    "check_cross_workspace_op",
    "cross_workspace_gate",
    "register_cross_workspace_gate",
]
