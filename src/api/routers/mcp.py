"""Model Context Protocol (MCP) API endpoints.

REST surface for managing MCP server connections from the web UI and any
other front-end that consumes the FastAPI app. The router is a thin
adapter around :mod:`synthesis_engine.mcp`: every endpoint resolves the
process-wide :class:`MCPClient` (the substrate's singleton), then asks
the registry to do the work.

Endpoints:

    GET    /api/mcp/servers                       list configured servers
    POST   /api/mcp/servers                       add or replace a server
    DELETE /api/mcp/servers/{server_id}           remove a server
    POST   /api/mcp/servers/{server_id}/toggle    connect or disconnect
    POST   /api/mcp/servers/{server_id}/oauth     trigger/refresh OAuth flow
    GET    /api/mcp/servers/{server_id}/tools     list tools (live)
    GET    /api/mcp/servers/{server_id}/resources list resources (live)
    GET    /api/mcp/servers/{server_id}/prompts   list prompts (live)

Workspace gating is exposed as a ``workspace`` query parameter on the
list endpoint, so the UI can render "what's available for the current
workspace" without re-implementing the per-workspace allow/deny logic.

The router does not authenticate callers. Ragbot's single-user threat
model is the same as for the memory router; multi-user auth is a
separate concern.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

# Add src/ to sys.path so synthesis_engine is importable when this
# module is loaded outside the FastAPI application (e.g., in tests).
_SRC = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.exceptions import ConfigurationError
from synthesis_engine.mcp import (
    AuthConfig,
    MCPClient,
    MCPConfig,
    MCPServerConfig,
    get_default_client,
    load_mcp_config,
    save_mcp_config,
    set_default_client,
)
from synthesis_engine.mcp.registry import MCPRegistryError, ServerEntry


logger = logging.getLogger("api.routers.mcp")

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_client() -> MCPClient:
    """Resolve the process-wide :class:`MCPClient`, building one on first use.

    The substrate exposes a singleton through
    :func:`get_default_client` / :func:`set_default_client`. The first
    caller into the router installs a client constructed from the on-disk
    ``~/.synthesis/mcp.yaml``. Subsequent calls reuse it. Tests can
    override the singleton before issuing requests; the override wins
    because :func:`get_default_client` is consulted on every call.
    """
    client = get_default_client()
    if client is not None:
        return client
    try:
        config = load_mcp_config()
    except ConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"failed to load mcp.yaml: {exc}",
        ) from exc
    # ``autoconnect=False`` because the router-driven flow opens connections
    # explicitly via the toggle endpoint. The lifespan-managed startup path
    # may construct a different client with ``autoconnect=True``; whichever
    # is installed first wins.
    client = MCPClient(config, autoconnect=False)
    set_default_client(client)
    return client


def _serialize_entry(entry: ServerEntry) -> Dict[str, Any]:
    """Return a JSON-friendly view of a :class:`ServerEntry`.

    Strips the live ``session`` object (not serialisable) and exposes the
    cached catalog sizes so the UI can render a summary without fetching
    each list separately. The full server config is round-tripped through
    ``model_dump`` so the bearer token / auth secrets stay where the user
    put them — we don't redact here because Ragbot is single-user; a
    multi-user version would filter the response.
    """
    cfg = entry.config
    return {
        "id": cfg.id,
        "name": cfg.name,
        "description": cfg.description,
        "transport": cfg.transport,
        "command": cfg.command,
        "args": list(cfg.args),
        "env": dict(cfg.env),
        "cwd": cfg.cwd,
        "url": cfg.url,
        "headers": dict(cfg.headers),
        "enabled_workspaces": (
            list(cfg.enabled_workspaces) if cfg.enabled_workspaces is not None else None
        ),
        "disabled_workspaces": list(cfg.disabled_workspaces),
        "auth": cfg.auth.model_dump(),
        "timeout_seconds": cfg.timeout_seconds,
        "enabled": cfg.enabled,
        "status": entry.status,
        "last_error": entry.last_error,
        "capabilities": (
            entry.capabilities.model_dump() if entry.capabilities is not None else None
        ),
        "catalog_sizes": {
            "tools": len(entry.catalog.tools),
            "resources": len(entry.catalog.resources),
            "prompts": len(entry.catalog.prompts),
        },
    }


def _model_to_dict(obj: Any) -> Any:
    """Best-effort conversion of pydantic models / lists / dicts to JSON-safe data."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_model_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _model_to_dict(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ServerUpsertRequest(BaseModel):
    """Body for POST /api/mcp/servers (add or replace by id)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    transport: str = "stdio"

    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None

    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)

    enabled_workspaces: Optional[List[str]] = None
    disabled_workspaces: List[str] = Field(default_factory=list)

    auth: Optional[Dict[str, Any]] = None

    timeout_seconds: int = 30
    enabled: bool = True

    @field_validator("transport")
    @classmethod
    def _validate_transport(cls, v: str) -> str:
        if v not in ("stdio", "http", "sse"):
            raise ValueError("transport must be one of: stdio, http, sse")
        return v

    def to_server_config(self) -> MCPServerConfig:
        """Translate the request body into a substrate-validated config."""
        auth_payload = self.auth or {"mode": "none"}
        try:
            auth_cfg = AuthConfig.model_validate(auth_payload)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"invalid auth config: {exc}",
            ) from exc

        # Required-field enforcement keyed off the transport. The substrate
        # validates these at construction time too, but raising HTTP 400
        # here gives the UI a friendlier shape than a 500.
        if self.transport == "stdio" and not self.command:
            raise HTTPException(
                status_code=400,
                detail="stdio transport requires a 'command'",
            )
        if self.transport in ("http", "sse") and not self.url:
            raise HTTPException(
                status_code=400,
                detail=f"{self.transport} transport requires a 'url'",
            )

        try:
            return MCPServerConfig(
                id=self.id,
                name=self.name,
                description=self.description,
                transport=self.transport,  # type: ignore[arg-type]
                command=self.command,
                args=list(self.args),
                env=dict(self.env),
                cwd=self.cwd,
                url=self.url,
                headers=dict(self.headers),
                enabled_workspaces=(
                    list(self.enabled_workspaces)
                    if self.enabled_workspaces is not None else None
                ),
                disabled_workspaces=list(self.disabled_workspaces),
                auth=auth_cfg,
                timeout_seconds=self.timeout_seconds,
                enabled=self.enabled,
            )
        except Exception as exc:  # pydantic validation error
            raise HTTPException(
                status_code=400,
                detail=f"invalid server config: {exc}",
            ) from exc


# ---------------------------------------------------------------------------
# Servers — CRUD
# ---------------------------------------------------------------------------


@router.get("/servers")
async def list_servers(
    workspace: Optional[str] = Query(
        default=None,
        description="Filter to servers enabled for this workspace.",
    ),
) -> Dict[str, Any]:
    """List configured MCP servers with their current connection state.

    Without ``workspace``: returns every configured server.
    With ``workspace``: returns only servers admitted by the per-workspace
    allow/deny rules. The response shape is the same in either case so
    the UI can pivot between "all servers" and "active here" without
    parsing two payloads.
    """
    client = _require_client()
    entries = (
        client.get_active_servers(workspace)
        if workspace is not None
        else client.list_servers()
    )
    return {
        "servers": [_serialize_entry(e) for e in entries],
        "workspace": workspace,
    }


@router.post("/servers")
async def upsert_server(body: ServerUpsertRequest = Body(...)) -> Dict[str, Any]:
    """Add a new server, or replace an existing one with the same id.

    The server is added to the on-disk config (``~/.synthesis/mcp.yaml``)
    and to the live registry. The live registry's existing connections
    for unchanged servers are preserved; if a server's config changes
    while a connection is open, the new config is associated but the
    connection is not restarted — toggle to apply.
    """
    client = _require_client()
    new_server = body.to_server_config()

    # Update the in-memory config: replace by id, otherwise append.
    config = client.config
    remaining = [s for s in config.servers if s.id != new_server.id]
    remaining.append(new_server)
    next_config = MCPConfig(servers=remaining, defaults=config.defaults)

    # Persist before swapping; if disk write fails the live state is
    # unchanged and the UI sees the failure.
    try:
        save_mcp_config(next_config)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"failed to persist mcp.yaml: {exc}",
        ) from exc

    client.replace_config(next_config)
    entry = client.registry.get_entry(new_server.id)
    return _serialize_entry(entry)


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str) -> Dict[str, Any]:
    """Disconnect (if connected) and remove a configured server."""
    client = _require_client()
    config = client.config
    if not any(s.id == server_id for s in config.servers):
        raise HTTPException(
            status_code=404,
            detail=f"server not found: {server_id}",
        )

    # Disconnect first — replace_config drops the entry from the registry
    # immediately, so the driver task needs to finish before the entry is
    # forgotten or it will keep the underlying transport open.
    try:
        await client.disconnect(server_id)
    except MCPRegistryError:
        # registry entry already gone or never existed; not fatal here
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("disconnect during delete failed for %s: %s", server_id, exc)

    next_config = MCPConfig(
        servers=[s for s in config.servers if s.id != server_id],
        defaults=config.defaults,
    )
    try:
        save_mcp_config(next_config)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"failed to persist mcp.yaml: {exc}",
        ) from exc
    client.replace_config(next_config)
    return {"deleted": server_id}


# ---------------------------------------------------------------------------
# Connection control
# ---------------------------------------------------------------------------


@router.post("/servers/{server_id}/toggle")
async def toggle_server(server_id: str) -> Dict[str, Any]:
    """Connect ``server_id`` if disconnected, otherwise disconnect it.

    Returns the post-toggle entry so the UI can render the new state
    without an extra round trip.
    """
    client = _require_client()
    try:
        entry = await client.toggle(server_id)
    except MCPRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        # The driver task surfaces connection-time exceptions through
        # the registry. A 502 is the closest match: the API works, but
        # the upstream MCP server refused us.
        logger.exception("toggle failed for %s", server_id)
        raise HTTPException(
            status_code=502,
            detail=f"toggle failed: {type(exc).__name__}: {exc}",
        ) from exc
    return _serialize_entry(entry)


@router.post("/servers/{server_id}/oauth")
async def trigger_oauth(server_id: str) -> Dict[str, Any]:
    """Trigger (or refresh) the OAuth browser flow for a remote server.

    The substrate's :func:`build_oauth_provider` wires an
    ``OAuthClientProvider`` into the transport whenever a server has
    ``auth.mode == "oauth"``; the provider consumes any cached tokens on
    disk and, if none are valid, drives the loopback browser dance via
    :class:`LocalBrowserOAuthFlow`. This endpoint disconnects an active
    session first so the next connect goes through that authorization
    path cleanly, then reconnects and reports the outcome.

    The UI shape (``{"ok": bool, "error"?: str}``) is intentionally
    distinct from the toggle endpoint's serialized entry: callers usually
    poll :func:`list_servers` to watch the ``connecting → connected``
    transition rather than parse the OAuth result directly.
    """
    client = _require_client()

    try:
        entry = client.registry.get_entry(server_id)
    except MCPRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if entry.config.transport == "stdio":
        raise HTTPException(
            status_code=400,
            detail=(
                f"server {server_id!r} uses stdio transport; "
                "OAuth applies only to http/sse transports"
            ),
        )
    if entry.config.auth.mode != "oauth":
        raise HTTPException(
            status_code=400,
            detail=(
                f"server {server_id!r} is not OAuth-mode "
                f"(auth.mode={entry.config.auth.mode!r}); "
                "no OAuth flow to trigger"
            ),
        )

    # Force a fresh handshake. If the existing session is healthy this
    # appears as a brief connecting/connected blip in the UI; if tokens
    # have expired and refresh fails the next connect kicks the user
    # through the loopback flow.
    if entry.status == "connected":
        try:
            await client.disconnect(server_id)
        except MCPRegistryError:
            # Registry forgot the entry between checks — fine; treat as
            # already disconnected and proceed to connect.
            pass
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "disconnect-before-oauth failed for %s: %s", server_id, exc
            )

    try:
        await client.connect(server_id)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        logger.warning("OAuth handshake failed for %s: %s", server_id, msg)
        return {"ok": False, "error": msg}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Primitive catalogs
# ---------------------------------------------------------------------------


def _require_connected_entry(client: MCPClient, server_id: str) -> ServerEntry:
    """Resolve ``server_id`` to an entry, raising clear HTTPExceptions otherwise."""
    try:
        entry = client.registry.get_entry(server_id)
    except MCPRegistryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if entry.status != "connected":
        raise HTTPException(
            status_code=409,
            detail=(
                f"server {server_id!r} is not connected "
                f"(status={entry.status}); toggle it first"
            ),
        )
    return entry


@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str) -> Dict[str, Any]:
    """Return the tool catalog the server advertises (live query)."""
    client = _require_client()
    _require_connected_entry(client, server_id)
    try:
        tools = await client.list_tools(server_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"list_tools failed: {type(exc).__name__}: {exc}",
        ) from exc
    return {"server_id": server_id, "tools": _model_to_dict(tools)}


@router.get("/servers/{server_id}/resources")
async def list_server_resources(server_id: str) -> Dict[str, Any]:
    """Return the resource catalog the server advertises (live query)."""
    client = _require_client()
    _require_connected_entry(client, server_id)
    try:
        resources = await client.list_resources(server_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"list_resources failed: {type(exc).__name__}: {exc}",
        ) from exc
    return {"server_id": server_id, "resources": _model_to_dict(resources)}


@router.get("/servers/{server_id}/prompts")
async def list_server_prompts(server_id: str) -> Dict[str, Any]:
    """Return the prompt catalog the server advertises (live query)."""
    client = _require_client()
    _require_connected_entry(client, server_id)
    try:
        prompts = await client.list_prompts(server_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"list_prompts failed: {type(exc).__name__}: {exc}",
        ) from exc
    return {"server_id": server_id, "prompts": _model_to_dict(prompts)}
