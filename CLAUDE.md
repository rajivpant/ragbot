# Claude Code Context: ragbot

## Repository: ragbot (PUBLIC)

This is a **PUBLIC** open source repository. Be careful not to include confidential information.

## Product Relationship

- **Ragbot**: Actively maintained and upgraded. Production-ready CLI and Streamlit UI.
- **RaGenie**: Successor product with advanced RAG capabilities. Under development.
- Both products share `ai-knowledge-*` repos as their data layer.
- Both products will continue to be actively developed.

## Architecture

```text
ragbot/
├── src/
│   ├── ragbot.py              # CLI entry point
│   ├── ragbot/                # Core library (chat, config, models)
│   ├── api/                   # FastAPI backend
│   ├── rag.py                 # RAG module
│   └── compiler/              # AI Knowledge Compiler
├── web/                       # React/Next.js frontend
│   ├── src/components/        # React components
│   ├── src/lib/api.ts         # API client
│   └── Dockerfile             # Frontend container
├── docker-compose.yml         # Full stack deployment
├── requirements.txt
└── engines.yaml               # LLM engine configurations (SINGLE SOURCE OF TRUTH)

~/.synthesis/                  # synthesis-engineering shared config home
├── keys.yaml                  # API keys (shared across ragbot, ragenie, etc.; never in repo)
├── ragbot.yaml                # Ragbot user preferences (default_workspace)
└── console.yaml               # Synthesis-console sources (also used by ragbot for repo discovery)
```

Legacy `~/.config/ragbot/{keys,config}.yaml` is read as a fallback when
`~/.synthesis/` is empty, so existing setups keep working.

**Running the stack:**
```bash
docker compose up -d
# Access at http://localhost:3000
```

## Data Location

Ragbot discovers AI Knowledge repositories from multiple sources. Resolution
order (when `--base-path` and `RAGBOT_BASE_PATH` are both unset, the index is
the **union** across these sources):

1. `--base-path` CLI argument or `RAGBOT_BASE_PATH` env (override mode: flat-parent only)
2. `~/.synthesis/console.yaml` — synthesis-console source list (the integration point)
3. `~/workspaces/*/ai-knowledge-*` — workspace-rooted layout glob
4. `/app/ai-knowledge` — Docker container default
5. `~/ai-knowledge` — legacy flat-parent convention

Workspace names are derived from the directory (`ai-knowledge-` prefix
stripped). Private repos (`-private` suffix or `.ai-knowledge-private-owner`
sentinel) are filtered unless `RAGBOT_OWNER_CONTEXT=1`.

