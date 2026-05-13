"""Stdio-to-HTTP/SSE proxy.

Many MCP servers ship as stdio-default binaries: ``npx`` packages,
Python entry points, local Go binaries. Surface them to non-local
consumers (a remote agent, a browser tab) by running a small ASGI
application that:

1. Spawns the configured stdio server as a child process.
2. Exposes a Streamable-HTTP endpoint at ``/mcp``.
3. Relays JSON-RPC frames between the HTTP transport and the child's
   stdio.

The proxy is built on the SDK's :class:`StreamableHTTPSessionManager`,
which already implements the 2025-11-25 streamable-HTTP transport and
session handling correctly. We supply a backing ``MCPServer`` instance
that forwards every request and notification onto a long-lived
:class:`mcp.ClientSession` attached to the upstream stdio child.

Usage::

    from synthesis_engine.mcp.proxy import StdioHTTPProxy

    proxy = StdioHTTPProxy(server_config)
    asgi_app = proxy.asgi_app()  # mount under e.g. uvicorn or FastAPI

    # When the host process shuts down:
    await proxy.aclose()

The proxy does *not* terminate inbound TLS or perform authorization;
those concerns belong to the host process. What it does guarantee is
that the on-the-wire shape matches the spec, so a Streamable-HTTP
client (including our own ``open_http_transport``) can connect to the
proxied endpoint and exercise every primitive without knowing that a
stdio child is doing the actual work behind the scenes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.lowlevel import Server as MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import (
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    Tool,
)
from pydantic import AnyUrl

from .config import MCPServerConfig


logger = logging.getLogger("synthesis_engine.mcp.proxy")


class StdioHTTPProxy:
    """Wrap a stdio MCP server behind a Streamable-HTTP endpoint.

    The proxy lazily connects to the upstream stdio child on first
    request and keeps the connection open for subsequent calls. Call
    :meth:`aclose` when the host shuts down so the child process and
    its pipes are cleaned up.

    The exposed ASGI app speaks Streamable-HTTP (the 2025-11-25 wire
    transport) by default. A separate factory for legacy SSE can be
    added later if a consumer needs it; we have not seen a real-world
    use case in the v3.4 design that needs both surfaces from the same
    proxy instance.
    """

    def __init__(self, server: MCPServerConfig):
        if server.transport != "stdio":
            raise ValueError(
                f"StdioHTTPProxy only proxies stdio servers; got {server.transport}"
            )
        if not server.command:
            raise ValueError(f"server {server.id!r} has no 'command' configured")
        self.server = server
        self._upstream: Optional[ClientSession] = None
        self._upstream_ctx: Optional[Any] = None
        self._lock = asyncio.Lock()
        self._mcp_app = self._build_relay_app()
        self._manager = StreamableHTTPSessionManager(
            app=self._mcp_app,
            stateless=False,
            json_response=False,
        )

    # ------ upstream lifecycle ---------------------------------------------

    async def _ensure_upstream(self) -> ClientSession:
        async with self._lock:
            if self._upstream is not None:
                return self._upstream
            params = StdioServerParameters(
                command=self.server.command,
                args=list(self.server.args),
                env=self.server.env or None,
                cwd=self.server.cwd,
            )
            # The async-context-manager chain has to be kept alive for the
            # lifetime of the proxy; we juggle it as a driver task.
            ready = asyncio.Event()
            self._stopped = asyncio.Event()
            self._upstream_task = asyncio.create_task(
                self._upstream_driver(params, ready),
                name=f"mcp-proxy-upstream:{self.server.id}",
            )
            await ready.wait()
            assert self._upstream is not None
            return self._upstream

    async def _upstream_driver(
        self, params: StdioServerParameters, ready: asyncio.Event
    ) -> None:
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._upstream = session
                    ready.set()
                    await self._stopped.wait()
        except Exception:
            logger.exception("upstream stdio driver crashed")
            ready.set()
            raise
        finally:
            self._upstream = None

    async def aclose(self) -> None:
        """Tear down the upstream stdio child and HTTP manager."""
        async with self._lock:
            if hasattr(self, "_stopped"):
                self._stopped.set()
            if hasattr(self, "_upstream_task"):
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(self._upstream_task, timeout=5.0)

    # ------ relay ----------------------------------------------------------

    def _build_relay_app(self) -> MCPServer:
        """Construct an :class:`MCPServer` that forwards calls to the upstream."""

        srv: MCPServer[Any, Any] = MCPServer(
            name=f"proxy:{self.server.id}",
            version="0.1.0",
            instructions=(
                f"Streamable-HTTP proxy in front of stdio server "
                f"{self.server.command} {' '.join(self.server.args)}."
            ),
        )

        @srv.list_tools()
        async def _list_tools() -> list[Tool]:
            upstream = await self._ensure_upstream()
            tools: list[Tool] = []
            cursor = None
            while True:
                page: ListToolsResult = await upstream.list_tools(cursor=cursor)
                tools.extend(page.tools)
                cursor = page.nextCursor
                if not cursor:
                    return tools

        @srv.call_tool()
        async def _call_tool(name: str, arguments: dict[str, Any] | None) -> Any:
            upstream = await self._ensure_upstream()
            result = await upstream.call_tool(name=name, arguments=arguments or {})
            return result.content if result is not None else []

        @srv.list_resources()
        async def _list_resources() -> list[Resource]:
            upstream = await self._ensure_upstream()
            resources: list[Resource] = []
            cursor = None
            while True:
                page: ListResourcesResult = await upstream.list_resources(cursor=cursor)
                resources.extend(page.resources)
                cursor = page.nextCursor
                if not cursor:
                    return resources

        @srv.list_resource_templates()
        async def _list_templates() -> list:
            upstream = await self._ensure_upstream()
            out: list = []
            cursor = None
            while True:
                page: ListResourceTemplatesResult = (
                    await upstream.list_resource_templates(cursor=cursor)
                )
                out.extend(page.resourceTemplates)
                cursor = page.nextCursor
                if not cursor:
                    return out

        @srv.read_resource()
        async def _read_resource(uri: AnyUrl) -> ReadResourceResult:
            upstream = await self._ensure_upstream()
            return await upstream.read_resource(uri)

        @srv.list_prompts()
        async def _list_prompts() -> list[Prompt]:
            upstream = await self._ensure_upstream()
            prompts: list[Prompt] = []
            cursor = None
            while True:
                page: ListPromptsResult = await upstream.list_prompts(cursor=cursor)
                prompts.extend(page.prompts)
                cursor = page.nextCursor
                if not cursor:
                    return prompts

        @srv.get_prompt()
        async def _get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
            upstream = await self._ensure_upstream()
            return await upstream.get_prompt(name=name, arguments=arguments or {})

        return srv

    # ------ ASGI ------------------------------------------------------------

    def asgi_app(self):
        """Return an ASGI application speaking Streamable-HTTP.

        Mount under any ASGI host. Standalone use::

            import uvicorn
            uvicorn.run(proxy.asgi_app(), host="127.0.0.1", port=7575)

        Mount inside a larger FastAPI/Starlette app via
        ``app.mount("/mcp/<id>/", proxy.asgi_app())``.
        """
        manager = self._manager

        async def app(scope, receive, send):
            if scope["type"] == "lifespan":
                # Run the manager's lifespan so its task group is alive.
                async with manager.run():
                    while True:
                        message = await receive()
                        if message["type"] == "lifespan.startup":
                            await send({"type": "lifespan.startup.complete"})
                        elif message["type"] == "lifespan.shutdown":
                            await self.aclose()
                            await send({"type": "lifespan.shutdown.complete"})
                            return
            else:
                await manager.handle_request(scope, receive, send)

        return app


__all__ = ["StdioHTTPProxy"]
