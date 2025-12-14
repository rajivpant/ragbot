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
| Phase 3: Core Library | ✅ Complete | `src/ragbot/` package extraction |
| Phase 4: React Frontend | Pending | Modern web UI (replaces Streamlit) |

### Phase 1 Completed (2025-12-14)

Changes made:
- RAG checkbox now defaults to ON when workspace has ai-knowledge content
- RAG section moved from Advanced Settings to main sidebar (prominent placement)
- Index status indicator shows ✅ Ready / ⚠️ Not indexed / ❓ Unknown
- Auto-indexing on first query when index is missing
- Index button label changes based on status (Index Workspace / Rebuild Index)
- `helpers.py` updated to default `use_rag=True`

### Phase 2 & 3: FastAPI Backend (Complete)

**Status**: FastAPI backend implemented (2025-12-14)

The FastAPI backend is now complete and ready for frontend development:
- REST API at `src/api/` with full OpenAPI documentation
- SSE streaming for chat responses
- Workspace management endpoints
- Model configuration endpoints
- Health check endpoint

**API Endpoints**:
- `POST /api/chat` - Chat with streaming (SSE)
- `GET /api/workspaces` - List workspaces
- `GET /api/workspaces/{name}` - Workspace details
- `POST /api/workspaces/{name}/index` - Trigger indexing
- `GET /api/models` - List available models
- `GET /api/config` - Get configuration

**Next Steps**: Build React/Next.js frontend that can be:
- Web app (React/Next.js)
- Mobile apps (React Native or native iOS/Android)
- Voice interfaces

## Success Metrics

| Metric | Before | After Phase 1 | Target |
|--------|--------|---------------|--------|
| Steps to enable RAG | 3+ clicks | 0 (automatic) | ✅ Done |
| Visible settings truncation | Yes | Yes | Deferred |
| Chat area width | ~70% | ~70% | Deferred |
| Time to first RAG query | Manual index required | Auto-indexed | ✅ Done |
