"""Cross-workspace policy API endpoints.

REST surface for inspecting per-workspace routing policies, dry-running
the cross-workspace boundary check, and reading the audit log. The
router is a thin adapter around :mod:`synthesis_engine.policy`: every
endpoint resolves a workspace name to an on-disk root, loads the
policy, and returns a JSON-serialisable view.

Endpoints:

    GET    /api/policy/workspaces/{workspace}        per-workspace policy
    GET    /api/policy/cross-workspace-check         dry-run boundary check
    GET    /api/policy/audit/recent                  recent audit log entries
    GET    /api/policy/example-routing-yaml          the embedded example schema

The router does not authenticate callers. Ragbot's single-user threat
model is the same as for the other routers; multi-user auth is a
separate concern.

Workspace resolution follows the conventions used elsewhere in the
codebase:

    1. ``~/workspaces/<name>/ai-knowledge-<name>``  (workspace-rooted layout)
    2. ``~/ai-knowledge-<name>``                    (legacy flat-parent)
    3. ``~/.synthesis/workspaces/<name>``           (fallback)

The :func:`set_default_workspace_resolver` hook lets tests override the
resolution policy without touching the filesystem. Production wires the
default resolver through the FastAPI lifespan startup (or relies on
the default convention above).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

# Add src/ to sys.path so synthesis_engine is importable when this
# module is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.exceptions import ConfigurationError
from synthesis_engine.policy import (
    AuditEntry,
    Confidentiality,
    EXAMPLE_ROUTING_YAML,
    FallbackBehavior,
    RoutingPolicy,
    check_cross_workspace_op,
    is_model_allowed,
    load_routing_policy,
    read_recent,
)


logger = logging.getLogger("api.routers.policy")

router = APIRouter(prefix="/api/policy", tags=["policy"])


# ---------------------------------------------------------------------------
# Workspace-root resolver
# ---------------------------------------------------------------------------


WorkspaceResolver = Callable[[str], Optional[str]]
"""Resolve a workspace name to an absolute filesystem root. Return None
when the workspace is unknown (the router will surface a 404)."""


def _default_workspace_resolver(name: str) -> Optional[str]:
    """Resolve a workspace name to its on-disk repo root.

    Consults the substrate's workspace discovery (the same logic that
    backs ``/api/workspaces``) so the policy router agrees with the rest
    of the app on workspace identity — including demo mode, the Docker
    container's bundled ``/app/demo/ai-knowledge-demo``, and the
    operator's actual ``~/workspaces/<W>/ai-knowledge-<W>`` layout.

    Falls back to the legacy ``~/workspaces/<name>/ai-knowledge-<name>``
    layout-guessing chain when discovery returns nothing (e.g., in unit
    tests with a synthetic home directory where the substrate's
    discovery is mocked out).
    """
    # Lazy import: the policy router is imported at FastAPI app-init
    # time; pulling ragbot.discover_workspaces into the module-import
    # path would couple the policy substrate to the runtime layer.
    try:
        from ragbot import discover_workspaces  # noqa: WPS433
    except ImportError:
        discover_workspaces = None  # type: ignore[assignment]

    if discover_workspaces is not None:
        try:
            from ragbot import get_workspace_info  # noqa: WPS433
            for ws in discover_workspaces():
                if ws.get("name") == name or ws.get("dir_name") == name:
                    # discover_workspaces() returns the raw dict (keys:
                    # name, path, dir_name, config, ai_knowledge);
                    # get_workspace_info promotes it to the
                    # WorkspaceInfo pydantic model whose ``repo_path``
                    # field is the canonical answer. Use that so the
                    # policy router agrees with /api/workspaces on the
                    # path it returns.
                    info = get_workspace_info(ws)
                    repo_path = getattr(info, "repo_path", None) or ws.get("path")
                    if repo_path and Path(repo_path).is_dir():
                        return str(repo_path)
        except Exception:  # pragma: no cover - discovery is best-effort
            pass

    # Legacy / test fallback: probe the standard layout locations.
    candidates = [
        Path.home() / "workspaces" / name / f"ai-knowledge-{name}",
        Path.home() / f"ai-knowledge-{name}",
        Path.home() / ".synthesis" / "workspaces" / name,
    ]
    for path in candidates:
        if path.is_dir():
            return str(path)
    return None


_RESOLVER: WorkspaceResolver = _default_workspace_resolver


def set_default_workspace_resolver(resolver: WorkspaceResolver) -> None:
    """Install a workspace-resolver callable (test hook)."""

    global _RESOLVER
    _RESOLVER = resolver


def reset_workspace_resolver() -> None:
    """Reset to the on-disk default (test hook)."""

    global _RESOLVER
    _RESOLVER = _default_workspace_resolver


def _resolve_workspace_or_404(name: str) -> str:
    """Resolve ``name`` to a workspace root or raise HTTP 404."""

    root = _RESOLVER(name)
    if root is None:
        raise HTTPException(
            status_code=404,
            detail=f"workspace not found: {name!r}",
        )
    return root


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_policy(
    policy: RoutingPolicy,
    *,
    workspace: str,
    workspace_root: str,
) -> Dict[str, Any]:
    """Return a JSON-friendly view of a :class:`RoutingPolicy`."""

    routing_yaml_path = str(Path(workspace_root) / "routing.yaml")
    return {
        "workspace": workspace,
        "workspace_root": workspace_root,
        "routing_yaml_path": routing_yaml_path,
        "routing_yaml_exists": os.path.isfile(routing_yaml_path),
        "confidentiality": policy.confidentiality.name,
        "allowed_models": list(policy.allowed_models),
        "denied_models": list(policy.denied_models),
        "local_only": policy.local_only,
        "fallback_behavior": policy.fallback_behavior.value,
    }


def _serialise_audit_entry(entry: AuditEntry) -> Dict[str, Any]:
    """Return a JSON-friendly view of an :class:`AuditEntry`."""

    return entry.to_dict()


def _parse_workspace_list(raw: str) -> List[str]:
    """Parse a comma-separated ``workspaces`` query string.

    Drops empty fragments and de-duplicates while preserving order.
    Raises HTTP 400 when the cleaned list is empty.
    """

    seen: List[str] = []
    for fragment in raw.split(","):
        name = fragment.strip()
        if name and name not in seen:
            seen.append(name)
    if not seen:
        raise HTTPException(
            status_code=400,
            detail="workspaces must list at least one workspace name",
        )
    return seen


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/example-routing-yaml")
async def get_example_routing_yaml() -> Dict[str, str]:
    """Return the embedded example ``routing.yaml`` schema.

    Useful for the UI to render a starter template when no policy
    file exists yet.
    """

    return {"example": EXAMPLE_ROUTING_YAML}


@router.get("/workspaces/{workspace}")
async def get_workspace_policy(workspace: str) -> Dict[str, Any]:
    """Return the loaded :class:`RoutingPolicy` for ``workspace``.

    404 when the workspace cannot be resolved to an on-disk root.
    400 when the ``routing.yaml`` exists but is malformed.
    """

    root = _resolve_workspace_or_404(workspace)
    try:
        policy = load_routing_policy(root)
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"routing.yaml at {root} is malformed: {exc}"
            ),
        ) from exc
    return _serialise_policy(policy, workspace=workspace, workspace_root=root)


@router.get("/cross-workspace-check")
async def cross_workspace_check(
    workspaces: str = Query(
        ..., description="Comma-separated workspace names to evaluate."
    ),
    requested_model: Optional[str] = Query(
        default=None,
        description=(
            "Optional model id. When supplied, the per-workspace "
            "is_model_allowed verdict is included in the response."
        ),
    ),
) -> Dict[str, Any]:
    """Dry-run :func:`check_cross_workspace_op` for ``workspaces``.

    Returns ``{allowed, effective_confidentiality, reason,
    requires_audit, boundaries, policies}``. When ``requested_model``
    is supplied the response also carries ``model_routing``: a list of
    per-workspace ``{workspace, allowed, reason}`` verdicts plus the
    aggregate decision.
    """

    names = _parse_workspace_list(workspaces)

    policies: Dict[str, RoutingPolicy] = {}
    unresolved: List[str] = []
    for name in names:
        root = _RESOLVER(name)
        if root is None:
            unresolved.append(name)
            continue
        try:
            policies[name] = load_routing_policy(root)
        except ConfigurationError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"routing.yaml at {root} is malformed: {exc}",
            ) from exc

    if unresolved:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unresolved_workspaces",
                "workspaces": unresolved,
            },
        )

    check = check_cross_workspace_op(names, policies)

    response: Dict[str, Any] = {
        "workspaces": names,
        "allowed": check.allowed,
        "effective_confidentiality": check.effective_confidentiality.name,
        "requires_audit": check.requires_audit,
        "reason": check.reason,
        "boundaries": [
            {
                "from_workspace": b.from_workspace,
                "to_workspace": b.to_workspace,
                "allowed": b.allowed,
                "reason": b.reason,
            }
            for b in check.boundaries
        ],
        "policies": {
            name: {
                "confidentiality": policy.confidentiality.name,
                "fallback_behavior": policy.fallback_behavior.value,
                "local_only": policy.local_only,
            }
            for name, policy in policies.items()
        },
    }

    if requested_model:
        verdicts = []
        denying_count = 0
        for name in names:
            policy = policies[name]
            v = is_model_allowed(policy, requested_model)
            verdicts.append({
                "workspace": name,
                "allowed": v.allowed,
                "reason": v.reason,
                "fallback_behavior": policy.fallback_behavior.value,
                "suggested_fallback": v.suggested_fallback,
            })
            if not v.allowed:
                denying_count += 1
        aggregate_allowed = denying_count == 0
        response["model_routing"] = {
            "requested_model": requested_model,
            "aggregate_allowed": aggregate_allowed,
            "denying_workspace_count": denying_count,
            "verdicts": verdicts,
        }

    return response


@router.get("/audit/recent")
async def get_audit_recent(
    limit: int = Query(
        default=100,
        ge=1,
        le=10_000,
        description="Maximum number of entries to return (newest last).",
    ),
) -> Dict[str, Any]:
    """Return the most-recent ``limit`` audit-log entries.

    Robust to rotation; corrupt lines are skipped server-side and the
    caller sees only well-formed entries. Empty list when the log is
    missing or empty.
    """

    try:
        entries = read_recent(limit=limit)
    except Exception as exc:
        logger.exception("Failed to read audit log")
        raise HTTPException(
            status_code=500,
            detail=f"failed to read audit log: {type(exc).__name__}: {exc}",
        ) from exc

    return {
        "entries": [_serialise_audit_entry(e) for e in entries],
        "limit": limit,
        "count": len(entries),
    }


__all__ = [
    "WorkspaceResolver",
    "reset_workspace_resolver",
    "router",
    "set_default_workspace_resolver",
]
