# Implementation Guide

> Phase-by-phase implementation plan for the Ragbot UI redesign.

## Phase 1: RAG as Default (Priority: High) ✅ COMPLETE

**Goal**: Make RAG work automatically without user intervention

### Tasks

1. ✅ **Enable RAG by default** in `ragbot_streamlit.py`
   - Changed `use_rag = st.checkbox(..., value=has_ai_knowledge)` - defaults ON when content exists
   - Moved RAG section out of Advanced Settings to main sidebar
   - Added index status indicator (✅ Ready / ⚠️ Not indexed / etc.)

2. ✅ **Auto-index on first query**
   - Check if index exists for workspace on page load
   - Auto-index triggered when RAG query made without index
   - Uses `st.status()` to show indexing progress

3. ✅ **Update helpers.py**
   - Changed `use_rag=False` default to `use_rag=True`
   - Updated docstring to reflect new default

### Files Modified

- `src/ragbot_streamlit.py` - RAG UI moved, auto-indexing added
- `src/helpers.py` - Default changed to `use_rag=True`

---

## Phase 2: FastAPI Backend ✅ COMPLETE

**Goal**: Build REST API backend to enable modern frontend development

**Status**: Implemented (2025-12-14)

### Completed

1. **Core Library Extraction** (`src/ragbot/`)
   - `core.py` - Chat engine with streaming support
   - `workspaces.py` - Workspace discovery and management
   - `models.py` - Pydantic models for API
   - `config.py` - Configuration and model definitions
   - `exceptions.py` - Custom exceptions

2. **FastAPI Application** (`src/api/`)
   - `main.py` - FastAPI app with CORS, health check
   - `routers/chat.py` - Chat endpoint with SSE streaming
   - `routers/workspaces.py` - Workspace endpoints
   - `routers/models.py` - Model listing
   - `routers/config.py` - Configuration endpoint

3. **Docker Configuration**
   - Updated `Dockerfile` with FastAPI as default
   - Updated `docker-compose.yml` with ragbot-api service
   - Streamlit moved to optional profile

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with SSE streaming |
| `/api/workspaces` | GET | List all workspaces |
| `/api/workspaces/{name}` | GET | Get workspace details |
| `/api/workspaces/{name}/index` | GET/POST | Index status/trigger |
| `/api/models` | GET | List available models |
| `/api/config` | GET | Get configuration |
| `/health` | GET | Health check |

### Files Created

- `src/ragbot/__init__.py`
- `src/ragbot/core.py`
- `src/ragbot/workspaces.py`
- `src/ragbot/models.py`
- `src/ragbot/config.py`
- `src/ragbot/exceptions.py`
- `src/api/__init__.py`
- `src/api/main.py`
- `src/api/dependencies.py`
- `src/api/routers/chat.py`
- `src/api/routers/workspaces.py`
- `src/api/routers/models.py`
- `src/api/routers/config.py`
- `ragbot_api` (shell script)

---

## Phase 3: React Frontend ✅ COMPLETE

**Goal**: Modern web UI to replace Streamlit

**Status**: Implemented (2025-12-14)

### Completed

1. **Next.js Project Setup** (`web/`)
   - Next.js 16 with App Router
   - TypeScript configuration
   - Tailwind CSS styling

2. **API Client** (`web/src/lib/api.ts`)
   - Full API client with TypeScript types
   - SSE streaming with async generator
   - All endpoints: workspaces, models, config, chat

3. **Components** (`web/src/components/`)
   - `Chat.tsx` - Main chat interface with streaming
   - `ChatMessage.tsx` - Message display (user/assistant)
   - `ChatInput.tsx` - Input with Enter key support
   - `WorkspaceSelector.tsx` - Workspace dropdown with status
   - `ModelSelector.tsx` - Model dropdown grouped by provider

4. **Features**
   - Workspace selector with status indicators
   - Model selector with provider grouping
   - Settings panel (collapsible)
   - RAG toggle
   - Clear chat button
   - Auto-scroll to new messages
   - Responsive design

### Files Created

- `web/` - Next.js project root
- `web/src/lib/api.ts` - API client
- `web/src/components/Chat.tsx`
- `web/src/components/ChatInput.tsx`
- `web/src/components/ChatMessage.tsx`
- `web/src/components/WorkspaceSelector.tsx`
- `web/src/components/ModelSelector.tsx`
- `web/src/components/index.ts`
- `web/src/app/page.tsx` - Updated
- `web/src/app/layout.tsx` - Updated

---

## Phase 4: Docker Setup ✅ COMPLETE

**Goal**: Full Docker Compose configuration for development and deployment

**Status**: Complete (2025-12-14)

### Completed

