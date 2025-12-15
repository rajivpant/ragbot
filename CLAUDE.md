# Claude Code Context: ragbot

## Repository: ragbot (PUBLIC)

This is a **PUBLIC** open source repository. Be careful not to include confidential information.

## Repository Ecosystem

### Core Repositories

| Repository | Type | Purpose | Location |
|------------|------|---------|----------|
| **ragbot** | Public | AI assistant CLI and Streamlit UI | `~/projects/my-projects/ragbot/` |
| **ragbot-site** | Public | Website for ragbot.ai | `~/projects/my-projects/ragbot-site/` |
| **ragenie** | Public | Next-gen RAG platform | `~/projects/my-projects/ragenie/` |
| **ragenie-site** | Public | Website for ragenie.ai | `~/projects/my-projects/ragenie-site/` |
| **ragbot-data** | Private | DEPRECATED - kept for workspace history | `~/ragbot-data/` |
| **synthesis-coding-site** | Public | Website for synthesiscoding.com | `~/projects/my-projects/synthesis-coding-site/` |

### AI Knowledge Repositories

All located in `~/projects/my-projects/ai-knowledge/`. See `ai-knowledge-rajiv/my-projects.yaml` for the authoritative list.

| Repository | GitHub Org | Type | Inherits From |
|------------|------------|------|---------------|
| **ai-knowledge-ragbot** | rajivpant | Public | (root) |
| **ai-knowledge-rajiv** | rajivpant | Private | ragbot |
| **ai-knowledge-example-company** | rajivpant | Private | rajiv |
| **ai-knowledge-example-client** | rajivpant | Private | example-company |
| **ai-knowledge-example-client** | rajivpant | Private | example-company |
| **ai-knowledge-example-client** | rajivpant | Private | example-company |
| **ai-knowledge-example-client** | rajivpant | Private | rajiv |
| **ai-knowledge-example-client** | tgorg-ai | Private | rajiv, example-company |

**Note:** example-client is in a different GitHub org (`tgorg-ai`), not `rajivpant`.

Note: Home directory varies by machine (`/Users/rajiv` vs `/Users/rajivpant`), so use `~` for paths.

## VS Code Workspace

All repositories are in the same VS Code workspace for unified development.

## Product Relationship

- **Ragbot**: Actively maintained and upgraded. Production-ready CLI and Streamlit UI.
- **RaGenie**: Successor product with advanced RAG capabilities. Under development.
- Both products share `ragbot-data` as their data layer.
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

~/.config/ragbot/
├── keys.yaml                  # API keys (per-user, never in repo)
└── config.yaml                # User preferences (default_workspace)
```

**Running the stack:**
```bash
cd ~/projects/my-projects/ragbot
docker compose up -d
# Access at http://localhost:3000
```

## Data Location

Ragbot uses **convention-based discovery** to find AI Knowledge repositories:

1. **Primary source:** `~/projects/my-projects/ai-knowledge/ai-knowledge-*/`
2. **Legacy source:** `~/ragbot-data/workspaces/` (deprecated)

Each ai-knowledge repo contains:
- **source/instructions/** - WHO: Identity/persona files
- **source/runbooks/** - HOW: Procedure guides
- **source/datasets/** - WHAT: Reference knowledge
- **compiled/** - AI-optimized output (auto-generated)

**Note:** `ragbot-data` is deprecated. Content has been migrated to individual `ai-knowledge-*` repositories.

## Privacy Guidelines for This Public Repo

### NEVER include in docs or code

- Client/employer company names (use "example-company" instead)
- Workspace names that reveal client relationships
- Any content from ragbot-data that could identify clients

### Safe to use

- "rajiv" workspace name (owner's personal workspace)
- Open source project workspace names (e.g., "ragenie")
- Generic example names: "example-company", "acme-corp", "test-workspace"

### Example transformations

When writing documentation or examples:

- Use "example-company" or "client-workspace" instead of actual client names
- Use generic business scenarios instead of actual client project details

## Key Concepts

### Workspace System

- `user_workspace` config points to the user's identity workspace (e.g., "rajiv")
- Workspace folder names are usernames - do NOT rename to generic names
- Workspaces inherit from the user workspace

### Multi-User Design

- System supports multiple users with separate identity workspaces
- Different workspaces may come from different git repos
- User workspaces are private; some workspaces may be shared team repos

## Git Operations

**IMPORTANT**: Before any git commands for this repo, ensure you are in the correct directory:

```bash
cd ~/projects/my-projects/ragbot
```

Each repo in the ecosystem has its own git history. Don't run git commands from the wrong directory.

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
- API keys stored in `~/.config/ragbot/keys.yaml`
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