Each ai-knowledge repo contains:
- **source/instructions/** - WHO: Identity/persona files
- **source/runbooks/** - HOW: Procedure guides
- **source/datasets/** - WHAT: Reference knowledge
- **compiled/** - AI-optimized output (auto-generated)

## Privacy Guidelines for This Public Repo

**This is a PUBLIC repository. Confidentiality is critical.**

- **NEVER** include client, company, or personal workspace names
- **ONLY** use generic placeholders: `personal`, `company`, `example-company`, `example-client`, `client-a`
- When in doubt, ask the user before committing

## Key Concepts

### Workspace System

- `user_workspace` config points to the user's identity workspace (e.g., "personal")
- Workspace folder names are usernames - do NOT rename to generic names
- Workspaces inherit from the user workspace

### Multi-User Design

- System supports multiple users with separate identity workspaces
- Different workspaces may come from different git repos
- User workspaces are private; some workspaces may be shared team repos

## Versioning

- Version is tracked in `VERSION` file (semantic versioning: MAJOR.MINOR.PATCH)
- **Maintain version numbers**: When making releases, increment the version appropriately:
  - PATCH (0.0.X): Bug fixes, minor changes
  - MINOR (0.X.0): New features, backwards compatible
  - MAJOR (X.0.0): Breaking changes
- Create git tags for releases: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- Push tags: `git push origin vX.Y.Z`

## Development Notes

- Python CLI with FastAPI backend + React/Next.js frontend
- Uses LiteLLM for multi-provider LLM support
- Engines configured in `engines.yaml` (SINGLE SOURCE OF TRUTH for all model config)
- API keys stored in `~/.synthesis/keys.yaml` (shared across synthesis-engineering products)

### Agent Skills

Ragbot reads Agent Skills (directories containing `SKILL.md`) as first-class content alongside legacy runbooks.

Discovery sources, in priority order (later wins on name collision):
1. `~/.synthesis/skills/` (synthesis-engineering shared install)
2. `~/.claude/skills/` (Claude Code private skills)
3. `~/.claude/plugins/cache/<vendor>/skills/` (plugin-installed skills)
4. Per-workspace skill roots declared in compile-config.yaml `sources.skills.roots`

A skill's full directory tree is honored:
- `SKILL.md` — canonical entry point (frontmatter + body).
- `references/**/*.md` and other markdown — additional procedure detail.
- Scripts (`*.py`, `*.sh`, `*.js`, etc.) — bundled tools.
- Other text artifacts — configs, data files, etc.

For RAG indexing (`ragbot skills index`), every text file becomes a searchable chunk tagged with `skill_name`, `skill_relative_path`, `skill_file_kind ∈ {skill_md, reference, script, other}`. Markdown is chunked normally; scripts are stored as whole-file chunks so a query like "install autostart" can hit `install-autostart.sh` directly.

For compilation (`ragbot compile`), the `sources.skills` block in `compile-config.yaml` opts in:

```yaml
sources:
  local:
    path: ./source
  skills:
    enabled: true
    roots: []                 # extra roots beyond ~/.synthesis/skills, ~/.claude/skills
    include: ["synthesis-*"]  # optional name-glob whitelist
    exclude: []
    include_references: true        # default true
    include_scripts_inline: false   # default false; scripts are listed by name
