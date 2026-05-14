# v3.4 Screenshot Capture Procedure

This file is the operator's checklist for capturing the v3.4 screenshots
referenced in [`docs/release-notes-v3.4.0.md`](../release-notes-v3.4.0.md)
and in the ragbot.ai homepage hero. The screenshot script at
[`scripts/capture-screenshots.sh`](../../scripts/capture-screenshots.sh)
prepares the stack in demo mode and prints the URL list with the
recommended viewport for each shot.

Screenshots are captured manually via the browser, not automatically.
This is intentional: the v3.4 UI surfaces include hover states, focus
rings, and animation that look right when a human composes them and
look wrong when an automated tool snaps them mid-transition.

## Prerequisites

- Docker Desktop or compatible runtime
- A working Ragbot stack — see [`INSTALL.md`](../../INSTALL.md)
- API keys configured in `~/.synthesis/keys.yaml` for at least one
  frontier provider (so the demo workspace can render real responses)
- A browser at recommended viewport `1440x900` for documentation
  captures; `2880x1800` for hero captures on a Retina display.

## One-time setup before capture

```bash
cd /path/to/ragbot
./scripts/capture-screenshots.sh
```

The script:

1. Starts the stack with `RAGBOT_DEMO=1 docker compose up -d`.
2. Waits for `/health` to return `demo_mode: true`.
3. Prints the URL list with the recommended viewport for each shot.
4. Does **not** take any screenshot itself. That step is manual.

When capture is done, stop the stack with `docker compose down`.

## Filename convention

`docs/screenshots/<surface>.png` for documentation captures (1440x900).
`docs/screenshots/hero/<surface>@2x.png` for Retina hero captures
(2880x1800), if any.

All filenames use kebab-case and match the placeholder filenames in
this directory exactly so the docs render without broken-image links
when the placeholders get replaced with real captures.

## Capture checklist

Each row is one screenshot. Set the browser viewport to **1440x900**
(or to your Retina equivalent), open the route, set the demo state
described, then capture.

### 1. Agent panel with multi-workspace

- **Filename:** `agent-panel.png`
- **Route:** `http://localhost:3000/`
- **Demo state:**
  - Open the workspace selector (`⌘J`); select `acme-news` and
    `acme-user` (the two demo workspaces).
  - Open the model picker (`⌘K`); pin `Claude Opus 4.7` and
    `Qwen3 27B (local)`.
  - In the agent panel toggle, set `Agent loop: on`.
  - Send the message: `Summarize the most recent decisions across both
    workspaces with citations.`
  - Wait for the agent to produce a multi-step plan with a sub-agent
    dispatch and citations visible in the response.
- **Capture state:** Agent response complete, sub-agent badge visible,
  per-step trace expanded inline.

### 2. MCP settings panel

- **Filename:** `mcp-settings.png`
- **Route:** Click the gear icon → Settings → MCP servers tab.
- **Demo state:**
  - Demo mode ships with two pre-configured MCP server entries
    (filesystem and a stub Slack-compatible server).
  - Both should show green "connected" status.
  - Expand the filesystem server entry to show its exposed tools
    (`list_directory`, `read_file`, etc.).
- **Capture state:** Two server entries visible, one expanded showing
  the tool list. The per-server toggle and per-workspace allow/deny
  affordances are visible.

### 3. Skills panel

- **Filename:** `skills-panel.png`
- **Route:** Settings → Skills tab.
- **Demo state:**
  - All six starter-pack skills visible: `workspace-search-with-citations`,
    `draft-and-revise`, `fact-check-claims`, `summarize-document`,
    `agent-self-review`, `cross-workspace-synthesis`.
  - Click `cross-workspace-synthesis` to expand its detail panel.
  - The detail panel shows the input schema, output schema, and the
    "Run with current workspaces" button.
- **Capture state:** Six skill cards, one expanded with the detail
  panel and the "Run" affordance visible.

### 4. Policy panel (cross-workspace + routing)

- **Filename:** `policy-panel.png`
- **Route:** Settings → Policy tab.
- **Demo state:**
  - Workspaces section shows `acme-news` (tagged `client-confidential`,
    yellow ink) and `acme-user` (tagged `personal`, neutral ink).
  - Click the `acme-news` row to expand; its `routing.yaml` editor
    shows the local-only allowed-models list and `DENY` fallback.
  - The cross-workspace check widget at the bottom shows the pairwise
    mix for `[acme-news, acme-user]` resolving to effective
    confidentiality `client-confidential`.
- **Capture state:** Two-workspace table, one expanded with routing
  config, cross-workspace check widget visible.

### 5. Audit log

- **Filename:** `audit-log.png`
- **Route:** Settings → Policy tab → "Audit log" sub-tab.
- **Demo state:**
  - After running the cross-workspace operation from screenshot #1,
    the audit log should show 4-6 entries: cross_workspace_op_start,
    one or more model_call entries, tool_call entries, and a terminal
    op_end entry.
  - Each row shows timestamp, op_type, workspaces involved, tools
    called, model used.
- **Capture state:** Recent entries visible with the multi-workspace
  op clearly traceable.

### 6. Observability trace

- **Filename:** `observability-trace.png`
- **Route:** Open `http://localhost:6006/` (Phoenix UI, if Phoenix is
  running; otherwise `http://localhost:3001/` for the local Grafana
  panel that ships with the demo `docker-compose.override.example.yml`).
- **Demo state:**
  - The most-recent trace for the agent run from screenshot #1 is
    visible.
  - The trace is expanded to show the span tree: agent_loop span at
    the root, with child spans for retrieve, model_call (with
    `cache_control` cache-hit attribute), tool_call,
    subagent_dispatch.
- **Capture state:** Span tree expanded, attributes panel visible on
  the right showing semantic GenAI attributes.

### 7. Keyboard shortcuts overlay

- **Filename:** `keyboard-shortcuts-overlay.png`
- **Route:** `http://localhost:3000/` (main chat view).
- **Demo state:**
  - Press `⌘?` (or `Ctrl+?` on Linux/Windows) to open the help overlay.
  - The overlay shows all seven shortcuts grouped: navigation
    (`⌘K`, `⌘J`, `⌘N`, `⌘/`), execution (`⌘B`, `⌘.`), help (`⌘?`).
  - Background chat is dimmed; focus is trapped inside the overlay;
    Escape closes.
- **Capture state:** Overlay open, all shortcuts visible, dimmed
  background showing the chat is preserved underneath.

## Hero capture (optional)

A single high-resolution hero capture for the ragbot.ai homepage and
the release-notes article header.

- **Filename:** `hero/agent-panel-with-multi-workspace@2x.png`
- **Viewport:** 2880x1800 (Retina capture; otherwise 1440x900)
- **Demo state:** Same as screenshot #1 above.
- **Capture state:** Same as #1, plus the v3.4 settings strip ("Ragbot
  — by Synthesis Engineering" with vermillion divider) visible in the
  top-right corner.

## After capture

1. Replace the placeholder PNGs in `docs/screenshots/` with the real
   captures, preserving filenames.
2. Verify the docs render: open `docs/release-notes-v3.4.0.md` in a
   markdown previewer and confirm no broken-image icons.
3. Compress with `pngcrush` or `imageoptim` before committing — the
   docs directory shouldn't carry 5 MB PNGs.
4. Commit with `git add docs/screenshots/*.png && git commit` and a
   generic message (per the global commit-message hygiene rule).
