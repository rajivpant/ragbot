"""Pluggable transport layer for the synthesis-engine MCP client.

A transport is responsible for creating the (read_stream, write_stream)
pair that :class:`mcp.ClientSession` consumes. The substrate ships three
transports — :mod:`stdio` for local servers, :mod:`http_sse` covering both
the legacy Server-Sent-Events transport and the 2025-11-25 Streamable
HTTP transport. The factory :func:`open_transport` selects the right one
based on the :class:`MCPServerConfig.transport` field.

Adding a new transport (e.g., WebSocket, in-process loopback) is a
single file implementing the async context-manager protocol that yields
``(read_stream, write_stream)``. Register it in :func:`open_transport`.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from synthesis_engine.exceptions import SynthesisError

from ..config import MCPServerConfig
from .http_sse import open_http_transport, open_sse_transport
from .stdio import open_stdio_transport


class MCPTransportError(SynthesisError):
    """Transport-level failure (process spawn, network connect, etc.)."""


@contextlib.asynccontextmanager
async def open_transport(
    server: MCPServerConfig,
    *,
    oauth_provider: Any | None = None,
) -> AsyncIterator[tuple[Any, Any]]:
    """Open the transport described by ``server.transport`` and yield streams.

    The yielded tuple is ``(read_stream, write_stream)`` — the exact shape
    :class:`mcp.ClientSession` accepts. The caller owns the streams for
    the duration of the ``async with`` block; on exit, the transport
    cleans up its underlying resources (process, HTTP session, etc.).
    """
    t = server.transport
    if t == "stdio":
        async with open_stdio_transport(server) as streams:
            yield streams
    elif t == "http":
        async with open_http_transport(server, oauth_provider=oauth_provider) as streams:
            yield streams
    elif t == "sse":
        async with open_sse_transport(server, oauth_provider=oauth_provider) as streams:
            yield streams
    else:  # pragma: no cover - validated upstream
        raise MCPTransportError(f"unsupported transport: {t}")


__all__ = [
    "MCPTransportError",
    "open_transport",
    "open_stdio_transport",
    "open_http_transport",
    "open_sse_transport",
]
