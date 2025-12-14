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

## Phase 3: React Frontend (Pending)

**Goal**: Modern web UI to replace Streamlit

### Planned

1. **React/Next.js Frontend**
   - Connect to FastAPI backend at `/api/*`
   - SSE handling for streaming chat responses
   - Responsive design for desktop and mobile

2. **Core Features**
   - Workspace selector dropdown
   - Model selector with provider grouping
   - Chat interface with streaming
   - Index status indicator and management

3. **Technical Stack**
   - Next.js 14+ with App Router
   - TypeScript
   - Tailwind CSS
   - SSE client for streaming

### Files to Create

- `ragbot-web/` or `web/` directory with Next.js project

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
