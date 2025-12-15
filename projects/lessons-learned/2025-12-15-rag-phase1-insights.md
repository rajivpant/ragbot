# Lessons Learned: RAG Phase 1 Implementation

**Date:** 2025-12-15
**Project:** RAG Relevance Improvements
**Phase:** Phase 1 Foundation

## Summary

Successfully implemented Phase 1 of RAG relevance improvements with 22 new tests passing. Key insights about RAG architecture and query handling.

## Key Lessons

### 1. Contractions Are More Important Than Expected

**The Problem:**
"what's in my biography" failed to find the biography file, while "show me my biography" worked.

**Root Cause:**
MiniLM embeddings treated "what's" as a single token with different semantics than "what is". The apostrophe broke keyword matching entirely.

**The Fix:**
Simple contraction expansion before embedding and keyword matching:
```python
query = query.replace("what's", "what is")
```

**Lesson:**
Text normalization is critical for hybrid search. What seems like a minor linguistic variation can completely break retrieval.

### 2. Full Document Retrieval Should Be a First-Class Feature

**The Problem:**
RAG by default returns chunks, but users asking "show me my biography" expect the complete document.

**The Insight:**
There are two fundamentally different query types:
1. **Information synthesis** - "How do I write a blog post?" → needs relevant chunks from multiple sources
2. **Document lookup** - "Show me my biography" → needs one complete document

**The Fix:**
Pattern detection + dedicated full document retrieval path. When we detect a lookup request, bypass chunked retrieval entirely.

**Lesson:**
RAG architectures should distinguish between these query types and handle them differently.

### 3. 8x More Context Is Safe and Helpful

**The Change:**
Increased context budget from 2K to 16K tokens.

**Why It's Safe:**
- Modern models have 200K+ context windows
- 16K is still <10% of available context
- Cost increase is negligible for personal use

**Why It Helps:**
- More complete document coverage
- Less information loss from aggressive truncation
- Closer to Claude Desktop experience (which has ~40K+ tokens)

**Lesson:**
Don't over-optimize for context budget in quality-first applications. The models can handle much more than we typically give them.

### 4. Pattern-Based Query Classification Works Surprisingly Well

**The Approach:**
Used regex patterns to detect document lookup requests:
```python
DOCUMENT_LOOKUP_PATTERNS = [
    r"^show\s+(?:me\s+)?(?:my\s+|the\s+)?(.+)$",
    r"^what(?:'s| is)\s+in\s+(?:my\s+|the\s+)?(.+)$",
    # ...
]
```

**Results:**
- Fast (no LLM call needed)
- Deterministic (same query always classified the same way)
- Accurate (patterns cover common cases well)

**Lesson:**
Not everything needs an LLM. Simple heuristics can handle many classification tasks effectively and more reliably.

### 5. Re-ranking Boost Values Matter

**The Change:**
Increased filename match boost from 0.3 to 0.5 per term, title match from 0.2 to 0.3.

**Why:**
Original values weren't strong enough to overcome semantic similarity scores for irrelevant-but-semantically-similar content.

**Lesson:**
Re-ranking parameters need tuning. Start with higher boosts for explicit matches (filename, title) since users mentioning these expect exact matches.

### 6. Defaults Must Be Updated Everywhere (Full-Stack Awareness)

**The Problem:**
After implementing 16K context in `rag.py`, the web UI still showed 2000 tokens and returned truncated results.

**Root Cause:**
The default value existed in **4 different locations**:
1. `src/rag.py` - `get_relevant_context()` default parameter ✅ updated
2. `src/ragbot/core.py` - `chat()` function default ✅ updated
3. `src/ragbot/core.py` - `chat_streaming()` kwargs.get fallback ❌ missed
4. `src/ragbot/models.py` - `ChatRequest` Pydantic model ❌ missed
5. `web/src/components/Chat.tsx` - React `useState(2000)` ❌ missed

**The Fix:**
```bash
grep -r "2000" --include="*.py" --include="*.tsx" | grep -i "rag\|token\|context"
```
Then updated all 4 remaining locations.

**Lesson:**
When changing defaults in a full-stack application:
1. **Grep for the old value** across the entire codebase
2. **Trace the data flow** from UI → API → backend → library
3. **Test from the UI**, not just unit tests (unit tests may use defaults that bypass the API layer)

## What Would I Do Differently?

1. **Start with full document mode from the beginning** - Should have been in the original RAG implementation

2. **Add query preprocessing earlier** - The contraction issue was obvious in hindsight

3. **Test with real user queries** - The "what's" vs "what is" issue only emerged from actual usage

## Metrics to Track

For future phases, track:
- Document lookup success rate (% of "show me X" queries returning the correct document)
- Retrieval precision (% of retrieved chunks actually relevant)
- Context utilization (how much of 16K budget typically used)

## Related Documents

- [implementation-phase1.md](../active/rag-relevance-improvements/implementation-phase1.md)
- [architecture.md](../active/rag-relevance-improvements/architecture.md)
