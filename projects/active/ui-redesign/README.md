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

A new layout with:
- Top bar for primary controls
- RAG enabled by default
- Auto-indexing when index is missing
- Dedicated index management screen
- Full-width chat area

## Documents

| Document | Purpose |
|----------|---------|
| [design.md](design.md) | Detailed UI mockups and design specifications |
| [implementation.md](implementation.md) | Phase-by-phase implementation guide |

## Quick Links

- **Source Code:** `ragbot/src/ragbot_streamlit.py`

## Related Projects

| Project | Location | Description |
|---------|----------|-------------|
| **AI Knowledge Architecture** | [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture) | Repository architecture this UI works with |
| **AI Knowledge Compiler** | [ragbot/projects/active/ai-knowledge-compiler](../ai-knowledge-compiler/) | Compiler for rebuild functionality |

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1: RAG as Default | ✅ Complete | Enable RAG by default, auto-indexing |
| Phase 2: Top Bar Layout | 🚧 Deferred | Replace sidebar with horizontal top bar |
| Phase 3: Settings Modal | 🚧 Deferred | Modal dialog for advanced settings |
| Phase 4: Index Management | Pending | Dedicated index operations screen |
| Phase 5: Compiler Integration | Pending | Rebuild from sources within UI |

### Phase 1 Completed (2025-12-14)

Changes made:
- RAG checkbox now defaults to ON when workspace has ai-knowledge content
- RAG section moved from Advanced Settings to main sidebar (prominent placement)
- Index status indicator shows ✅ Ready / ⚠️ Not indexed / ❓ Unknown
- Auto-indexing on first query when index is missing
- Index button label changes based on status (Index Workspace / Rebuild Index)
- `helpers.py` updated to default `use_rag=True`

### Phase 2 & 3 Deferred

**Reason**: Streamlit's layout limitations make a proper top bar difficult:
- Streamlit header overlaps custom top elements
- Deploy button cannot be hidden
- Need to consider migration to React/Next.js for better UI control

**Future approach**: Build a FastAPI backend service, then create React frontend that can be:
- Web app (React/Next.js)
- Mobile apps (React Native or native iOS/Android)
- Voice interfaces
- This aligns with RaGenie architecture plans

## Success Metrics

| Metric | Before | After Phase 1 | Target |
|--------|--------|---------------|--------|
| Steps to enable RAG | 3+ clicks | 0 (automatic) | ✅ Done |
| Visible settings truncation | Yes | Yes | Deferred |
| Chat area width | ~70% | ~70% | Deferred |
| Time to first RAG query | Manual index required | Auto-indexed | ✅ Done |
