# Ragbot UI/UX Redesign

**Status:** Complete (Phase 5), Testing Planned (Phase 6)
**Created:** 2025-12-14
**Last Updated:** 2025-12-14

## Overview

This project redesigns Ragbot's user interface to better reflect its core value proposition as a RAG-enabled AI assistant. The current sidebar-based Streamlit layout has usability issues and hides RAG functionality in "Advanced Settings" despite "RAG" being in the product name.

## Problem Statement

1. **RAG Hidden in Advanced Settings**: RAG is Ragbot's core differentiator but requires users to find and enable it manually
2. **Narrow Sidebar**: Dropdown menus are truncated, model names unreadable
3. **Wasted Space**: Sidebar takes up valuable horizontal space that could be used for chat
4. **No Index Management**: Users can't see index status or manage workspace indexes
5. **Manual Indexing Required**: Users must manually click "Index Workspace" before RAG works

## Solution

A modern architecture with:
- FastAPI backend with REST API and SSE streaming
- React/Next.js frontend (replacing Streamlit)
- RAG enabled by default with auto-indexing
- Full-width chat area
- Mobile and voice interface ready

## Documents

| Document | Purpose |
|----------|---------|
| [design.md](design.md) | Detailed UI mockups and design specifications |
| [implementation.md](implementation.md) | Phase-by-phase implementation guide |

## Quick Links

- **React Frontend:** `ragbot/web/`
- **Backend API:** `ragbot/src/api/`
- **Core Library:** `ragbot/src/ragbot/`
- **Streamlit (legacy):** `ragbot/src/ragbot_streamlit.py`

## Related Projects

| Project | Location | Description |
|---------|----------|-------------|
| **AI Knowledge Architecture** | [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture) | Repository architecture this UI works with |
| **AI Knowledge Compiler** | [ragbot/projects/active/ai-knowledge-compiler](../ai-knowledge-compiler/) | Compiler for rebuild functionality |

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: RAG as Default | ✅ Complete | Enable RAG by default, auto-indexing |
| Phase 2: FastAPI Backend | ✅ Complete | REST API with SSE streaming |
| Phase 3: React Frontend | ✅ Complete | Next.js web UI with TypeScript |
| Phase 4: Docker Setup | ✅ Complete | Full Docker Compose configuration |
| Phase 5: Config & Models | ✅ Complete | engines.yaml integration, all 9 models tested |
| Phase 6: Testing | ✅ Complete | 82 tests passing (config, keystore, API, helpers) |
| Phase 7: Cleanup | 🔄 Planned | Remove Streamlit, legacy code cleanup |

### Phase 1 Completed (2025-12-14)

Changes made:
- RAG checkbox now defaults to ON when workspace has ai-knowledge content
- RAG section moved from Advanced Settings to main sidebar (prominent placement)
- Index status indicator shows ✅ Ready / ⚠️ Not indexed / ❓ Unknown
- Auto-indexing on first query when index is missing
- Index button label changes based on status (Index Workspace / Rebuild Index)
- `helpers.py` updated to default `use_rag=True`

### Phase 2: FastAPI Backend (Complete)

**Status**: FastAPI backend implemented (2025-12-14)

- REST API at `src/api/` with full OpenAPI documentation
- SSE streaming for chat responses
- Workspace/model/config endpoints
- Health check endpoint

### Phase 3: React Frontend (Complete)

**Status**: Next.js frontend implemented (2025-12-14)

The React frontend is complete at `web/`:
- Next.js 16 with TypeScript and Tailwind CSS
- Full API client with SSE streaming support
- Workspace selector with status indicators
- Model selector grouped by provider with category filter
- Chat interface with streaming responses and markdown rendering
- Settings panel with RAG toggle and API key status
- Copy buttons on messages and code blocks

### Phase 4: Docker Setup (Complete)

**Status**: Docker Compose configuration complete (2025-12-14)

