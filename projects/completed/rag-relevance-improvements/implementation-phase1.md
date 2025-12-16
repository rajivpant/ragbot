# Phase 1 Implementation Details

**Completed:** 2025-12-15

## Summary

Phase 1 implements the foundation improvements for RAG relevance:

| Feature | Status | Impact |
|---------|--------|--------|
| 16K token context budget | ✅ Done | 8x more context available |
| Full document retrieval | ✅ Done | Perfect "show me X" responses |
| Contraction expansion | ✅ Done | "what's" → "what is" for matching |
| Enhanced filename matching | ✅ Done | Stronger boost for filename/title matches |
| Unit tests | ✅ Done | 22 new tests, all passing |

## Changes Made

### 1. Query Preprocessing (`src/rag.py`)

Added new functions for query preprocessing:

```python
# Contraction expansion
expand_contractions(query: str) -> str
# "what's in my biography" → "what is in my biography"

# Document request detection
detect_document_request(query: str) -> Tuple[bool, Optional[str]]
# Returns (True, "biography") for "show me my biography"

# Full preprocessing pipeline
preprocess_query(query: str) -> Dict[str, any]
# Returns: original_query, processed_query, is_document_request, document_hint, search_terms
```

**Contractions supported:** 40+ common English contractions including:
- Question words: what's, where's, who's, how's
- Negatives: can't, won't, don't, doesn't, didn't, etc.
- Pronouns: I'm, you're, we're, they're, I've, you've, etc.

**Document lookup patterns detected:**
- "show me [my/the] X"
- "display [my/the] X"
- "get [me] [my/the] X"
- "read [my/the] X"
- "open [my/the] X"
- "use [the] X [runbook]"
- "what's in [my/the] X"
- "what is in [my/the] X"
- "what does [my/the] X say/contain/have"

### 2. Full Document Retrieval (`src/rag.py`)

Added `find_full_document()` function:

```python
find_full_document(workspace_name: str, document_hint: str, search_terms: List[str]) -> Optional[Dict]
```

**How it works:**
1. Scrolls through all indexed chunks in the collection
2. Groups chunks by source file
3. Scores each file based on:
   - Filename word match: +10 per matching word
   - Title word match: +5 per matching word
   - Search term in filename: +3 per term
   - Search term in title: +2 per term
   - Substring match (e.g., "bio" in "biography"): +15
4. Selects best matching file
5. Reconstructs full document from chunks (handles overlap)
6. Returns complete content with metadata

### 3. Enhanced Search Function (`src/rag.py`)

Updated `search()` function:

```python
search(workspace_name, query, limit=5, content_type=None, use_preprocessing=True)
```

Changes:
- Added `use_preprocessing` parameter (default: True)
- Uses preprocessed query for embedding
- Uses extracted search terms for re-ranking
- Increased re-ranking boosts:
  - Filename match: 0.3 → 0.5 per term
  - Title match: 0.2 → 0.3 per term

### 4. Updated Context Retrieval (`src/rag.py`)

Updated `get_relevant_context()`:

```python
get_relevant_context(workspace_name, query, max_tokens=16000)  # Was 2000
```

**New flow:**
1. Preprocess query
2. If document request detected:
   - Try full document retrieval first
   - If document fits in budget, return it complete
   - Otherwise, fall back to chunk retrieval
3. For general queries:
   - Fetch 100 results (was 50)
   - Apply re-ranking with preprocessed search terms
   - Build context within token budget
   - Include sources summary in output

### 5. Core Integration (`src/ragbot/core.py`)

Updated `chat()` function default:

```python
rag_max_tokens: int = 16000  # Was 2000
```

## Test Coverage

Created `tests/test_rag_phase1.py` with 22 tests:

| Test Class | Tests | Purpose |
|------------|-------|---------|
| TestContractionExpansion | 6 | Verify contraction handling |
| TestDocumentRequestDetection | 5 | Verify pattern matching |
| TestQueryPreprocessing | 3 | Verify full preprocessing |
| TestSearchWithPreprocessing | 2 | Verify search integration |
| TestContextBudget | 2 | Verify 16K defaults |
| TestFullDocumentRetrieval | 1 | Verify structure |
| TestDocumentLookupPatterns | 1 | Verify all patterns |
| TestIntegration | 2 | End-to-end verification |

**Test results:** All 102 tests pass (22 new + 80 existing)

## Files Modified

| File | Changes |
|------|---------|
| `src/rag.py` | +250 lines (preprocessing, full doc retrieval, enhanced search) |
| `src/ragbot/core.py` | 2 lines (rag_max_tokens defaults in both chat functions) |
| `src/ragbot/models.py` | 1 line (ChatRequest.rag_max_tokens default) |
| `web/src/components/Chat.tsx` | 1 line (useState default for ragMaxTokens) |
| `README.md` | Updated RAG documentation |
| `tests/test_rag_phase1.py` | New file, 22 tests |

## Expected Impact

| Query | Before | After |
|-------|--------|-------|
| "what's in my biography" | Fragmented chunks | Full document |
| "show me my biography" | Good (already worked) | Full document (even better) |
| "use the author-bios runbook" | May miss | Full document |
| General queries | 2K context | 16K context (8x more) |

## Next Steps (Phase 2)

See [architecture.md](architecture.md) for Phase 2 plans:
- Add Planner stage using Haiku
- Multi-query expansion (5-10 variations)
- HyDE (Hypothetical Document Embeddings)

## Lessons Learned

1. **Contractions matter more than expected** - "what's" vs "what is" caused the original biography retrieval issue

2. **Full document mode is critical** - For targeted queries, users expect complete documents, not chunks

3. **8x context budget is safe** - Models have 200K+ context, 16K is still <10%

4. **Pattern-based detection works well** - Regex patterns reliably identify document lookup requests without needing an LLM

5. **Update ALL default locations** - The 16K default was set in `rag.py` and one `core.py` function, but missed:
   - `core.py` second chat function (kwargs.get fallback)
   - `models.py` (Pydantic ChatRequest model)
   - `Chat.tsx` (React useState initial value)

   This caused the web UI to still use 2000 tokens even though the backend supported 16K. **Always grep for the old value across the entire codebase.**
