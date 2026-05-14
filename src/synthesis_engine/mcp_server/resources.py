"""MCP resources surface for :class:`RagbotMCPServer`.

The server exposes three categories of resource:

* **Workspaces**          — one resource per known workspace, addressed as
  ``synthesis://workspaces/<name>``. Reading the resource returns the
  workspace's metadata (name, confidentiality, routing policy summary).

* **Skills**              — one resource per ``(workspace, skill)`` pair
  visible from that workspace, addressed as
  ``synthesis://skills/<workspace>/<skill_name>``. Reading returns the
  SKILL.md body.

* **Audit (recent)**      — a single resource at
  ``synthesis://audit/recent`` whose content is the most-recent entries
  of the cross-workspace audit log as JSONL.

The MCP SDK's ``read_resource`` decorator expects either a single bytes/
string payload or an iterable of :class:`ReadResourceContents`. We
return :class:`ReadResourceContents` so the mime type is explicit and
multi-line resources stay clean across transports.

Dispatch is split into ``list_*`` helpers (used by the server's
``list_resources`` decorator) and a single :func:`read_resource_contents`
entry point used by the ``read_resource`` decorator. The resolver is
URI-shape based so a new resource family is one constant + one helper
away.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Tuple
from urllib.parse import unquote

from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import Resource

from ..policy.audit import read_recent as audit_read_recent
from ..policy.routing import RoutingPolicy


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URI scheme constants
# ---------------------------------------------------------------------------


URI_SCHEME = "synthesis"
WORKSPACE_RESOURCE_PREFIX = f"{URI_SCHEME}://workspaces/"
SKILL_RESOURCE_PREFIX = f"{URI_SCHEME}://skills/"
AUDIT_RESOURCE_URI = f"{URI_SCHEME}://audit/recent"


# ---------------------------------------------------------------------------
# Resource provider
# ---------------------------------------------------------------------------


@dataclass
class ResourceProvider:
    """Runtime dependencies the resource helpers consume.

    Held as a separate dataclass so the server can build it once and
    pass it through to each :func:`list_*` / :func:`read_resource_contents`
    call. Tests inject fakes for ``list_workspaces``, ``skills_for``,
    and ``routing_policy_for``.

    Attributes:
        list_workspaces:    Callable returning every known workspace
                            name. The server's resolver decides whether
                            this is "all on this machine" or "the
                            subset visible to the current bearer token."
        skills_for:         Callable ``workspace -> Iterable[Skill]``.
                            The returned skills are the ones visible
                            from that workspace's inheritance chain.
        routing_policy_for: Callable ``workspace -> RoutingPolicy``.
        audit_limit:        Max audit lines to surface on a
                            ``synthesis://audit/recent`` read. 200 by
                            default — enough to be useful, small
                            enough to fit in one MCP response.
    """

    list_workspaces: Callable[[], Iterable[str]]
    skills_for: Callable[[str], Iterable[Any]]
    routing_policy_for: Callable[[str], RoutingPolicy]
    audit_limit: int = 200


# ---------------------------------------------------------------------------
# Resource listing helpers
# ---------------------------------------------------------------------------


def list_workspace_resources(provider: ResourceProvider) -> List[Resource]:
    """One :class:`Resource` per workspace returned by the provider."""
    out: List[Resource] = []
    for ws in sorted(set(provider.list_workspaces())):
        if not ws:
            continue
        out.append(
            Resource(
                uri=f"{WORKSPACE_RESOURCE_PREFIX}{ws}",
                name=ws,
                description=f"Workspace metadata for {ws!r}.",
                mimeType="application/json",
            )
        )
    return out


def list_skill_resources(provider: ResourceProvider) -> List[Resource]:
    """One :class:`Resource` per ``(workspace, skill)`` visible pair.

    The URI shape is ``synthesis://skills/<workspace>/<skill_name>``.
    Listing every visible pair keeps the surface explicit: an MCP client
    can see at a glance which skills are usable from a given workspace
    without first reading the workspace resource.
    """
    out: List[Resource] = []
    seen: set = set()
    for ws in sorted(set(provider.list_workspaces())):
        if not ws:
            continue
        for skill in provider.skills_for(ws):
            name = getattr(skill, "name", None)
            if not name:
                continue
            uri = f"{SKILL_RESOURCE_PREFIX}{ws}/{name}"
            if uri in seen:
                continue
            seen.add(uri)
            description = getattr(skill, "description", "") or (
                f"Skill {name} visible from workspace {ws}."
            )
            out.append(
                Resource(
                    uri=uri,
                    name=f"{ws}/{name}",
                    description=description,
                    mimeType="text/markdown",
                )
            )
    return out


def list_audit_resources(provider: ResourceProvider) -> List[Resource]:
    """Single-entry list with the ``synthesis://audit/recent`` resource."""
    return [
        Resource(
            uri=AUDIT_RESOURCE_URI,
            name="Recent audit entries",
            description=(
                "JSONL stream of the most recent cross-workspace audit "
                f"entries (up to {provider.audit_limit})."
            ),
            mimeType="application/x-ndjson",
        )
    ]