- `docker-compose.yml` with ragbot-api and ragbot-web services
- `web/Dockerfile` for Next.js frontend
- Named volume for node_modules persistence
- Environment variables for API URL configuration

**To run**:
```bash
cd ragbot && docker compose up -d
# Access at http://localhost:3000
```

### Phase 5: Config & Model Fixes (Complete)

**Status**: Complete (2025-12-14)

**Configuration cleanup**:
- Removed hardcoded MODELS dict from `src/ragbot/config.py`
- All model/provider config now loads from `engines.yaml`
- Added new functions: `load_engines_config()`, `get_providers()`, `get_temperature_settings()`
- Added API endpoints: `/api/models/providers`, `/api/models/temperature-settings`, `/api/config/keys`
- Frontend fetches providers dynamically from API

**Model fixes (all 9 models tested and working)**:
- OpenAI: gpt-5-mini, gpt-5.2-chat-latest, gpt-5.2
- Anthropic: claude-haiku-4-5-20251001, claude-sonnet-4-5-20250929, claude-opus-4-5-20251101
- Google: gemini/gemini-2.5-flash-lite, gemini/gemini-2.5-flash, gemini/gemini-3-pro-preview

**Technical fixes**:
- OpenAI GPT-5 models use temperature=1.0 (only supported value)
- gpt-5-mini uses `max_completion_tokens` instead of `max_tokens`
- Made ChatRequest.temperature Optional to use model defaults from engines.yaml
- Added `litellm.drop_params=True` for unsupported parameter handling

**API Key UX improvements**:
- `/api/config/keys` endpoint returns detailed key status per provider
- Shows key source (workspace/default) in UI
- Auto-switches to provider with available key when workspace changes
- Provider dropdown filters to only show providers with keys

### Phase 6: Testing (Planned)

**Status**: Planned

**Goal**: Add comprehensive test coverage for all model configurations

**Planned tasks**:
- Model integration tests to verify all engines.yaml models work
- Unit tests for config.py functions (load_engines_config, get_all_models, etc.)
- Unit tests for keystore.py functions (get_api_key, get_key_status, etc.)
- API endpoint tests for chat, models, config, workspaces
- Frontend component tests (optional)

**Benefits**:
- Catch model configuration issues before deployment
- Prevent regressions when updating engines.yaml
- Ensure API key handling works correctly

## Lessons Learned

### CRITICAL: Never Hardcode Configuration

**Problem**: Multiple instances of hardcoding providers, models, and labels in code instead of reading from `engines.yaml`.

**Examples of violations found**:
1. Hardcoded `MODELS` dict in `src/ragbot/config.py`
2. Hardcoded `PROVIDERS` array in `web/src/components/SettingsPanel.tsx`
3. Hardcoded `PROVIDER_LABELS` in `src/api/routers/models.py`
4. Hardcoded `DEFAULT_MODEL` constant instead of reading from engines.yaml

**Solution**: All configuration MUST come from `engines.yaml`:
- Use `load_engines_config()` to load the configuration
- Use `get_providers()` to get provider list
- Use `get_all_models()` to get models (reads from engines.yaml)
- Use `get_default_model()` to get default (reads from engines.yaml)
- Frontend should fetch providers from `/api/models/providers` endpoint

### CRITICAL: Never Rely on Training Data for Model Information

**Problem**: AI assistants (including Claude) have outdated training data. When asked to update model configurations, Claude repeatedly downgraded models to older versions it "knew" from training (e.g., GPT-4o instead of GPT-5.2, o3 instead of gpt-5.2-thinking).

**Impact**: This caused significant damage to the codebase and user frustration.

**Rules added to CLAUDE.md**:
1. NEVER downgrade model versions - ever
2. DO NOT rely on training data for model information
3. Always use web search to find current model versions
4. If engines.yaml has a model configured, the user put it there intentionally
5. Today's date is provided in system context - use it

