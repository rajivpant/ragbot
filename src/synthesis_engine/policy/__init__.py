"""Cross-workspace policy: routing, confidentiality boundaries, and audit.

The policy package is the synthesis-engine substrate's enforcement layer
for multi-workspace operations. Three orthogonal concerns:

* :mod:`.routing` decides which LLM model (or class of models) a given
  workspace is allowed to route requests to. Per-workspace ``routing.yaml``
  declares confidentiality, allowed/denied model globs, ``local_only``,
  and a fallback behavior when an attempt to use a disallowed model is
  detected.

* :mod:`.confidentiality` enforces cross-workspace mixing rules. The
  effective confidentiality of a multi-workspace operation is the
  STRICTEST among the participating workspaces. AIR_GAPPED workspaces
  cannot mix with anything; CLIENT_CONFIDENTIAL workspaces cannot mix
  with PUBLIC; PERSONAL + CLIENT_CONFIDENTIAL is allowed but audited.
  Plugs into :class:`synthesis_engine.agent.permissions.PermissionRegistry`
  via the ``cross_workspace_gate`` callable.

* :mod:`.audit` writes an append-only JSONL audit trail at
  ``~/.synthesis/cross-workspace-audit.jsonl`` (env-overridable). Every
  cross-workspace synthesis, model call gated by routing policy, and
  tool call observed by a confidentiality boundary lands here with
  redacted args so the operator has a forensically clean record.

Fail-closed is the default everywhere a default is needed: unknown
confidentiality tags collapse to the strictest policy; missing
``routing.yaml`` returns a PUBLIC-confidentiality policy with
``fallback_behavior=WARN`` and emits a one-time log warning so the
operator knows they are running unconfigured.
"""

from __future__ import annotations

from .audit import (
    AuditEntry,
    read_recent,
    record,
    redact_args,
)
from .confidentiality import (
    ConfidentialityBoundary,
    ConfidentialityCheck,
    check_cross_workspace_op,
    cross_workspace_gate,
    register_cross_workspace_gate,
)
from .routing import (
    AllowanceCheck,
    Confidentiality,
    EXAMPLE_ROUTING_YAML,
    FallbackBehavior,
    RoutingPolicy,
    is_model_allowed,
    load_routing_policy,
)

__all__ = [
    "AllowanceCheck",
    "AuditEntry",
    "Confidentiality",
    "ConfidentialityBoundary",
    "ConfidentialityCheck",
    "EXAMPLE_ROUTING_YAML",
    "FallbackBehavior",
    "RoutingPolicy",
    "check_cross_workspace_op",
    "cross_workspace_gate",
    "is_model_allowed",
    "load_routing_policy",
    "read_recent",
    "record",
    "redact_args",
    "register_cross_workspace_gate",
]
