"""HTTP/SSE transport adapters.

Covers two related but distinct wire transports:

* **Streamable HTTP** — the 2025-11-25 transport. Single endpoint, full
  duplex via HTTP POSTs from the client and SSE streams from the server.
  Used when ``server.transport == "http"``.
* **Legacy SSE** — the original MCP HTTP transport. A persistent
  ``GET /sse`` opens the read channel and the client sends each message
  as a separate POST. Retained because plenty of MCP servers in May 2026
  still offer it as their primary endpoint. Used when
  ``server.transport == "sse"``.

Both delegate to the official SDK helpers. They additionally compose
``OAuthClientProvider`` (when configured) and any static headers from
the server entry into a single httpx.Auth + headers pair so the caller
need not know which auth path is in play.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from ..auth import static_headers_for
from ..config import MCPServerConfig


@contextlib.asynccontextmanager
async def open_http_transport(
    server: MCPServerConfig,
    *,
    oauth_provider: Any | None = None,
) -> AsyncIterator[tuple[Any, Any]]:
    """Open a Streamable HTTP transport against ``server.url``."""
    if not server.url:
        raise ValueError(f"http server {server.id!r} has no 'url' configured")
    headers = static_headers_for(server)
    async with streamablehttp_client(
        server.url,
        headers=headers or None,
        timeout=server.timeout_seconds,
        auth=oauth_provider,
    ) as (read_stream, write_stream, _session_id_getter):
        # The third element is a callback for retrieving the streamable-http
        # session id; we do not surface it through the substrate API because
        # ClientSession-level features supersede that information.
        yield read_stream, write_stream


@contextlib.asynccontextmanager
async def open_sse_transport(
    server: MCPServerConfig,
    *,
    oauth_provider: Any | None = None,
) -> AsyncIterator[tuple[Any, Any]]:
    """Open a legacy SSE transport against ``server.url``."""
    if not server.url:
        raise ValueError(f"sse server {server.id!r} has no 'url' configured")
    headers = static_headers_for(server)
    async with sse_client(
        server.url,
        headers=headers or None,
        timeout=float(server.timeout_seconds),
        auth=oauth_provider,
    ) as (read_stream, write_stream):
        yield read_stream, write_stream


__all__ = ["open_http_transport", "open_sse_transport"]
