# synthesis_engine.mcp — Model Context Protocol client substrate

This package implements the client side of the [Model Context Protocol](https://modelcontextprotocol.io)
on top of the official `mcp` Python SDK (>=1.27). It is the shared building
block that every synthesis-engineering runtime (Ragbot, Ragenie,
synthesis-console, future implementations) uses when it needs to connect
to MCP servers — local stdio binaries or remote HTTP/SSE endpoints — to
list and invoke tools, read resources, and fetch prompts.

The substrate intentionally stops at "connect and invoke." Higher-level
concerns — auth UX, settings UI, per-workspace policy presentation — live
in the runtime that consumes the substrate. The split keeps every
runtime parsing the same `~/.synthesis/mcp.yaml`, applying the same
allow/deny rules, and surfacing the same primitive set.

## Architecture

```
+-----------------+        +------------------+      +-----------------+
|   MCPClient     |  -->   |    MCPRegistry   | -->  |   ServerEntry   |
|  (orchestration)|        | (catalog + locks)|      |  (per-server)   |
+-----------------+        +------------------+      +-----------------+
                                                            |
                                  +-------------------------+--------------------------+
                                  v                         v                          v
                          +-------------+         +---------------+          +-------------------+
                          |  transport  |         | ClientSession |          |  primitives:      |
                          | stdio | http|         |   (SDK)       |          |  tools, resources |
                          |  | sse      |         +---------------+          |  prompts, roots,  |
                          +-------------+                  |                  |  sampling,        |
                                                           |                  |  elicitation      |
                                                           v                  +-------------------+
                                                  +-----------------+                 ^
                                                  |  auth (OAuth2.1 |                 |
                                                  | + DCR + CIMD)   |        +------------------+
                                                  +-----------------+        |  tasks (SEP-1686)|
                                                                             |  promote any req |
                                                                             +------------------+
```

Component responsibilities:

- **`MCPClient`** — process-singleton orchestration. Owns one
  `MCPRegistry`, threads sampling/elicitation/roots callbacks through to
  every session, and exposes a flat async API (`list_tools`, `call_tool`,
  `read_resource`, ...).
- **`MCPRegistry`** — in-memory catalog of configured servers and their
  live state. Concurrency-safe; per-entry locks guard mutating ops.
  Pre-warms the per-server catalog at connect time so the UI does not
  have to wait on `tools/list` for every render.
- **`transport/`** — three transports ship: `stdio` for local servers,
  `http` for the 2025-11-25 Streamable HTTP transport, `sse` for the
  legacy Server-Sent-Events transport. Adding a new one
  (WebSocket, in-process loopback) is a single file implementing the
  async-context-manager shape.
- **`primitives/`** — one module per primitive in the spec. Wrappers
  return SDK-native types; the substrate does not invent its own
  parallel hierarchy.
- **`auth.py`** — OAuth 2.1 with PKCE, Dynamic Client Registration (RFC
  7591), Client ID Metadata Document flow (preferred per the 2025-11-25
  spec), and a `DiskTokenStorage` that persists tokens to
  `~/.synthesis/mcp/tokens/`.
- **`tasks.py`** — the SEP-1686 Tasks API. Any request can be promoted
  to a task; the wrappers cover create, poll, get-result, cancel, and
  subscribe.
- **`proxy.py`** — `StdioHTTPProxy` wraps a stdio server behind a
  Streamable-HTTP endpoint so non-local consumers (a remote agent, a
  browser tab) can reach a locally-launched server.

## Configuration

The user's catalog of configured servers lives at
`~/.synthesis/mcp.yaml` (override via the `SYNTHESIS_HOME` env var, used
mainly by tests). The schema is enforced by `MCPConfig` /
`MCPServerConfig` in `config.py`.

```yaml
servers:
  - id: fs-local
    name: "Local Filesystem"
    description: "Read-only access under ~/workspaces"
    transport: stdio
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/workspaces"]
    # per-workspace gating (optional; omit for "everywhere")
    enabled_workspaces: ["*"]
    disabled_workspaces: ["client-acme"]

  - id: github-cloud
    name: "GitHub Cloud"
    description: "Hosted GitHub MCP server"
    transport: http
    url: "https://mcp.github.example.com"
    auth:
      mode: oauth
      client_id_metadata_url: "https://app.example.com/mcp/client.json"
      client_name: "Ragbot"
      scope: "repo:read"

defaults:
  timeout_seconds: 30
  enabled_by_default: true
```

### Per-workspace allow/deny

Two complementary fields:

- `enabled_workspaces` — a list of workspace names the server is enabled
  for. The literal `"*"` matches every workspace. Omitting the field
  entirely defers to `defaults.enabled_by_default`.
- `disabled_workspaces` — workspace names where the server is forcibly
  off. Deny beats allow.

`MCPClient.get_active_servers(workspace=...)` resolves these rules and
returns only the entries admitted for that workspace. The runtime's
discovery filter (see `synthesis_engine.discovery`) may override the
result under the `"mcp_servers"` scope.

## Python usage

```python
import asyncio
from synthesis_engine.mcp import MCPClient, load_mcp_config

async def main():
    config = load_mcp_config()
    async with MCPClient(config) as client:
        # List configured servers and their connection state.
        for entry in client.list_servers():
            print(entry.config.id, entry.status)

        # Discover and call a tool.
        tools = await client.list_tools("fs-local")
        for tool in tools:
            print(" -", tool.name)

        result = await client.call_tool(
            "fs-local",
            name="read_file",
            arguments={"path": "/Users/me/workspaces/README.md"},
        )
        for block in result.content:
            if getattr(block, "type", None) == "text":
                print(block.text)

asyncio.run(main())
```

The async context manager opens every server enabled for the current
workspace at entry and closes them at exit. For finer control —
connecting/disconnecting specific servers, switching workspaces mid-
process — call `client.connect(server_id)`, `client.disconnect(server_id)`,
or `client.toggle(server_id)` directly.

### Long-running tool calls — Tasks API

```python
res = await client.call_tool_as_task("svr", "compile_corpus", {})
task_id = res.task.task_id
status = await client.wait_for_task("svr", task_id)
payload = await client.task_result("svr", task_id)
```

## Spec references

- Model Context Protocol — <https://modelcontextprotocol.io>
- 2025-11-25 revision notes — <https://modelcontextprotocol.io/specification/2025-11-25>
- SEP-1686 (Tasks) — <https://github.com/modelcontextprotocol/specification>
- RFC 9728 (Protected Resource Metadata), RFC 7591 (Dynamic Client
  Registration), RFC 8707 (Resource Indicators) — referenced by the
  spec's authorization section.

## Public surface — quick index

| Symbol | Purpose |
| --- | --- |
| `MCPClient`, `get_default_client`, `set_default_client` | Top-level orchestration and singleton |
| `MCPConfig`, `MCPServerConfig`, `AuthConfig`, `MCPDefaults` | Validated config schema |
| `load_mcp_config`, `save_mcp_config`, `mcp_config_path`, `mcp_state_dir` | Config IO and path resolution |
| `MCPRegistry`, `ServerEntry`, `CachedCatalog`, `MCPRegistryError` | Lower-level registry (advanced) |
| `open_transport`, `open_stdio_transport`, `open_http_transport`, `open_sse_transport` | Transport factories |
| `build_oauth_provider`, `DiskTokenStorage`, `LocalBrowserOAuthFlow`, `MCPAuthError` | OAuth plumbing |
| `list_tools`, `call_tool`, `list_resources`, `read_resource`, `subscribe_resource`, `list_prompts`, `get_prompt`, ... | Per-primitive helpers |
| `tasks.call_tool_as_task`, `tasks.get_status`, `tasks.get_result`, `tasks.cancel`, `tasks.poll_until_done` | Tasks API |
| `StdioHTTPProxy` | Wrap a stdio server behind a Streamable-HTTP endpoint |
| `SCOPE_MCP_SERVERS` | Discovery-filter scope key |