def list_all_resources(provider: ResourceProvider) -> List[Resource]:
    """Aggregate every resource family into one ordered list."""
    return (
        list_workspace_resources(provider)
        + list_skill_resources(provider)
        + list_audit_resources(provider)
    )


# ---------------------------------------------------------------------------
# Resource reader
# ---------------------------------------------------------------------------


def _split_skill_uri(uri: str) -> Optional[Tuple[str, str]]:
    """Parse ``synthesis://skills/<workspace>/<skill_name>`` into a tuple."""
    if not uri.startswith(SKILL_RESOURCE_PREFIX):
        return None
    rest = uri[len(SKILL_RESOURCE_PREFIX):]
    parts = rest.split("/", 1)
    if len(parts) != 2:
        return None
    ws = unquote(parts[0]).strip()
    skill = unquote(parts[1]).strip()
    if not ws or not skill:
        return None
    return ws, skill


def _read_workspace_resource(
    provider: ResourceProvider, uri: str
) -> Iterable[ReadResourceContents]:
    rest = uri[len(WORKSPACE_RESOURCE_PREFIX):]
    workspace = unquote(rest).strip("/")
    if not workspace:
        raise LookupError(f"Workspace resource URI {uri!r} is malformed.")
    known = set(provider.list_workspaces())
    if workspace not in known:
        raise LookupError(f"Workspace {workspace!r} is not known.")
    policy = provider.routing_policy_for(workspace)
    body = {
        "workspace": workspace,
        "confidentiality": policy.confidentiality.name,
        "allowed_models": list(policy.allowed_models),
        "denied_models": list(policy.denied_models),
        "local_only": policy.local_only,
        "fallback_behavior": policy.fallback_behavior.value,
    }
    yield ReadResourceContents(
        content=json.dumps(body, sort_keys=True, indent=2),
        mime_type="application/json",
    )


def _read_skill_resource(
    provider: ResourceProvider, uri: str
) -> Iterable[ReadResourceContents]:
    parsed = _split_skill_uri(uri)
    if parsed is None:
        raise LookupError(f"Skill resource URI {uri!r} is malformed.")
    workspace, skill_name = parsed
    for skill in provider.skills_for(workspace):
        if getattr(skill, "name", None) == skill_name:
            body = getattr(skill, "body", "") or ""
            yield ReadResourceContents(
                content=body,
                mime_type="text/markdown",
            )
            return
    raise LookupError(
        f"Skill {skill_name!r} not visible from workspace {workspace!r}."
    )


def _read_audit_resource(
    provider: ResourceProvider, uri: str
) -> Iterable[ReadResourceContents]:
    entries = audit_read_recent(limit=provider.audit_limit)
    # Emit as JSONL — one entry per line, in chronological order so a
    # consumer can tail the stream.
    lines = [
        json.dumps(entry.to_dict(), sort_keys=True, ensure_ascii=False)
        for entry in entries
    ]
    yield ReadResourceContents(
        content="\n".join(lines) + ("\n" if lines else ""),
        mime_type="application/x-ndjson",
    )


def read_resource_contents(
    provider: ResourceProvider, uri: str
) -> Iterable[ReadResourceContents]:
    """Resolve ``uri`` to one or more :class:`ReadResourceContents` items.

    Raises:
        LookupError: when the URI does not match any known resource
            family or the named resource does not exist. The server
            translates this into a clear MCP error response.
    """
    uri_str = str(uri)
    if uri_str.startswith(WORKSPACE_RESOURCE_PREFIX):
        return _read_workspace_resource(provider, uri_str)
    if uri_str.startswith(SKILL_RESOURCE_PREFIX):
        return _read_skill_resource(provider, uri_str)
    if uri_str == AUDIT_RESOURCE_URI:
        return _read_audit_resource(provider, uri_str)
    raise LookupError(f"Unknown resource URI: {uri_str!r}")


__all__ = [
    "AUDIT_RESOURCE_URI",
    "ResourceProvider",
    "SKILL_RESOURCE_PREFIX",
    "URI_SCHEME",
    "WORKSPACE_RESOURCE_PREFIX",
    "list_all_resources",
    "list_audit_resources",
    "list_skill_resources",
    "list_workspace_resources",
    "read_resource_contents",
]
