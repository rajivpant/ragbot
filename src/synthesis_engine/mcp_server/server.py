"""RagbotMCPServer — wraps :class:`mcp.server.lowlevel.Server`.

This module is the transport-level adapter. It binds the tool and
resource handlers defined in :mod:`.tools` and :mod:`.resources` to a
:class:`mcp.server.lowlevel.Server`, then exposes two ways to serve
that server to an external client:

* :meth:`RagbotMCPServer.serve_stdio` — blocks on stdin/stdout. The
  standard transport for desktop integrations (Claude Code, Cursor,
  ChatGPT desktop). Auth is process-local; the parent process is
  trusted.

* :meth:`RagbotMCPServer.serve_http` — serves the same handlers over
  Streamable HTTP (the 2025-11-25 MCP transport). Bearer-token auth is
  enforced via the per-server config at ``~/.synthesis/mcp-server.yaml``.
  The handler raises :class:`MCPServerAuthError` and refuses to start
  when the config is missing or malformed.

The class is intentionally a thin shell. Every protocol-level concern
(transport, framing, JSON validation, schema enforcement) is the SDK's
responsibility. Every tool-level concern (dispatch, permission, policy)
lives in :mod:`.tools`. Every resource-level concern (URI parsing,
content materialisation) lives in :mod:`.resources`. The server is the
glue that puts those layers behind one MCP-compliant socket.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import os
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    AnyUrl,
    Resource,
    TextContent,
    Tool,
)

from ..policy.audit import read_recent as audit_read_recent  # noqa: F401  # re-export for tests
from .auth import (
    BearerToken,
    MCPServerAuthConfig,
    MCPServerAuthError,
    load_auth_config,
)
from .resources import (
    ResourceProvider,
    list_all_resources,
    read_resource_contents,
)
from .tools import (
    TOOL_DEFINITIONS,
    ToolDispatchContext,
    ToolDispatchError,
    dispatch_tool,
)


logger = logging.getLogger(__name__)


# ContextVar holding the current request's bearer-token entry. The
# Streamable-HTTP transport sets it inside its ASGI handler before
# invoking the MCP session's request loop, so the tool handlers can pick
# up the per-request entry without changing the SDK's call_tool
# signature. Stdio mode never sets it, which is how the tool dispatcher
# distinguishes "no auth needed" from "bearer present."
_CURRENT_BEARER: contextvars.ContextVar[Optional[BearerToken]] = (
    contextvars.ContextVar("ragbot_mcp_bearer", default=None)
)


# ---------------------------------------------------------------------------
# Server dependencies
# ---------------------------------------------------------------------------


@dataclass
class ServerDependencies:
    """Runtime collaborators required by :class:`RagbotMCPServer`.

    All collaborators are passed in by the caller (typically a FastAPI
    lifespan handler in production, or a test fixture). The server
    never imports the substrate's process-singletons; this keeps the
    server testable in isolation and makes the wiring explicit at the
    composition root.

    Attributes:
        memory:               Substrate :class:`Memory` backend.
        skill_runtime:        :class:`SkillRuntime` for ``skill_run``.
        skills_visible_for:   Callable ``workspace -> List[Skill]``.
        list_workspaces:      Callable ``() -> Iterable[str]`` returning
                              every known workspace name.
        routing_policies:     Callable ``workspace -> RoutingPolicy``.
        document_getter:      Callable ``(workspace, document_id) -> dict``.
        agent_run_starter:    Async callable ``(workspaces, task, rubric)
                              -> (task_id, status_url)``.
        permission_registry:  Optional :class:`PermissionRegistry` for
                              cross-cutting policy.
        audit_limit:          Max audit entries surfaced through the
                              ``synthesis://audit/recent`` resource.
        status_url_template:  Template for the status URL returned from
                              ``agent_run_start``.
        retrieve_single:      Test seam for the single-workspace
                              retriever. Defaults to the real one.
        retrieve_multi:       Test seam for the multi-workspace
                              retriever. Defaults to the real one.
    """

    memory: Any
    skill_runtime: Any
    skills_visible_for: Callable[[str], Iterable[Any]]
    list_workspaces: Callable[[], Iterable[str]]
    routing_policies: Callable[[str], Any]
    document_getter: Callable[[str, str], Dict[str, Any]]
    agent_run_starter: Callable[
        [Tuple[str, ...], str, Optional[str]], Awaitable[Tuple[str, str]]
    ]
    permission_registry: Optional[Any] = None
    audit_limit: int = 200
    status_url_template: str = "/api/agent/sessions/{task_id}"
    retrieve_single: Optional[Callable[..., List[Any]]] = None
    retrieve_multi: Optional[Callable[..., List[Any]]] = None


# ---------------------------------------------------------------------------
# RagbotMCPServer
# ---------------------------------------------------------------------------


class RagbotMCPServer:
    """Expose Ragbot's primitives as an MCP server.

    Construction
    ------------

    The server is constructed with a :class:`ServerDependencies`
    instance. The dependencies object is the single seam between the
    substrate (memory, skills, policy, agent loop) and this adapter.
    """

    DEFAULT_NAME = "ragbot"

    def __init__(
        self,
        dependencies: ServerDependencies,
        *,
        name: str = DEFAULT_NAME,
        version: str = "1.0.0",
    ) -> None:
        self._deps = dependencies
        self._server: Server = Server(name=name, version=version)
        self._resource_provider = ResourceProvider(
            list_workspaces=dependencies.list_workspaces,
            skills_for=lambda ws: list(dependencies.skills_visible_for(ws)),
            routing_policy_for=dependencies.routing_policies,
            audit_limit=dependencies.audit_limit,
        )
        self._register_handlers()

    # ------ public introspection -------------------------------------------

    @property
    def server(self) -> Server:
        """The underlying SDK :class:`Server` instance.

        Exposed so tests and the HTTP transport can reach into it for
        capabilities, initialisation options, and the in-memory test
        helper from ``mcp.shared.memory``.
        """
        return self._server

    @property
    def dependencies(self) -> ServerDependencies:
        return self._deps

    def tools(self) -> Tuple[Tool, ...]:
        """Return the static tool definitions surfaced by this server."""
        return TOOL_DEFINITIONS

    # ------ handler registration -------------------------------------------

    def _register_handlers(self) -> None:
        """Wire the SDK decorators to dispatch into this module's helpers."""
        server = self._server

        @server.list_tools()
        async def _list_tools() -> List[Tool]:  # pragma: no cover - small shim
            return list(TOOL_DEFINITIONS)

        @server.call_tool()
        async def _call_tool(
            name: str, arguments: Dict[str, Any]
        ) -> Dict[str, Any]:
            ctx = self._build_dispatch_context(_CURRENT_BEARER.get())
            try:
                return await dispatch_tool(name, arguments or {}, ctx)
            except ToolDispatchError as exc:
                # Surface the dispatch error as a tool error result so
                # the SDK turns it into a CallToolResult(isError=True).
                # We re-raise as a plain Exception with the same message
                # so the SDK's wrapper does that translation.
                raise RuntimeError(f"[{exc.code}] {exc}") from exc

        @server.list_resources()
        async def _list_resources() -> List[Resource]:
            return list_all_resources(self._resource_provider)

        @server.read_resource()
        async def _read_resource(uri: AnyUrl) -> Iterable[Any]:
            try:
                return list(
                    read_resource_contents(self._resource_provider, str(uri))
                )
            except LookupError as exc:
                raise ValueError(str(exc)) from exc

    def _build_dispatch_context(
        self, bearer: Optional[BearerToken]
    ) -> ToolDispatchContext:
        """Compose a :class:`ToolDispatchContext` for one request."""
        deps = self._deps
        return ToolDispatchContext(
            memory=deps.memory,
            skill_runtime=deps.skill_runtime,
            skills_visible_for=lambda ws: list(deps.skills_visible_for(ws)),
            document_getter=deps.document_getter,
            agent_run_starter=deps.agent_run_starter,
            routing_policies=deps.routing_policies,
            permission_registry=deps.permission_registry,
            bearer_token=bearer,
            retrieve_single=deps.retrieve_single,
            retrieve_multi=deps.retrieve_multi,
            status_url_template=deps.status_url_template,
        )

    # ------ transport: stdio -----------------------------------------------

    async def serve_stdio(self) -> None:
        """Serve the MCP server over stdin/stdout. Auth is bypassed.

        Stdio is process-local: the client (Claude Code, Cursor, etc.)
        spawned this process and shares its security boundary. No
        bearer token is consulted; the current bearer ContextVar is
        left at its default ``None`` so the tool dispatcher recognises
        the stdio-trust path.
        """
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )

    # ------ transport: HTTP/SSE --------------------------------------------

    async def serve_http(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        auth_config: Optional[MCPServerAuthConfig] = None,
        config_path: Optional[str] = None,
    ) -> None:
        """Serve the MCP server over Streamable HTTP with bearer-token auth.

        Args:
            host: Bind host. Defaults to localhost so a misconfigured
                deployment does not silently expose the server to the
                public internet.
            port: Bind port.
            auth_config: Pre-loaded auth config. When omitted the
                method calls :func:`load_auth_config` with
                ``require=True``; the call raises
                :class:`MCPServerAuthError` when
                ``~/.synthesis/mcp-server.yaml`` is missing or
                malformed.
            config_path: Optional override for the auth-config path.
                Passed through to :func:`load_auth_config`.

        Raises:
            MCPServerAuthError: when the HTTP-mode auth config cannot
                be loaded. Fail-closed; the server does not start.

        Note:
            The Streamable HTTP transport is wired through
            :class:`StreamableHTTPSessionManager`. The server is
            mounted under an ASGI app inside this method so a deployer
            can reuse it behind their own HTTP layer (FastAPI, Hypercorn,
            etc.). The default in-process Uvicorn binding is the
            simplest standalone path. Use :meth:`asgi_app_factory` if
            you need to embed the server inside an existing ASGI app.
        """
        if auth_config is None:
            cfg_path = (
                None if config_path is None else os.path.expanduser(config_path)
            )
            from pathlib import Path

            auth_config = load_auth_config(
                require=True,
                config_path=Path(cfg_path) if cfg_path else None,
            )
        # An empty token list would have raised inside load_auth_config
        # when require=True; assert here for defence in depth.
        if auth_config is None or not auth_config.tokens:
            raise MCPServerAuthError(
                "HTTP/SSE transport requires at least one bearer token. "
                "Add one to ~/.synthesis/mcp-server.yaml and restart."
            )

        # Lazy import: uvicorn is only needed for the default in-process
        # binding. Embedding the server in an existing ASGI app uses
        # :meth:`asgi_app_factory` and never imports uvicorn here.
        import uvicorn

        app = self.asgi_app_factory(auth_config=auth_config)
        config = uvicorn.Config(
            app=app, host=host, port=port, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    def asgi_app_factory(
        self, *, auth_config: MCPServerAuthConfig
    ) -> Callable[..., Awaitable[None]]:
        """Return an ASGI callable that serves this MCP server.

        The factory wraps the Streamable HTTP transport with a
        bearer-token middleware. The middleware reads the
        ``Authorization`` header, resolves it against ``auth_config``,
        and stores the resolved :class:`BearerToken` in the
        :data:`_CURRENT_BEARER` ContextVar before forwarding to the
        transport's own ASGI handler. Unauthenticated requests get a
        401 with a clear remediation message.
        """
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        manager = StreamableHTTPSessionManager(app=self._server)

        async def asgi_app(scope: Dict[str, Any], receive: Any, send: Any) -> None:
            if scope.get("type") != "http":
                await manager.handle_request(scope, receive, send)
                return
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in (scope.get("headers") or [])
            }
            bearer = auth_config.authenticate_bearer(
                headers.get("authorization")
            )
            if bearer is None:
                body = (
                    b'{"error":"unauthorized",'
                    b'"detail":"Missing or invalid bearer token. '
                    b'Authorization: Bearer <token>."}'
                )
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"www-authenticate", b'Bearer realm="ragbot-mcp"'),
                        ],
                    }
                )
                await send(
                    {"type": "http.response.body", "body": body}
                )
                return
            token_var_token = _CURRENT_BEARER.set(bearer)
            try:
                await manager.handle_request(scope, receive, send)
            finally:
                _CURRENT_BEARER.reset(token_var_token)

        return asgi_app

    # ------ test helpers ----------------------------------------------------

    def set_current_bearer_for_test(
        self, bearer: Optional[BearerToken]
    ) -> contextvars.Token:
        """Install ``bearer`` as the current request's token.

        Tests use this to simulate a per-request HTTP context without
        spinning up the actual ASGI transport. Returns the ContextVar
        token so the test can call :func:`contextvars.ContextVar.reset`
        afterwards.
        """
        return _CURRENT_BEARER.set(bearer)

    @staticmethod
    def reset_current_bearer_for_test(token: contextvars.Token) -> None:
        """Restore the previous ContextVar state set by
        :meth:`set_current_bearer_for_test`."""
        _CURRENT_BEARER.reset(token)