```

SKILL.md and references go into the `instructions` category (compiled into the LLM-target output). Scripts are listed by name in a per-skill inventory file under `runbooks` so the LLM knows what tools exist without inlining executable code.

CLI: `ragbot skills list`, `ragbot skills info <name>`, `ragbot skills index [--workspace skills]`.

Backend code lives in `src/ragbot/skills/`.

### LLM Backend Abstraction

Ragbot routes every LLM call through a backend interface (`src/ragbot/llm/`) so the underlying provider gateway is swappable without touching the chat code path.

Two backends ship:

- **litellm** (default) — wraps `litellm.completion()`. Best provider/model coverage, handles long-tail provider quirks. Pinned `>=1.83.0` to avoid the March-2026 supply-chain incident range.
- **direct** — opt-in. Calls each provider's official SDK directly: `anthropic`, `openai`, `google-genai`. Smaller dependency surface, no third-party gateway. Useful for users who want to retire LiteLLM, or for benchmarking.

Selection: `RAGBOT_LLM_BACKEND={litellm|direct}` (default `litellm`). The cached singleton is exposed via `ragbot.llm.get_llm_backend()`.

Adding a new backend (e.g., Bifrost, Portkey, OpenRouter) is a single file implementing `LLMBackend` plus one selection arm in `__init__.py`. The backend swallows provider quirks (GPT-5.x `max_completion_tokens`, Claude 4.7+ `thinking.type.adaptive`, Anthropic-thinking-requires-temp-1, etc.) so the chat code path stays clean.

### Reasoning / Thinking Modes

Models that advertise thinking support in `engines.yaml` (Claude Sonnet 4.6, Claude Opus 4.7, GPT-5.5, GPT-5.5-pro, Gemini 3 Flash / 3.1 Pro / 3.1 Flash Lite) are wired through LiteLLM's `reasoning_effort` parameter. LiteLLM normalises that into the provider-native shape (e.g., `thinking={"type": "adaptive"}` for Claude 4.x).

Default policy:

- **Flagship models** with thinking support → `reasoning_effort: medium` automatically.
- **Non-flagship models** with thinking support → off by default.
- Models without a `thinking:` block in `engines.yaml` → no thinking params sent.

Override:

- Per-call: pass `thinking_effort=` to `chat()` / `chat_stream()`. Accepted values: `high`, `medium`, `low`, `minimal`, `off`, `auto`.
- Globally: set `RAGBOT_THINKING_EFFORT=...` env var.

Implementation in `src/ragbot/core.py::_resolve_thinking_for_model`.

### Cross-Workspace Search

`get_relevant_context` automatically merges retrieved context from the user's selected workspace AND the canonical `skills` workspace (when it exists and has chunks). Each workspace's chunk identity, char ranges, and full-document logic remain isolated; the fan-out happens at the formatted-block level.

API:

- `rag.search_across_workspaces(workspaces, query, limit, content_type)` — vector search across workspaces, RRF-merged, results tagged with `metadata.source_workspace`.
- `rag.get_relevant_context(workspace, query, additional_workspaces=[...])` — explicit fan-out (pass `[]` to opt out).
- Auto-include policy: when `additional_workspaces is None` and the `skills` workspace has data, ragbot includes it automatically.

### Vector Store Backends

Ragbot uses an abstraction over the vector store. Two backends ship:

- **pgvector** (default) — PostgreSQL with the `pgvector` extension. Native FTS via tsvector replaces in-process BM25. Selected when `RAGBOT_VECTOR_BACKEND=pgvector` (or unset) and `RAGBOT_DATABASE_URL` is reachable.
- **qdrant** (legacy) — Embedded local-file Qdrant. Selected with `RAGBOT_VECTOR_BACKEND=qdrant`. Retained for back-compat; falls back to in-process BM25.

Backend code lives in `src/ragbot/vectorstore/`. The schema (single shared `documents` + `chunks` table, scoped by `workspace` column, with HNSW + GIN indexes) is in `vectorstore/migrations/0001_initial.sql`. New migrations append numerically; the runner is idempotent.

Diagnose with `ragbot db status`. Apply migrations explicitly with `ragbot db init`.
- Workspaces discovered automatically from ai-knowledge-* repositories

### Configuration Functions (from engines.yaml)

All model/provider configuration comes from `engines.yaml`. Use these functions:
- `load_engines_config()` - Load the raw configuration
- `get_providers()` - Get list of provider names
- `get_all_models()` - Get all models with full info
- `get_default_model()` - Get the default model ID
- `get_temperature_settings()` - Get temperature presets

**NEVER hardcode model names, provider names, or defaults in code.**

## Model Configuration Rules - CRITICAL

**NEVER DOWNGRADE MODEL VERSIONS. EVER. THIS IS ABSOLUTE AND NON-NEGOTIABLE.**

**DO NOT RELY ON TRAINING DATA FOR MODEL INFORMATION.** Training data is outdated. Use the current date (provided in system context) and web search to find the latest models.

When the codebase or `engines.yaml` specifies a model version, DO NOT:
- Revert to older model IDs
- Change model versions to "safer" or "more familiar" versions from training data
- Downgrade because a model "doesn't seem to work"
- Assume models from training data are current - THEY ARE NOT
- Replace newer models with older ones you "know" from training
- **EVER replace a preview/beta model with an older "stable" model** - preview/beta of a new version is ALWAYS better than stable of an old version
- Remove models that return empty responses or errors - FIX THE CODE instead

If `engines.yaml` has a model configured, it was added intentionally by the user who knows what models are currently available. DO NOT TOUCH IT unless explicitly asked.

**Models in engines.yaml should ONLY move forward, NEVER backward.**
- If the user ever wants to downgrade a model, THEY will do it manually
- Claude should NEVER downgrade models, even if they appear broken
- When a model doesn't work, the issue is in the code/API configuration, NOT the model

**If you need to update models:**
1. Check the current date from system context
2. Web search for the latest released models
3. Never rely on training data cutoff knowledge
4. The user knows what models exist better than your training data
5. ONLY add newer models, NEVER replace with older ones

**Always check the current date** and use web search for the latest released model versions:
- Anthropic: https://www.anthropic.com/claude
- OpenAI: https://platform.openai.com/docs/models
- Google: https://ai.google.dev/models

If a model doesn't work, investigate the code/API issues rather than downgrading. The problem is ALWAYS in the code, not in choosing the wrong model.
