# Phase 2 Implementation Details

**Completed:** 2025-12-15

## Summary

Phase 2 implements query intelligence with LLM-powered features:

| Feature | Status | Impact |
|---------|--------|--------|
| Query Planner stage | ✅ Done | LLM analyzes intent, selects retrieval strategy |
| Multi-query expansion | ✅ Done | 5-7 search variations for better recall |
| HyDE (Hypothetical Document Embeddings) | ✅ Done | Bridges question-answer semantic gap |
| Provider-agnostic model selection | ✅ Done | Uses each provider's fast model via categories |
| Unit tests | ✅ Done | 32 new tests, all passing (148 total) |

## Key Design Decisions

### 1. Provider-Agnostic Fast Model Selection

**Requirement:** Don't hardcode model names like "haiku" - use model categories from engines.yaml.

**Implementation:** Added two new functions to `config.py`:

```python
def get_model_by_category(provider: str, category: str) -> Optional[str]:
    """Get a model ID for a specific provider and category.
    Categories: "small" (fast), "medium" (balanced), "large" (flagship)
    """

def get_fast_model_for_provider(model_id: str) -> Optional[str]:
    """Get the fast (small category) model for the same provider as model_id."""
```

**Result:**
- Anthropic users get `claude-haiku-4-5-20251001` for auxiliary calls
- OpenAI users get `gpt-5-mini`
- Google users get `gemini-2.5-flash-lite`

This ensures:
1. Consistent API key usage (same provider for main and auxiliary calls)
2. Consistent billing (no surprise charges from different providers)
3. Future-proof (new providers/models just need engines.yaml updates)

### 2. Graceful Fallback to Phase 1 Heuristics

**Design:** If LLM calls fail (API issues, rate limits, no API key), fall back to Phase 1's pattern-based approach.

**Implementation:** Each Phase 2 function has a fallback path:
- `plan_query()` → Falls back to `preprocess_query()` heuristics
- `expand_query()` → Falls back to term extraction and simple variations
- `generate_hyde_document()` → Returns `None` (HyDE is optional)

**Result:** RAG always works, just with reduced intelligence when LLM unavailable.

## Changes Made

### 1. New Functions in `src/rag.py`

```python
# Provider-agnostic fast model selection
_get_fast_model(user_model: str) -> Optional[str]
_call_fast_llm(prompt: str, user_model: str, workspace: str) -> Optional[str]

# Phase 2 Query Intelligence
plan_query(query: str, user_model: str, workspace: str) -> Dict
expand_query(query: str, query_type: str, user_model: str, workspace: str) -> Dict
generate_hyde_document(query: str, user_model: str, workspace: str) -> Optional[str]
enhanced_preprocess_query(query: str, ...) -> Dict
```

### 2. Updated `get_relevant_context()`

New signature:
```python
def get_relevant_context(
    workspace_name: str,
    query: str,
    max_tokens: int = 16000,
    user_model: Optional[str] = None,  # NEW: for Phase 2
    use_phase2: bool = True             # NEW: enable/disable Phase 2
) -> str:
```

New behavior:
1. Calls `enhanced_preprocess_query()` for Phase 2 intelligence
2. Searches with multiple expanded queries
3. Merges and deduplicates results
4. If HyDE enabled, also searches with hypothetical document
5. Falls back to Phase 1 if LLM unavailable

### 3. Updated `src/ragbot/core.py`

Both `chat()` and `chat_streaming()` now pass `user_model=model` to `get_relevant_context()`, enabling provider-agnostic Phase 2 features.

### 4. New Functions in `src/ragbot/config.py`

```python
def get_model_by_category(provider: str, category: str) -> Optional[str]:
    """Get model by provider and category from engines.yaml."""

def get_fast_model_for_provider(model_id: str) -> Optional[str]:
    """Get fast model for same provider as given model."""
```

## Prompt Templates

### Planner Prompt

```
You are a query planning assistant for a RAG system.
Analyze the user's query and create an execution plan.

User query: "{query}"

Respond with JSON:
{
  "query_type": "document_lookup" | "factual_qa" | "procedural" | "multi_step",
  "retrieval_strategy": "full_document" | "semantic_chunks" | "hybrid",
  "filename_hints": ["hint1", "hint2"],
  "answer_style": "return_content" | "synthesize" | "list_sources",
  "complexity": "simple" | "moderate" | "complex"
}
```

