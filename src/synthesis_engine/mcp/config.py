"""Configuration schema and loader for ``~/.synthesis/mcp.yaml``.

The MCP configuration lives in the synthesis-engineering shared config home
under ``~/.synthesis/mcp.yaml``. It describes the user's catalog of
configured MCP servers and per-workspace allow/deny rules.

Schema (top level):

.. code-block:: yaml

    servers:
      - id: "fs-local"                   # required, unique within the file
        name: "Local Filesystem"         # required, human-readable
        description: "Read/write under ~/workspaces"
        transport: stdio                 # one of: stdio | sse | http
        # stdio fields
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/workspaces"]
        env: {}                          # optional environment overrides
        cwd: null                        # optional working directory
        # http / sse fields (omit when transport=stdio)
        url: null
        headers: {}                      # static headers (e.g., bearer for legacy servers)
        # workspace gating (optional; see Per-workspace allow/deny below)
        enabled_workspaces: ["*"]
        disabled_workspaces: []
        # auth (optional; only meaningful for remote http/sse transports)
        auth:
          mode: oauth                    # one of: none | oauth | bearer
          # CIMD-style identity (preferred over DCR per the 2025-11-25 spec)
          client_id_metadata_url: "https://app.example.com/mcp/client.json"
          client_name: "Ragbot"
          redirect_port: 33418           # localhost callback port (optional)
          scope: null                    # whitespace-separated scopes (optional)
          # bearer mode only
          token: null

    defaults:
      # global defaults applied to every server unless overridden
      timeout_seconds: 30
      enabled_by_default: true

Per-workspace allow/deny rules
------------------------------

Two complementary fields per server:

``enabled_workspaces``
    List of workspace names this server is enabled for. The literal ``"*"``
    matches every workspace. When the list is omitted entirely, the server
    inherits ``defaults.enabled_by_default``.

``disabled_workspaces``
    List of workspace names where the server is forcibly off, even if
    ``enabled_workspaces`` would otherwise admit it. Deny beats allow.

Examples:

* Enabled everywhere: ``enabled_workspaces: ["*"]``
* Only on the ``personal`` workspace: ``enabled_workspaces: ["personal"]``
* Everywhere except a sensitive workspace::

    enabled_workspaces: ["*"]
    disabled_workspaces: ["client-acme"]

The config schema is intentionally explicit. ``enabled_by_default`` exists
so the user can choose the global posture without having to enumerate every
workspace, but per-server overrides always take precedence.

Why this lives in the substrate
-------------------------------

Every synthesis runtime that consumes ``synthesis_engine.mcp`` will need
the same configuration shape. Putting it here means Ragenie, synthesis-
console, and future runtimes parse the same YAML and apply the same
workspace gating without re-implementing it.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from synthesis_engine.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------

TransportLiteral = Literal["stdio", "sse", "http"]
AuthModeLiteral = Literal["none", "oauth", "bearer"]


class AuthConfig(BaseModel):
    """Per-server authentication configuration.

    ``mode`` selects the strategy. ``oauth`` is the 2025-11-25-spec flow:
    the client discovers the server's authorization endpoints via RFC 9728
    Protected Resource Metadata, optionally registers via CIMD or RFC 7591
    Dynamic Client Registration, and obtains a PKCE-protected bearer token.
    ``bearer`` is the legacy path: a token is supplied directly. ``none``
    skips auth entirely.
    """

    mode: AuthModeLiteral = "none"
    client_id_metadata_url: Optional[str] = None
    client_name: str = "Ragbot"
    redirect_port: int = 33418
    scope: Optional[str] = None
    token: Optional[str] = None

    model_config = {"extra": "forbid"}


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server entry.

    Required fields: ``id``, ``name``, ``transport``. Transport-specific
    fields (``command``/``args`` for stdio; ``url`` for http/sse) are
    enforced via ``model_validator``.
    """

    id: str = Field(min_length=1, description="Stable opaque identifier.")
    name: str = Field(min_length=1, description="Human-readable label.")
    description: str = ""
    transport: TransportLiteral = "stdio"

    # stdio fields
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None

    # http / sse fields
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)

    # workspace gating
    enabled_workspaces: Optional[List[str]] = None
    disabled_workspaces: List[str] = Field(default_factory=list)

    # auth
    auth: AuthConfig = Field(default_factory=AuthConfig)

    # connection lifecycle
    timeout_seconds: int = 30
    enabled: bool = True

    model_config = {"extra": "forbid"}

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        # Conservative: alphanumeric, dash, dot, underscore. Keeps file
        # paths and JSON-RPC client identifiers tidy.
        bad = [ch for ch in v if not (ch.isalnum() or ch in "-_.")]
        if bad:
            raise ValueError(
                f"server id may only contain alphanumerics, '-', '_', '.': {v!r}"
            )
        return v

    def is_remote(self) -> bool:
        """Return True iff this is a transport-over-network server."""
        return self.transport in ("http", "sse")

    def is_enabled_for_workspace(self, workspace: Optional[str], default_on: bool) -> bool:
        """Return True iff this server is admitted for ``workspace``.

        Resolution order (deny beats allow):

        1. If ``self.enabled`` is False the answer is False regardless.
        2. If ``workspace`` is in ``disabled_workspaces`` the answer is False.
        3. If ``enabled_workspaces`` is None the global default applies.
        4. Otherwise, the answer is True iff ``"*"`` or ``workspace`` is in
           ``enabled_workspaces``.

        ``workspace`` of None means "not workspace-scoped." Such callers
        receive the global default unless the server has an explicit
        non-wildcard ``enabled_workspaces`` list, in which case the
        server requires a named workspace and the answer is False.
        """
        if not self.enabled:
            return False
        if workspace is not None and workspace in self.disabled_workspaces:
            return False
        if self.enabled_workspaces is None:
            return default_on
        if "*" in self.enabled_workspaces:
            return True
        if workspace is None:
            return False
        return workspace in self.enabled_workspaces


