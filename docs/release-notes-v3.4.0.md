---
title: "Ragbot v3.4.0 — Ragbot becomes the conversational reference runtime of synthesis engineering"
slug: ragbot-v3-4-0
date: 2026-05-14
canonical_url: https://synthesisengineering.org/posts/2026/05/14/ragbot-v3-4-0/
categories:
  - synthesis-engineering
  - ragbot
  - releases
tags:
  - ragbot
  - mcp
  - skills
  - agent-loop
  - synthesis-engineering
author: Rajiv Pant
---

# Ragbot v3.4.0 — Ragbot becomes the conversational reference runtime of synthesis engineering

Ragbot v3.4 is the next-major-features release. It moves the project from a
polished 2024-paradigm chat-with-RAG product to a 2026-shaped conversational
AI runtime: explicit agent loop, first-class MCP in both directions, an
executable skills runtime, cross-workspace synthesis with visible
confidentiality boundaries, durable memory beyond vector RAG, and the
production-grade signals that make the architecture legible to engineering
leadership.

The synthesis-engineering positioning that the architecture had quietly
named for a year is now visible in the README, the ragbot.ai homepage, and
the in-product chrome. Ragbot is the reference runtime for the
**conversational** interaction primitive inside synthesis engineering, with
sibling reference implementations covering direct manipulation
([synthesis-console](https://github.com/synthesisengineering/synthesis-console)),
procedural execution
([Ragenie](https://github.com/synthesisengineering/ragenie)), and the
portable capability format
([synthesis-skills](https://github.com/synthesisengineering/synthesis-skills)).
The family will grow as the methodology and the AI landscape evolve.

![Ragbot v3.4 — Jaeger trace tree for a chat.request showing retrieval and chat-completion children, one of the production-grade observability signals new in this release](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/observability-trace.png)

The architectural rationale behind v3.4 — the synthesis-ecosystem
framing, the HCI-primitives map, the deterministic-enforcement thesis —
will be published as a blog series at
[synthesisengineering.org](https://synthesisengineering.org) and
[synthesiscoding.org](https://synthesiscoding.org) following this
release.

## Why this release matters

The 2026 center of gravity for chat-with-tools products has shifted from
"chat with retrieval" to stateful, tool-using agents with durable memory,
governed execution, and async background work. MCP is industry-default
infrastructure at 97M monthly SDK downloads and 5,800+ public servers.
SKILL.md is a cross-vendor standard adopted by Codex CLI, Gemini CLI, GitHub
Copilot, and Cursor. Memory has three layers in production. Observability
is a buying criterion, not polish. Local inference crossed the credibility
threshold with the Ollama 0.19 MLX backend on Apple Silicon.

Ragbot v3.3 was a polished 2024-paradigm product. It read clean. It worked
well. It did not look like a 2026 product to anyone who had seen the new
shape of the category. v3.4 closes that gap. Every architectural commitment
v3.4 ships traces back to a concrete shift in the category, not to feature
preference.

The 1.6%/98.4% ratio from VILA-Lab's *Dive into Claude Code* analysis
([source](https://github.com/VILA-Lab/Dive-into-Claude-Code)) is the design
instruction. AI decision logic is the small slice. Deterministic
infrastructure — permission gates, context management pipelines, tool
routing, recovery mechanisms — is the rest. v3.4 builds that
infrastructure for the conversational primitive.

## Headliner 1: Agent loop runtime

Ragbot is now an execution surface, not just a chat surface. A hand-rolled
graph-state agent loop replaces the single-turn `prompt → retrieve → call
LLM → return` path. The agent can decide between answering directly,
dispatching retrieval, calling a tool, running a skill, or fanning out to
sub-agents.

![Ragbot v3.4 agent panel — substantive multi-step response drawing on indexed workspace chunks, demonstrating the agent loop in action](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/agent-panel.png)

The loop is hand-rolled — no LangGraph, no CrewAI, no AutoGen. Use what
those frameworks teach; do not depend on them. The Plan-and-Execute pattern
is the default for compound questions with explicit replanning on failure.
The lead-agent-with-sub-agents pattern handles parallel research across
workspaces. Sandboxed code execution runs through E2B microVM or
self-hosted Daytona Docker for air-gapped installations; the disabled
sandbox fails closed with an actionable error rather than dropping into a
plain subprocess.

Permission gates fail closed at the tool boundary. The default behavior
denies any tool that does not match a read-only pattern or have an
explicit gate. The 98:2 ratio is enforced literally — most of the work is
the deterministic plumbing. State checkpoints are durable and replayable
through the `ragbot agent replay` command.

The chat-only no-tools mode remains available. The agent loop is opt-in
per session via the picker toggle or `agent=true` on `/api/chat`. Test
coverage gates the rollout: 45 tests across the agent loop core and the
agent capabilities surface (sub-agent dispatcher, sandbox, self-grader).

The `{"$ref": "step_id.field"}` placeholder syntax in plan-step inputs
lets a multi-step plan thread outputs without a separate scratchpad. The
self-grading loop ("Outcomes" pattern borrowed from Anthropic's
Code w/ Claude 2026 talks) lets the agent score its own output against a
written rubric and iterate.

## Headliner 2: First-class MCP — client and server

Ragbot is now both an MCP client and an MCP server.

As a client, Ragbot covers **all six MCP primitives** — tools, resources,
prompts, Roots, Sampling, and Elicitation — plus MCP Tasks for
long-running calls. Most "MCP-supporting" chat products only implement
tools; doing all six is the engineering-judgment signal. OAuth 2.1 with
Dynamic Client Registration is supported for remote servers, with a
stdio + HTTP/SSE proxy so local stdio-default servers work without
leaking complexity into the user's setup.

![Ragbot v3.4 MCP settings panel — empty state with the Add server form expanded, showing the stdio / http / sse transport selector](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/mcp-settings.png)

The MCP settings panel lists configured MCP servers, their connection
state, and the tools and resources they expose. Per-server toggles. Per
workspace allow/deny rules. The configured server list lives at
`~/.synthesis/mcp-clients.yaml`.

As a server, Ragbot exposes its workspace surface to other MCP-aware
agents — Claude Code, Cursor, ChatGPT desktop, Gemini CLI, and any other
client that speaks the protocol. Two transports: stdio for desktop
integrations, HTTP/SSE via `StreamableHTTPSessionManager` for network
clients. Bearer-token auth via `~/.synthesis/mcp-server.yaml` with
per-token `allowed_tools` glob filtering.

Five exposed tools:

- `workspace_search(workspace, query, k)` — vector + FTS search inside a
  single workspace.
- `workspace_search_multi(workspaces, query, k, budget_tokens)` —
  multi-workspace search with the confidentiality gate firing **before**
  retrieval, so denied workspace combinations never read content.
- `document_get(workspace, document_id)` — retrieve a single document.
- `skill_run(skill_name, inputs)` — execute a discovered skill.
- `agent_run_start(prompt, workspaces, ...)` — start an agent run, return
  a task ID. Pair with the existing agent endpoints for status/replay.

Three exposed resources: `ragbot://workspaces`, `ragbot://skills`,
`ragbot://audit/recent`.

## Headliner 3: Skills as runtime

In v3.3, Ragbot read skills as markdown and indexed them for RAG. v3.4
makes skills **executable** in the progressive-disclosure model: names
and descriptions in the system prompt, full body on selection, scripts
and templates on tool call.

![Ragbot v3.4 skills panel — seven skills visible: the six bundled starter-pack skills plus the demo skill, filtered to the demo workspace scope](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/skills-panel.png)

`SKILL.md` is now Ragbot's native extensibility format. A skill written
for Claude Code, Codex CLI, Cursor, or Gemini CLI runs on Ragbot without
modification. This makes Ragbot the third compatible runtime for the
SKILL.md format (after Claude Code and Codex CLI), which is the kind of
cheap-cost interoperability signal that compounds.

Six starter skills ship in the box:

- `workspace-search-with-citations` — search the active workspace and
  return results with `[workspace:document_id]` citations.
- `draft-and-revise` — multi-turn drafting with explicit revision passes.
- `fact-check-claims` — verify claims against the workspace and surface
  uncertainty honestly.
- `summarize-document` — structured summarization with citation
  retention.
- `agent-self-review` — the self-grading skill that powers the
  "Outcomes" pattern.
- `cross-workspace-synthesis` — the brand-defining skill (described in
  Headliner 5 below).

The `npx skills add synthesisengineering/synthesis-skills` install path
turns the 32 public synthesis-skills into runnable capabilities. Skills
discovery walks five roots in priority order:
`synthesis_engine/skills/starter_pack/` (built-in),
`~/.synthesis/skills/` (synthesis-engineering shared install),
`~/.claude/skills/` (Claude Code private skills),
`~/.claude/plugins/cache/<vendor>/skills/` (plugin-installed), and
per-workspace skill roots declared in `compile-config.yaml`. Later wins
on name collision, so operator-installed skills override built-ins.

CLI: `ragbot skills list/info/run`. REST: `/api/skills` with
`?workspace=W` filtering. UI: skills panel with one-click execution and
structured output rendering.

## Headliner 4: Synthesis ecosystem positioning and rebrand

Ragbot is officially the reference runtime for the conversational
interaction primitive inside synthesis engineering. The branding catches
up with what the architecture has been quietly saying for a year.

The README hero now opens with the synthesis-engineering framing. The
ragbot.ai homepage leads with the canonical paragraph and the synthesis
family identifier bar. `llms.txt` opens with the synthesis positioning
and the sibling reference implementations. The in-product chrome carries
the "Ragbot — by Synthesis Engineering" identifier in the settings panel
header and a vermillion-accented footer with cross-links to
synthesisengineering.org and synthesiscoding.org.

Vermillion (#b8312f) — the cinnabar red used in monastic manuscripts for
emphasis and correction — is Ragbot's accent ink in the historical-inks
palette of the synthesis family. It joins:

- Prussian blue (#1e3a5f) for synthesis-engineering
- Iron-gall green (#2e4a3a) for synthesis-coding
- Walnut brown for synthesis-writing
- Lapis ultramarine (#1c39bb) for Ragenie
- Sepia / oak-gall (#704214) for synthesis-console

Each runtime gets its own historical ink; the methodology sites carry the
contemplative inks of the crafts. Vermillion reads as the "active" ink —
the runtime that flags, executes, and surfaces — which matches Ragbot's
role inside the family.

The product name stays `Ragbot` (sentence case, not RAGbot). The product
is `Ragbot — by Synthesis Engineering`, the way `Postgres` is
`PostgreSQL — by the PostgreSQL Global Development Group`. Renaming a
product whose feature set still said "chat with RAG" would have read as
marketing dressing. v3.4 ships the substance first.

The stock Next.js public SVGs (`file.svg`, `globe.svg`, `next.svg`,
`vercel.svg`, `window.svg`) and the favicon were replaced with custom
synthesis-family icons.

## Headliner 5: Cross-workspace synthesis

This is the brand-defining feature. The synthesis-engineering thesis is
that AI's strengths — instant full-text search, cross-document synthesis,
tireless consistency — should be designed for, not retrofitted onto
human workflows. Multi-workspace synthesis is what only Ragbot can
credibly do; no incumbent has the architecture for it.

![Ragbot v3.4 cross-workspace policy panel — active workspaces, per-workspace policy with PUBLIC confidentiality and warn fallback, effective confidentiality across the operation, per-workspace model-routing verdicts, and the audit-log heading](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/policy-panel.png)

Multi-workspace chat is now first-class. Select 2+ workspaces in the UI.
The agent sees a per-workspace context budget (equal-split with floor
and redistribution; configurable via `cross_workspace_budget_tokens`) and
a per-workspace confidentiality tag (`public` / `personal` /
`client-confidential` / `air-gapped`). The effective confidentiality of
a cross-workspace operation is the max of participants, so a mix of
`personal` + `client-confidential` is treated as `client-confidential`
end-to-end.

Per-workspace `routing.yaml` governs which models can be called for
each workspace. Defaults: local-only for `client-confidential`, frontier
for `personal`. The `fallback_behavior` field controls what happens when
a requested model is denied: `DENY` (refuse the operation),
`DOWNGRADE_TO_LOCAL` (route to a local model), or `WARN` (proceed with
a logged warning).

Every cross-workspace operation is logged to
`~/.synthesis/cross-workspace-audit.jsonl` — append-only, atomic via
`O_APPEND`, with timestamp, workspaces involved, tools called, model
used, and a redacted prompt summary. A CTO who plugs Ragbot into
Datadog or Honeycomb can read the audit trail line by line.

![Ragbot v3.4 cross-workspace audit log — five entries spanning a multi-workspace operation: cross_workspace_op_start, two model_call entries, a tool_call for workspace_search_multi, and cross_workspace_op_end — all outcome=allowed across the acme-news and acme-user workspaces](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/audit-log.png)

The `cross-workspace-synthesize` starter skill walks the agent through
per-workspace budget math, the four-level confidentiality strictness
order with pairwise mix table, and the `[workspace:document_id]`
citation format. Citations name the source workspace explicitly so a
reviewer can trace any synthesized fact back to its origin.

A worked example. With workspaces `acme-news` (tagged
`client-confidential`) and `acme-user` (tagged `personal`) selected,
asking "what patterns appear in my AI consulting work this quarter?"
produces:

1. The agent loads each workspace's `routing.yaml`. `acme-news` denies
   frontier models; `acme-user` allows them. The effective policy is the
   intersection — local-only.
2. The cross-workspace gate checks the pairwise mix. Allowed.
3. `three_tier_retrieve_multi` retrieves per-workspace context with the
   budget split.
4. The agent dispatches to a local Qwen3 27B (or Gemma 4 31B, depending
   on the routing config).
5. The synthesis report cites each fact with `[acme-news:doc-id]` or
   `[acme-user:doc-id]`. The audit log captures the full operation.

## Production-grade signals

The features above are the headliners. The release also ships the
deterministic infrastructure that makes the headliners credible.

**Memory beyond RAG.** A three-layer memory stack lives in
`synthesis_engine.memory`: vector RAG over pgvector (existing),
entity-graph memory with provenance and temporal validity (new `nodes`
and `edges` tables; pgvector for embedding), and session/working memory
(per-user persistent prefs and in-flight context). A consolidation pass
between sessions distills durable facts from the previous session and
writes them into the entity graph — Anthropic's "Dreaming" pattern. The
consolidation is idempotent: a re-run checks `list_entities +
query_graph` *before* the LLM call so no duplicate facts get written.
Mem0 and Letta integrations are available as optional swap-ins behind
the abstraction.

**Replay CLI.** `ragbot agent replay <task_id> [--from-checkpoint N]
[--against-checkpoint M] [--show-trace] [--save-output PATH]`
deterministically re-runs an agent session from any checkpoint. A stable
hash over `{current_state, final_answer, step_results}` (timestamps
excluded) gates regression detection. `ragbot agent list-sessions` and
`ragbot agent checkpoints <task_id>` provide inspection.

**Eval regressions.** `tests/evals/regressions/` captures canonical bug
shapes as YAML cases: sub-agent dispatch max-parallel, disabled sandbox
actionable error, permission deny blocks tool, cross-workspace
air-gapped isolation, replay determinism canary. `make eval` runs the
full eval suite with a scorecard renderer. Regressions group separately
in the output and surface as URGENT on failure.

**Background tasks.** `synthesis_engine.tasks.BackgroundTaskManager`
provides JSONL persistence at `~/.synthesis/tasks/{id}.jsonl`,
cooperative cancellation (`TaskCancelled` raised at safe points; no
force-kill), crash recovery on startup (any `running`-state task gets
`crashed` reason `restart_during_run` on next boot), webhook delivery
per-task, and three notifier adapters: macOS via `osascript`, email via
SMTP, Slack via the existing MCPClient calling a Slack MCP server. The
`CompositeNotifier` isolates per-adapter failures so a Slack outage
doesn't break local notifications.

A scheduler is opt-in via `RAGBOT_SCHEDULER=1`, reading
`~/.synthesis/schedules.yaml`. A task-factory registry keeps the YAML
free of Python import paths. REST: six `/api/tasks/*` endpoints.

**Keyboard shortcuts.** A coherent shortcut layer covers the 2026
expected interactions:

![Ragbot v3.4 keyboard shortcuts overlay — ⌘? dialog showing all seven shortcuts with the underlying UI dimmed](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/keyboard-shortcuts-overlay.png)

- `⌘K` — model picker (re-wired through the registry)
- `⌘J` — workspace switch
- `⌘/` — message history search (real search; not a stub)
- `⌘N` — new chat
- `⌘B` — background the current run
- `⌘.` — cancel the current run
- `⌘?` — help overlay with focus trap and Escape close

Platform-aware key matching (Meta on macOS, Ctrl elsewhere); strict
exact-modifier matching so `⌘⌥K` does not accidentally fire `⌘K`.

**Observability.** OpenTelemetry traces by default with semantic GenAI
attributes on every model call, retrieval step, guardrail check, and
tool dispatch. `OTEL_EXPORTER_OTLP_ENDPOINT` ships traces to Phoenix,
Langfuse, Datadog, or Honeycomb. Prometheus exposition at
`/api/metrics`; cache-stats JSON at `/api/metrics/cache`. Prompt caching
with `cache_control` annotations on the static system-prompt prefix —
ngrok benchmarks report 70-90% real-world cost reduction on Anthropic;
Ragbot's own numbers track in that range.

![Ragbot v3.4 observability — Jaeger trace timeline for ragbot-api:chat.request: 12.01 seconds duration, 8 spans across one service at depth 2, with six retrieval children clustered around the 3-second mark and the chat openai/gpt-5-mini child accounting for nine of the twelve seconds](https://raw.githubusercontent.com/synthesisengineering/ragbot/v3.4.0/docs/screenshots/observability-trace.png)

## Open-weights additions

`engines.yaml` adds the four open-weights families that became serious
local agent defaults in 2026:

- **Llama 4** (Meta) — sizes documented in
  [`docs/open-weights-sizing.md`](open-weights-sizing.md).
- **Qwen3** (Alibaba) — the practical local agent default; 27B is the
  recommended balance of capability and footprint on Apple Silicon with
  the MLX backend.
- **DeepSeek-V3** — strong reasoning at competitive sizes.
- **Mistral Large** — Mistral's open-weights flagship.

Updated **Gemma 4** entries with notes on the Ollama 0.19 MLX backend
(~2x decode speedup on Apple Silicon).

The full sizing matrix at
[`docs/open-weights-sizing.md`](open-weights-sizing.md) maps model
families to recommended hardware tiers (laptop, prosumer desktop, Mac
Studio-class, workstation), VRAM/unified-memory requirements, and target
inference profiles. A Fortune 500 CISO who needs to bring AI capability
inside a controlled network can read the matrix and pick a deployment
configuration in one sitting.

## Breaking changes

v3.4 is the next-major-features release. Breaking changes are
intentional and visible. If you are upgrading from v3.3, the items
below require migration steps.

### `synthesis_engine` is now a public substrate library

The runtime code under `src/synthesis_engine/` is the supported import
surface for building synthesis-engineering products on top of Ragbot's
primitives. `src/ragbot/` is now ragbot-runtime-specific code only.

Imports under `from ragbot.X` for substrate types (config, workspaces,
keystore, models, llm backends, vectorstore, skills loader, memory,
agent, MCP, observability, policy, tasks) have moved to `from
synthesis_engine.X`. The `RagbotError` exception base class is renamed
to `SynthesisError` across the substrate; all five subclasses are
renamed correspondingly.

`Ragenie` v1.0 imports `synthesis_engine` cleanly. So can any other
synthesis-engineering runtime built on top of these primitives.

### `routing.yaml` per-workspace convention

Each workspace may declare a `routing.yaml` at its root:

```yaml
confidentiality: client-confidential
allowed_models:
  - "ollama/*"
  - "ollama_chat/*"
denied_models:
  - "claude-*"
  - "gpt-*"
  - "gemini-*"
fallback_behavior: DENY
```

The cross-workspace agent runtime enforces the strictest applicable
policy. Workspaces with no `routing.yaml` default to `personal` with
no model restrictions, preserving prior behavior.

### `identity.yaml` at `~/.synthesis/`

Declares the workspaces treated as personal (universal for skill
scoping) and the remote URL patterns used to classify a repo as
personal vs strict by the synthesis-git-hooks engine.

```yaml
personal_workspaces:
  - acme-user
personal_remote_patterns:
  - "github.com:acme-user/"
```

Required for workspace-scoped skills discovery and for the unified git
hooks engine.

### Agent loop API signature

`AgentLoop.run()` accepts new kwargs: `workspaces` (list, not single
value), `workspace_roots`, `routing_enforced`, and
`cross_workspace_budget_tokens`. The legacy single-workspace shape
continues to work — a single-element list preserves prior behavior — but
consumers calling the agent loop directly should update to the
multi-workspace shape.

## Migration notes

1. **Update imports.** Replace `from ragbot.X` substrate imports with
   `from synthesis_engine.X`. The same applies to `RagbotError` →
   `SynthesisError`.

2. **Install the v3.4 skill stack.**

   ```bash
   npx skills add synthesisengineering/synthesis-skills --global --all --copy
   ```

   This installs `synthesis-git-hooks`, `synthesis-anti-shortcuts`, and
   the rest of the synthesis-skills package into `~/.synthesis/skills/`.

3. **Create `~/.synthesis/identity.yaml`.**

   ```yaml
   personal_workspaces:
     - acme-user
   personal_remote_patterns:
     - "github.com:acme-user/"
   ```

4. **Add `routing.yaml` to each confidential workspace.** See the
   example above.

5. **Configure `~/.synthesis/git-hook-config.yaml`** for the
   synthesis-git-hooks engine. The skill ships a commented example.

6. **Run the upgrade verification.**

   ```bash
   make test            # 400+ tests across the v3.4 surface
   make eval-quick      # 9 eval cases including 5 regressions
   ragbot agent list-sessions
   ```

## Engineering decisions worth naming

A handful of architectural decisions in v3.4 are worth calling out for
anyone evaluating the codebase as a reference implementation:

- **Hand-rolled agent loop, no framework.** No LangGraph, CrewAI, or
  AutoGen. The deterministic plumbing is the differentiator; depending
  on a framework would leak that differentiator out of the codebase.

- **Fail-closed permission gates.** Unknown tools deny by default. The
  cross-workspace gate fires *before* retrieval so denied workspace
  combinations never read content.

- **`{"$ref": "step_id.field"}` placeholder syntax.** Multi-step plans
  thread outputs through plan-step inputs without a separate scratchpad.

- **Idempotent memory consolidation.** A re-run produces no duplicates
  because the consolidator checks `list_entities + query_graph` before
  the LLM call.

- **Append-only audit log.** `O_APPEND` is atomic on POSIX. Redaction
  uses the same patterns as the synthesis-git-hooks policy so the audit
  trail does not become a leak vector.

- **Substrate / runtime layer separation.** `synthesis_engine` knows
  nothing about Ragbot. Ragbot composes `synthesis_engine` primitives.
  Ragenie v1.0 will compose the same primitives differently.

- **Anti-shortcut catalog.** `~/.synthesis/anti-shortcut-catalog.yaml`
  is consumed by both human review and pre-commit hooks to detect
  costume vocabulary (backward-compat-as-a-pro, "minimal diff" as
  framing, "stalled with substantial progress" as closure, and so on).
  The catalog is the operationalization of an engineering discipline.

## What's not in this release

- **Voice and other multimodal.** Lives in Ragenie. The chat-led
  posture is text-led by design; voice fits better with the
  workflow-led posture where the human is on the loop.
- **Computer use / browser use.** Lives in Ragenie. Sandboxed agent
  fleets running computer-use and browser-use are the multi-agent /
  async-default territory.
- **LAN-shared inference.** Lives in Ragenie's deployment surface or in
  the local-open-weights-models runbook track. Ragbot's
  single-container default is fine for the chat-led use case.

These are not deferrals. They are explicit scope decisions: each lives
in the synthesis ecosystem implementation whose posture matches it.

## Acknowledgments

Thanks to everyone who reviewed proposals, surfaced issues, and pushed
back on lazy shortcuts during the v3.4 development cycle. The lessons
distilled during development inform the
[synthesis-anti-shortcuts](https://github.com/synthesisengineering/synthesis-skills/tree/main/synthesis-anti-shortcuts)
skill, which ships as part of synthesis-skills and can be installed
into any AI coding agent that reads the SKILL.md format.

The v3.4 release is the result of synthesis engineering practiced on
itself.

## Where to go next

- [Install Ragbot v3.4](https://github.com/synthesisengineering/ragbot/blob/main/INSTALL.md)
- [Configure providers and keys](https://github.com/synthesisengineering/ragbot/blob/main/CONFIGURE.md)
- [Try demo mode](https://github.com/synthesisengineering/ragbot#demo-mode) (`RAGBOT_DEMO=1 docker compose up -d`)
- [Synthesis Engineering — the methodology](https://synthesisengineering.org)
- [Synthesis Coding — the daily practice](https://synthesiscoding.org)
- [synthesis-skills — the portable capability format](https://github.com/synthesisengineering/synthesis-skills)