1. **Docker Compose Configuration**
   - `docker-compose.yml` with ragbot-api and ragbot-web services
   - `web/Dockerfile` for Next.js frontend
   - Named volume for node_modules persistence

2. **Environment Configuration**
   - API URL configuration via environment variables
   - Support for .env file

---

## Phase 5: Config & Model Fixes ✅ COMPLETE

**Goal**: Remove hardcoded configuration, fix all model integrations

**Status**: Complete (2025-12-14)

### Completed

1. **Configuration Cleanup**
   - Removed hardcoded MODELS dict from `src/ragbot/config.py`
   - All model/provider config now loads from `engines.yaml`
   - Added new config functions: `load_engines_config()`, `get_providers()`, `get_temperature_settings()`

2. **API Endpoints Added**
   - `/api/models/providers` - List providers from engines.yaml
   - `/api/models/temperature-settings` - Get temperature presets
   - `/api/config/keys` - Detailed key status per provider

3. **Model Fixes (All 9 Models Tested)**
   - OpenAI: gpt-5-mini, gpt-5.2-chat-latest, gpt-5.2
   - Anthropic: claude-haiku-4-5-20251001, claude-sonnet-4-5-20250929, claude-opus-4-5-20251101
   - Google: gemini/gemini-2.5-flash-lite, gemini/gemini-2.5-flash, gemini/gemini-3-pro-preview

4. **Technical Fixes**
   - OpenAI GPT-5 models: temperature=1.0 (only supported value)
   - gpt-5-mini: uses `max_completion_tokens` instead of `max_tokens`
   - Made ChatRequest.temperature Optional (uses model default from engines.yaml)
   - Added `litellm.drop_params=True` for unsupported parameter handling

5. **API Key UX Improvements**
   - Show key source (workspace/default) in UI
   - Auto-switch to provider with available key when workspace changes
   - Provider dropdown filters to only show providers with keys

### Files Modified

- `src/ragbot/config.py` - Removed hardcoded models, added engines.yaml loading
- `src/ragbot/core.py` - Model-specific parameter handling
- `src/ragbot/models.py` - Optional temperature field
- `src/ragbot/keystore.py` - Added get_key_status()
- `src/api/routers/config.py` - Added /keys endpoint
- `web/src/lib/api.ts` - Added getKeysStatus()
- `web/src/components/SettingsPanel.tsx` - Key source display, provider filtering
- `engines.yaml` - Updated model IDs and parameters

---

## Phase 6: Testing (Planned)

**Goal**: Comprehensive test coverage for models and API

**Status**: Planned

### Planned Tasks

1. **Model Integration Tests** (`tests/test_models_integration.py`)
   - Test each model in engines.yaml with a simple prompt
   - Verify streaming responses work
   - Catch configuration issues early

2. **Config Unit Tests** (`tests/test_config.py`)
   - `load_engines_config()` returns valid structure
   - `get_all_models()` returns models from engines.yaml
   - `get_default_model()` returns valid model ID
   - `get_temperature_settings()` returns presets

3. **Keystore Unit Tests** (`tests/test_keystore.py`)
   - `get_api_key()` returns key from correct source
   - `get_key_status()` returns correct status
   - `check_api_keys()` returns availability

4. **API Endpoint Tests** (`tests/test_api.py`)
   - `/api/models` returns models
   - `/api/config` returns config
   - `/api/config/keys` returns key status
   - `/api/workspaces` returns workspaces
   - `/api/chat` handles streaming

5. **Update Existing Tests**
   - Review and fix any tests broken by recent changes
   - Ensure tests don't have hardcoded model names

---

## Phase 7: Cleanup (Future)

**Goal**: Remove deprecated code and finalize migration

### Planned

1. **Remove Streamlit**
   - Delete `src/ragbot_streamlit.py`
   - Remove Streamlit from `requirements.txt`
   - Remove `ragbot-web` service from `docker-compose.yml`
   - Update documentation

2. **Remove Legacy Code**
   - Clean up `src/helpers.py` (now just re-exports from `src/ragbot/`)
   - Remove `RAGBOT_DATA_ROOT` references from legacy files
   - Remove Pinecone references (replaced by Qdrant)

3. **Docker Optimization**
   - Single-service `docker-compose.yml`
   - Add Next.js build to Dockerfile (optional)

---

## Technical Considerations

### API Integration

- FastAPI backend runs on port 8000
- CORS configured for localhost:3000
- SSE streaming via EventSource API

### Mobile Responsiveness

- Top bar should collapse gracefully on mobile
- Consider hamburger menu for mobile

---

## References

- [Claude Desktop UI](https://claude.ai) - Reference for clean chat interface
- [ChatGPT UI](https://chatgpt.com) - Reference for streaming responses
- [Next.js Documentation](https://nextjs.org/docs) - React framework
