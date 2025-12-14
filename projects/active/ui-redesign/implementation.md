# Implementation Guide

> Phase-by-phase implementation plan for the Ragbot UI redesign.

## Phase 1: RAG as Default (Priority: High)

**Goal**: Make RAG work automatically without user intervention

### Tasks

1. **Enable RAG by default** in `ragbot_streamlit.py`
   - Change `use_rag = st.checkbox(..., value=False)` to `value=True`
   - Move RAG toggle out of Advanced Settings

2. **Auto-index on first query**
   - Check if index exists for workspace
   - If not, build index automatically (show progress indicator)
   - Cache index status to avoid repeated checks

3. **Update helpers.py**
   - Change `use_rag=False` default to `use_rag=True`
   - Add auto-index logic to `chat()` function

### Files to Modify

- `src/ragbot_streamlit.py`
- `src/helpers.py`
- `src/rag.py`

---

## Phase 2: Top Bar Layout (Priority: High)

**Goal**: Replace narrow sidebar with horizontal top bar

### Tasks

1. **Create new layout structure**
   - Use `st.columns()` for top bar elements
   - Remove sidebar (`st.sidebar`)
   - Use full page width for chat

2. **Implement top bar components**
   - Workspace selector (dropdown)
   - Model selector (dropdown with provider grouping)
   - Creativity selector (preset dropdown)
   - Settings button (opens modal)
   - Index button (opens index management)

3. **Style improvements**
   - Custom CSS for compact top bar
   - Responsive design for different screen sizes

### Files to Modify

- `src/ragbot_streamlit.py`
- New: `src/ui/top_bar.py`
- New: `src/ui/styles.css`

---

## Phase 3: Settings Modal (Priority: Medium)

**Goal**: Replace sidebar settings with modal dialog

### Tasks

1. **Create modal component**
   - Use Streamlit's `st.dialog` or custom implementation
   - Organize settings into logical groups

2. **Settings groups**
   - Model Configuration (provider, model, max tokens)
   - RAG Configuration (toggle, context tokens)
   - Conversation (history stats, clear button)
   - Debug Info (file counts, token counts, index stats)

### Files to Modify

- `src/ragbot_streamlit.py`
- New: `src/ui/settings_modal.py`

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
