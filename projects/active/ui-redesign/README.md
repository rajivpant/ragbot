# Ragbot UI/UX Redesign

**Status:** In Progress
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
| Phase 5: Cleanup | In Progress | Remove hardcoded config, finalize engines.yaml integration |

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

### Phase 5: Cleanup (In Progress)

**Status**: Refactoring to use engines.yaml as single source of truth

- Removed hardcoded MODELS dict from `src/ragbot/config.py`
- All model/provider config now loads from `engines.yaml`
- Added new functions: `load_engines_config()`, `get_providers()`, `get_temperature_settings()`
- Added API endpoints: `/api/models/providers`, `/api/models/temperature-settings`
- Frontend needs update to fetch providers dynamically from API

**Next Steps**:
- Update frontend SettingsPanel to fetch providers from API instead of hardcoding
- Remove Streamlit and legacy code
- Update models to latest December 2025 versions

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

### Model Version Management

**Problem**: Model versions were downgraded or outdated versions were used.

**Rule**: NEVER downgrade model versions. Always use the latest released models.
- Check current date (December 2025)
- Search for latest model versions from official sources
- Update engines.yaml with latest models
- Added rule to CLAUDE.md to prevent future violations

### Single Source of Truth

**Principle**: `engines.yaml` is the single source of truth for:
- Provider names and API key names
- Model IDs, categories, and capabilities
- Default models per provider
- Temperature settings
- Context windows and output limits

Code should NEVER duplicate this information. All code should call functions that read from engines.yaml.

## Success Metrics

| Metric | Before | After Phase 1 | Current | Target |
|--------|--------|---------------|---------|--------|
| Steps to enable RAG | 3+ clicks | 0 (automatic) | ✅ Done | ✅ Done |
| Visible settings truncation | Yes | Yes | Better | ✅ Done |
| Chat area width | ~70% | ~70% | ~100% | ✅ Done |
| Time to first RAG query | Manual index required | Auto-indexed | ✅ Done | ✅ Done |
| Markdown rendering | None | Basic | Full with syntax highlighting | ✅ Done |
| Docker deployment | Manual | Manual | docker compose up | ✅ Done |
