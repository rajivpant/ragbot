"""synthesis_engine.mcp — Model Context Protocol client substrate.

This package implements the *client* side of the Model Context Protocol
(MCP) as specified by the 2025-11-25 revision, on top of the official
``mcp`` Python SDK (``mcp>=1.27.0``). It is the shared building block
that every synthesis-engineering runtime (Ragbot, Ragenie, synthesis-
console, future implementations) consumes when it needs to talk to MCP
servers — local stdio binaries or remote HTTP/SSE endpoints.

Public surface
--------------

Top-level client orchestration:

* :class:`MCPClient` — one client per process; manages multiple server
  connections, threads sampling/elicitation/roots callbacks through to
  every session, and exposes the primitive operations.
* :func:`get_default_client`, :func:`set_default_client` — process-wide
  singleton helpers for the common case of one shared registry.

Configuration:

* :class:`MCPConfig`, :class:`MCPServerConfig`, :class:`MCPDefaults`,
  :class:`AuthConfig` — the validated schema for ``~/.synthesis/mcp.yaml``.
* :func:`load_mcp_config`, :func:`save_mcp_config` — read/write helpers.

Per-primitive helpers (advanced; most callers go through :class:`MCPClient`):

* tools — :func:`list_tools`, :func:`call_tool`
* resources — :func:`list_resources`, :func:`list_resource_templates`,
  :func:`read_resource`, :func:`subscribe_resource`,
  :func:`unsubscribe_resource`
* prompts — :func:`list_prompts`, :func:`get_prompt`
* roots — :class:`RootsProvider`, :class:`StaticRootsProvider`
* sampling — :class:`SamplingCallback`, :func:`default_sampling_handler`
* elicitation — :class:`ElicitationCallback`,
  :func:`default_elicitation_handler`

Tasks (2025-11-25 spec, SEP-1686):

* :mod:`synthesis_engine.mcp.tasks` — call_tool_as_task, poll_until_done,
  get_status, get_result, cancel, list_tasks, subscribe.

Transports:

* :mod:`synthesis_engine.mcp.transport` — stdio, http (Streamable HTTP),
  sse (legacy).

Auth:

* :mod:`synthesis_engine.mcp.auth` — OAuth 2.1 + Dynamic Client
  Registration, plus the CIMD-style client metadata document flow
  preferred by the 2025-11-25 spec.

Proxy:

* :class:`StdioHTTPProxy` — wrap a stdio server behind a Streamable-HTTP
  endpoint, useful for serving local servers to non-local consumers.

Per-workspace allow/deny
------------------------

:meth:`MCPClient.get_active_servers` resolves the user's
``enabled_workspaces`` / ``disabled_workspaces`` rules and returns only
the servers admitted for a given workspace. The substrate's
discovery-filter registration (``synthesis_engine.discovery``) is
honored under the ``"mcp_servers"`` scope, so a runtime can plug in a
workspace-aware filter that runs ahead of the config-level policy.
"""

from .auth import (
    DiskTokenStorage,
    LocalBrowserOAuthFlow,
    MCPAuthError,
    build_oauth_provider,
)
from .client import MCPClient, get_default_client, set_default_client
from .config import (
    AuthConfig,
    MCPConfig,
    MCPDefaults,
    MCPServerConfig,
    load_mcp_config,
    mcp_config_path,
    mcp_state_dir,
    save_mcp_config,
)
from .primitives import (
    ElicitationCallback,
    RootsProvider,
    SamplingCallback,
    StaticRootsProvider,
    call_tool,
    default_elicitation_handler,
    default_sampling_handler,
    get_prompt,
    list_prompts,
    list_resource_templates,
    list_resources,
    list_tools,
    read_resource,
    subscribe_resource,
    unsubscribe_resource,
)
from .proxy import StdioHTTPProxy
from .registry import (
    CachedCatalog,
    MCPRegistry,
    MCPRegistryError,
    ServerEntry,
    ServerStatus,
)
from .transport import (
    MCPTransportError,
    open_http_transport,
    open_sse_transport,
    open_stdio_transport,
    open_transport,
)

# Submodule re-export for the Tasks API (``from synthesis_engine.mcp import tasks``).
from . import tasks  # noqa: F401  re-export


# Discovery scope name for runtime-level filters on the MCP server set.
SCOPE_MCP_SERVERS = "mcp_servers"


__all__ = [
    # top-level client
    "MCPClient",
    "get_default_client",
    "set_default_client",
    # config
    "AuthConfig",
    "MCPConfig",
    "MCPDefaults",
    "MCPServerConfig",
    "load_mcp_config",
    "save_mcp_config",
    "mcp_config_path",
    "mcp_state_dir",
    # primitives
    "call_tool",
    "list_tools",
    "list_resources",
    "list_resource_templates",
    "read_resource",
    "subscribe_resource",
    "unsubscribe_resource",
    "list_prompts",
    "get_prompt",
    "RootsProvider",
    "StaticRootsProvider",
    "SamplingCallback",
    "default_sampling_handler",
    "ElicitationCallback",
    "default_elicitation_handler",
    # registry
    "MCPRegistry",
    "MCPRegistryError",
    "ServerEntry",
    "ServerStatus",
    "CachedCatalog",
    # transport
    "open_transport",
    "open_stdio_transport",
    "open_http_transport",
    "open_sse_transport",
    "MCPTransportError",
    # auth
    "MCPAuthError",
    "DiskTokenStorage",
    "LocalBrowserOAuthFlow",
    "build_oauth_provider",
    # proxy
    "StdioHTTPProxy",
    # tasks (submodule export)
    "tasks",
    # discovery scope key
    "SCOPE_MCP_SERVERS",
]
