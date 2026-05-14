"""synthesis_engine.mcp_server — expose Ragbot primitives as an MCP server.

Where :mod:`synthesis_engine.mcp` is the CLIENT side of MCP (Ragbot calls
out to other MCP servers), this package is the SERVER side: an MCP server
that surfaces Ragbot's own primitives (workspace search, document
retrieval, skill execution, agent runs) to any MCP-speaking client —
Claude Code, Cursor, ChatGPT desktop, or another agent.

Architecture
============

The server is split into four files so the responsibilities stay
separable and the test surface is straightforward:

* :mod:`.server`     — the :class:`RagbotMCPServer` class. Wraps
  :class:`mcp.server.lowlevel.Server`. Constructor accepts the runtime
  dependencies (workspace resolver, skill runtime, memory retriever,
  permission and routing registries). Methods ``serve_stdio()`` and
  ``serve_http()`` start the transport-specific loops.

* :mod:`.tools`      — the five MCP tool definitions: ``workspace_search``,
  ``workspace_search_multi``, ``document_get``, ``skill_run``,
  ``agent_run_start``. Each tool has a complete JSON input AND output
  schema and routes through the existing permission registry, cross-
  workspace policy gate, and (for agent runs) the agent loop.

* :mod:`.resources`  — MCP resource definitions. Exposes workspaces,
  per-workspace skills, and recent audit entries as readable resources
  under the ``synthesis://`` URI scheme.

* :mod:`.auth`       — Bearer-token authentication for the HTTP/SSE
  transport. Stdio mode is process-local and skips auth. HTTP mode
  fails closed when ``~/.synthesis/mcp-server.yaml`` is missing or
  malformed.

Two transports ship in one package
==================================

The same :class:`RagbotMCPServer` runs over stdio (the default; one
process per desktop client) and over HTTP/SSE (for remote clients). The
same tool and resource definitions back both transports — the only
difference is the auth layer. Stdio trust is process-local; HTTP requires
a Bearer token resolved against the per-server YAML.

Cross-workspace policy is enforced uniformly
============================================

Every tool exposed through the MCP server routes through the existing
:class:`synthesis_engine.agent.permissions.PermissionRegistry` and the
cross-workspace policy gate from
:mod:`synthesis_engine.policy.confidentiality`. A frontier-model call
requested via MCP from outside Ragbot still respects the active
workspace's ``routing.yaml`` and the AIR_GAPPED / CLIENT_CONFIDENTIAL
mixing rules.
"""

from __future__ import annotations

from .auth import (
    BearerToken,
    MCPServerAuthConfig,
    MCPServerAuthError,
    load_auth_config,
)
from .resources import (
    AUDIT_RESOURCE_URI,
    SKILL_RESOURCE_PREFIX,
    WORKSPACE_RESOURCE_PREFIX,
    list_audit_resources,
    list_skill_resources,
    list_workspace_resources,
    read_resource_contents,
)
from .server import RagbotMCPServer, ServerDependencies
from .tools import (
    TOOL_DEFINITIONS,
    ToolDispatchError,
    dispatch_tool,
)


__all__ = [
    # server
    "RagbotMCPServer",
    "ServerDependencies",
    # tools
    "TOOL_DEFINITIONS",
    "ToolDispatchError",
    "dispatch_tool",
    # resources
    "AUDIT_RESOURCE_URI",
    "SKILL_RESOURCE_PREFIX",
    "WORKSPACE_RESOURCE_PREFIX",
    "list_audit_resources",
    "list_skill_resources",
    "list_workspace_resources",
    "read_resource_contents",
    # auth
    "BearerToken",
    "MCPServerAuthConfig",
    "MCPServerAuthError",
    "load_auth_config",
]