class MCPDefaults(BaseModel):
    """Top-level defaults block."""

    timeout_seconds: int = 30
    enabled_by_default: bool = True

    model_config = {"extra": "forbid"}


class MCPConfig(BaseModel):
    """Top-level configuration document for ``~/.synthesis/mcp.yaml``."""

    servers: List[MCPServerConfig] = Field(default_factory=list)
    defaults: MCPDefaults = Field(default_factory=MCPDefaults)

    model_config = {"extra": "forbid"}

    def get(self, server_id: str) -> Optional[MCPServerConfig]:
        """Return the server with ``server_id`` or ``None`` if absent."""
        for s in self.servers:
            if s.id == server_id:
                return s
        return None


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

DEFAULT_MCP_CONFIG_RELPATH = "mcp.yaml"


def synthesis_home() -> Path:
    """Return the synthesis-engineering shared config home as a Path.

    Honors ``SYNTHESIS_HOME`` (test/dev override) before falling back to
    ``~/.synthesis``. The directory is created on demand by callers that
    write into it; this function only resolves the path.
    """
    env = os.environ.get("SYNTHESIS_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".synthesis"


def mcp_config_path() -> Path:
    """Return the resolved path to ``mcp.yaml``."""
    return synthesis_home() / DEFAULT_MCP_CONFIG_RELPATH


def mcp_state_dir() -> Path:
    """Directory for MCP runtime state (token cache, server fingerprints)."""
    return synthesis_home() / "mcp"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_mcp_config(path: Optional[Path] = None) -> MCPConfig:
    """Load and validate ``mcp.yaml``.

    Returns an empty :class:`MCPConfig` (no servers) when the file is
    absent. Raises :class:`ConfigurationError` on parse or validation
    failure so callers get a single exception type to catch.
    """
    p = path or mcp_config_path()
    if not p.exists():
        return MCPConfig()
    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(f"failed to parse {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"{p}: top level must be a mapping, got {type(raw).__name__}"
        )
    try:
        return MCPConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigurationError(f"{p} failed validation: {e}") from e


def save_mcp_config(config: MCPConfig, path: Optional[Path] = None) -> Path:
    """Write ``config`` to ``mcp.yaml`` atomically.

    The destination directory is created if needed. The write is
    atomic: the YAML is rendered into a sibling ``.tmp`` file and then
    ``os.replace``d into place so a crash mid-write cannot leave the
    config truncated.
    """
    p = path or mcp_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = config.model_dump(mode="json", exclude_none=False)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)
    )
    os.replace(tmp, p)
    return p


__all__ = [
    "AuthConfig",
    "MCPConfig",
    "MCPDefaults",
    "MCPServerConfig",
    "DEFAULT_MCP_CONFIG_RELPATH",
    "load_mcp_config",
    "save_mcp_config",
    "mcp_config_path",
    "mcp_state_dir",
    "synthesis_home",
]
