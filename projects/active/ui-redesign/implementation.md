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
   - Connect to FastAPI backend
   - SSE handling for streaming chat
   - Responsive design

2. **Features**
   - Workspace selector
   - Model selector
   - Chat interface with streaming
   - Index management UI

---

## Phase 4: Index Management Screen (Priority: Medium)

**Goal**: Dedicated screen for index operations

### Tasks

1. **Create index management page**
   - Could be a separate Streamlit page or modal
   - Show all workspaces and their index status

2. **Index operations**
   - Rebuild index from compiled content
   - Recompile from sources (trigger AI Knowledge Compiler)
   - Clear index
   - Index all workspaces

3. **Status indicators**
   - ✅ Ready: Index exists and is current
   - ⚠️ Stale: Index exists but source files are newer
   - ❌ None: No index exists

### Files to Modify

- New: `src/ui/index_management.py`
- `src/rag.py` (add status checking methods)

---

## Phase 5: Compiler Integration (Priority: Low)

**Goal**: Ability to recompile from sources within Ragbot

### Tasks

1. **Add compiler trigger**
   - Call AI Knowledge Compiler from Ragbot
   - Show compilation progress
   - Refresh index after compilation

2. **Watch mode** (future)
   - Detect source file changes
   - Auto-recompile and re-index

### Files to Modify

- `src/ui/index_management.py`
- `src/compiler/` (if needed)

---

## Technical Considerations

### Streamlit Limitations

- No native modal support (use `st.dialog` in newer versions or custom CSS)
- Limited layout control (use `st.columns`, custom CSS)
- State management complexity (use session state carefully)

### RAG Auto-Indexing

- First query may be slow (indexing happens in background)
- Need progress indicator during indexing
- Consider lazy indexing (index on demand, not all at once)

### Mobile Responsiveness

- Top bar should collapse gracefully on mobile
- Consider hamburger menu for mobile

---

## Open Questions

1. **Multi-page vs Single-page**: Should Index Management be a separate page or a modal?
2. **Keyboard Shortcuts**: Should we add keyboard shortcuts (Cmd+K for settings, etc.)?
3. **Theme Support**: Should we support dark/light themes?
4. **Mobile First**: How important is mobile support?

---

## References

- [Claude Desktop UI](https://claude.ai) - Reference for collapsible sidebar
- [ChatGPT UI](https://chatgpt.com) - Reference for clean chat interface
- [Streamlit Components](https://docs.streamlit.io/library/components) - Available UI elements
