"""Stdio transport adapter.

Wraps :func:`mcp.client.stdio.stdio_client` so callers in this package
can treat every transport identically. Stdio is the default transport
for locally-installed MCP servers — the SDK launches the configured
binary, pipes JSON-RPC frames in and out, and tears the process down
when the context exits.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from mcp.client.stdio import StdioServerParameters, stdio_client

from ..config import MCPServerConfig


@contextlib.asynccontextmanager
async def open_stdio_transport(
    server: MCPServerConfig,
) -> AsyncIterator[tuple[Any, Any]]:
    """Spawn the configured stdio server and yield ``(read, write)``."""
    if not server.command:
        raise ValueError(f"stdio server {server.id!r} has no 'command' configured")
    params = StdioServerParameters(
        command=server.command,
        args=list(server.args),
        env=server.env or None,
        cwd=server.cwd,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        yield read_stream, write_stream


__all__ = ["open_stdio_transport"]
