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

## Phase 2: Top Bar Layout (Priority: Medium) 🚧 DEFERRED

**Goal**: Replace narrow sidebar with horizontal top bar

**Status**: Attempted and reverted due to Streamlit framework limitations.

### Issues Encountered

1. **Streamlit header overlap** - Custom top bar elements were covered by Streamlit's built-in header
2. **Deploy button** - Streamlit's "Deploy" button appeared and could not be hidden via CSS
3. **Dropdown rendering** - Selectboxes rendered as gray bars instead of proper dropdowns
4. **CSS limitations** - Streamlit's internal styling conflicts with custom CSS overrides

### Original Planned Tasks

1. **Create new layout structure**
   - Use `st.columns()` for top bar elements
   - Remove sidebar via CSS
   - Full-width chat area

2. **Implement top bar components**
   - Workspace selector (dropdown)
   - Combined model selector
   - Creativity selector
   - Settings popover

### Future Approach

Per strategic decision (2025-12-14), these layout improvements are deferred until:
- Migration to FastAPI backend + React/Next.js frontend
- This will enable proper UI control, mobile apps, and voice interfaces
- See README.md for full rationale

---

## Phase 3: Settings Modal (Priority: Medium) 🚧 DEFERRED

**Goal**: Replace sidebar settings with modal dialog

**Status**: Merged into Phase 2, deferred along with it.

### Original Planned Tasks

1. **Create settings popover**
   - Use `st.popover()` for settings panel
   - Organize settings into logical groups

2. **Settings groups**
   - RAG Configuration
   - Response Settings
   - Conversation controls
   - Advanced options

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