# ---------------------------------------------------------------------------
# Convenience: build a default agent-run starter from an AgentLoop
# ---------------------------------------------------------------------------


def make_agent_run_starter_from_loop(
    loop: Any,
    *,
    status_url_template: str = "/api/agent/sessions/{task_id}",
) -> Callable[
    [Tuple[str, ...], str, Optional[str]], Awaitable[Tuple[str, str]]
]:
    """Build an ``agent_run_starter`` callable wrapping an :class:`AgentLoop`.

    The returned async callable matches the contract expected by
    :class:`ServerDependencies.agent_run_starter`. It mirrors the
    background-task pattern in :mod:`api.routers.agent`: build an
    initial :class:`GraphState`, save it via the loop's checkpoint
    store, kick off ``drive_to_terminal`` as a background asyncio task,
    and return the new task id.
    """
    from ..agent import AgentState, GraphState  # local import to avoid cycle

    async def _starter(
        workspaces: Tuple[str, ...],
        task: str,
        rubric: Optional[str],
    ) -> Tuple[str, str]:
        state = GraphState.new(task)
        if workspaces:
            state.metadata["workspaces"] = list(workspaces)
        if rubric:
            state.metadata["rubric"] = rubric
            state.metadata["pending_grade"] = True
        state.add_turn(state.current_state, "MCP-initiated agent run.")
        await loop.checkpoint_store.save(state)

        async def _drive() -> None:
            try:
                await loop.drive_to_terminal(state)
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "MCP-initiated agent run %s raised", state.task_id
                )

        asyncio.create_task(_drive())
        status_url = status_url_template.format(task_id=state.task_id)
        return state.task_id, status_url

    return _starter


__all__ = [
    "RagbotMCPServer",
    "ServerDependencies",
    "make_agent_run_starter_from_loop",
]