### Multi-Query Expansion Prompt

```
Generate 5-7 search query variations for better recall.

Original query: "{query}"
Query type: {query_type}

Respond with JSON:
{
  "queries": ["query1", "query2", ...],
  "key_entities": ["entity1", ...],
  "filename_patterns": ["pattern1", ...]
}
```

### HyDE Prompt

```
Generate a hypothetical document excerpt that would answer this query.
Write 2-3 sentences that a relevant document would contain.
```

## Test Coverage

Created `tests/test_rag_phase2.py` with 32 tests:

| Test Class | Tests | Purpose |
|------------|-------|---------|
| TestGetFastModel | 5 | Provider-agnostic model selection |
| TestPlannerPrompt | 3 | Planner prompt structure |
| TestPlanQuery | 5 | Query planning with LLM and fallback |
| TestExpandQuery | 4 | Multi-query expansion |
| TestGenerateHydeDocument | 3 | HyDE generation |
| TestEnhancedPreprocessQuery | 6 | Combined Phase 2 preprocessing |
| TestMultiQueryPrompt | 2 | Multi-query prompt structure |
| TestProviderAgnosticIntegration | 2 | Provider-agnostic integration |
| TestFallbackBehavior | 2 | Graceful degradation |

**Test results:** All 148 tests pass (32 new + 116 existing)

## Files Modified

| File | Changes |
|------|---------|
| `src/rag.py` | +250 lines (Phase 2 functions, enhanced preprocessing) |
| `src/ragbot/config.py` | +30 lines (category-based model selection) |
| `src/ragbot/core.py` | 4 lines (pass user_model to get_relevant_context) |
| `tests/test_rag_phase2.py` | New file, 32 tests |

## Expected Impact

| Scenario | Before (Phase 1) | After (Phase 2) |
|----------|------------------|-----------------|
| Query: "how do I write a blog post" | May miss procedural docs | Planner identifies procedural intent, targets runbooks |
| Query: "authentication" | Single search | 5-7 variations: "auth", "login", "credentials", etc. |
| Query: "What is OAuth?" | Semantic search | HyDE + semantic search (bridges question-answer gap) |
| Different LLM provider | N/A | Uses provider's own fast model for auxiliary calls |

## Architecture Notes

### Data Flow

```
User Query
    │
    ▼
enhanced_preprocess_query()
    ├──> plan_query() ─────────> Fast LLM (Planner)
    │                              │
    │    ┌─────────────────────────┘
    │    │ Query Type + Strategy
    │    ▼
    ├──> expand_query() ───────> Fast LLM (Multi-Query)
    │                              │
    │    ┌─────────────────────────┘
    │    │ 5-7 Query Variations
    │    ▼
    └──> generate_hyde_document() > Fast LLM (HyDE)
         │
         │ Hypothetical Answer
         ▼
    get_relevant_context()
         ├──> Search with each expanded query
         ├──> Search with HyDE document
         ├──> Merge and deduplicate results
         └──> Return context within token budget
```

### Fallback Chain

```
Phase 2 LLM Features
    │ (if LLM fails)
    ▼
Phase 1 Heuristics
    ├── Pattern matching for document requests
    ├── Contraction expansion
    ├── Filename/title boosting
    └── Full document retrieval
```

## Lessons Learned

### 1. Category-Based Model Selection is Essential

Using engines.yaml categories (`small`, `medium`, `large`) instead of hardcoded model names ensures:
- Multi-provider support without code changes
- Consistent behavior as models are updated
- Easy customization per deployment

### 2. Fallback Design is Critical

Phase 2 features enhance RAG but shouldn't break it. By always falling back to Phase 1 heuristics, users get:
- Reliable operation even without LLM access
- Gradual degradation, not complete failure
- Same or better performance than Phase 1 baseline

### 3. JSON Response Parsing Needs Robustness

LLMs sometimes wrap JSON in markdown code blocks. The parsing code handles:
- Raw JSON: `{"key": "value"}`
- Markdown wrapped: ` ```json\n{"key": "value"}\n``` `
- Plain code blocks: ` ```\n{"key": "value"}\n``` `

## Next Steps (Phase 3)

See [architecture.md](architecture.md) for Phase 3 plans:
- Implement BM25/keyword search alongside vector search
- Add Reciprocal Rank Fusion (RRF) for result merging
- Implement LLM-based reranking with fast model