**Current models (December 2025)**:
- OpenAI: gpt-5-mini, gpt-5.2-chat-latest, gpt-5.2
- Anthropic: claude-haiku-4-5-20251001, claude-sonnet-4-5-20250929, claude-opus-4-5-20251101
- Google: gemini/gemini-2.5-flash-lite, gemini/gemini-2.5-flash, gemini/gemini-3-pro-preview

### Single Source of Truth

**Principle**: `engines.yaml` is the single source of truth for:
- Provider names and API key names
- Model IDs, categories, and capabilities
- Default models per provider
- Temperature settings
- Context windows and output limits

Code should NEVER duplicate this information. All code should call functions that read from engines.yaml.

### LiteLLM Provider Prefixes

**Problem**: OpenAI models returned blank responses because LiteLLM needs provider prefixes for routing.

**Solution**: The `_normalize_model_id()` function in `config.py` adds the appropriate prefix:
- Anthropic models: `anthropic/{model_name}`
- OpenAI models: `openai/{model_name}`
- Google models: Already have `gemini/` prefix in engines.yaml

### Model-Specific Parameter Handling

**Problem**: Different LLM providers use different parameter names and constraints:
- OpenAI GPT-5 models only support temperature=1.0
- gpt-5-mini requires `max_completion_tokens` instead of `max_tokens`
- Gemini 3 Pro uses "thinking tokens" that consume the output budget

**Solution**:
1. Store model-specific temperature in engines.yaml
2. Make ChatRequest.temperature Optional (uses model default)
3. Detect model type in core.py and use correct parameter name
4. Set `litellm.drop_params=True` to ignore unsupported parameters

**Lesson**: When models don't work, debug the code/API parameters first. Don't downgrade to older models.

### Git Branch Strategy for Development

**Practice**: Use feature branches for significant work:
- Create `feature/react-ui` branch for development
- Commit frequently to protect against data loss
- Keep main branch stable for public users
- Merge to main only when ready to publish

## Success Metrics

| Metric | Before | After Phase 1 | Current | Target |
|--------|--------|---------------|---------|--------|
| Steps to enable RAG | 3+ clicks | 0 (automatic) | ✅ Done | ✅ Done |
| Visible settings truncation | Yes | Yes | Better | ✅ Done |
| Chat area width | ~70% | ~70% | ~100% | ✅ Done |
| Time to first RAG query | Manual index required | Auto-indexed | ✅ Done | ✅ Done |
| Markdown rendering | None | Basic | Full with syntax highlighting | ✅ Done |
| Docker deployment | Manual | Manual | docker compose up | ✅ Done |

## Future Considerations

These items are documented for potential future projects. They don't block current project completion but are worth considering for future enhancements.

### Mid-Conversation Model Switching & Instruction Handling

**Current behavior**: When users switch LLM providers mid-conversation, Ragbot:
1. Sends the new model's instructions (e.g., `chatgpt.md` when switching to GPT)
2. Includes full conversation history in each request (LLM APIs are stateless)
3. The new model sees responses generated by the previous model

**Considerations for future work**:

| Approach | Pros | Cons |
|----------|------|------|
| **Current (model-specific instructions each request)** | Optimal for that model's capabilities | History mismatch - GPT sees Claude's responses with Claude-optimized instructions |
| **Unified instructions (same for all models)** | Consistent behavior across switches | Can't optimize for each model's strengths |
| **Handoff context** | Explicitly tells new model about the switch | Extra tokens; may confuse some models |
| **Lock model after first message** | Avoids the problem entirely | Reduces flexibility |

**How other platforms handle this**:
- **Claude/ChatGPT web**: Don't allow mid-conversation model switching
- **Poe**: Allows switching but uses same instructions for all models
- **Ragbot**: Allows switching with model-specific instructions (unique capability)

**Potential future project**: "Multi-Model Conversation UX" to explore optimal handling of model switches, including:
- User-visible indication when instructions change
- Option to "translate" conversation context for new model
- Analytics on how often users actually switch mid-conversation
- A/B testing different approaches

**Decision**: Current behavior is correct and functional. Revisit only if user feedback indicates problems with model switching experience
