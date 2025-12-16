# Potential Approaches

Brainstorming solutions to improve RAG relevance. These are options to evaluate, not a committed plan.

---

# Industry Research: How Leading AI Systems Handle RAG (December 2025)

## Key Finding: Query Rewriting is Standard Practice

Yes, the best systems **do** use a fast LLM to preprocess queries before vector search:

| System | Approach | Source |
|--------|----------|--------|
| **OpenAI File Search** | "Rewrites user queries to optimize them for search, breaks down complex queries into multiple parallel searches" | [OpenAI Docs](https://platform.openai.com/docs/guides/tools-file-search) |
| **Anthropic Claude** | Uses `retrieve()` to "iteratively search...until it decides enough has been collected" | [Anthropic Engineering](https://www.anthropic.com/engineering/contextual-retrieval) |
| **Perplexity** | Multi-stage pipeline with query expansion, dense + sparse retrieval fusion | [Vespa Case Study](https://vespa.ai/perplexity/) |

## State-of-the-Art Techniques (2025)

### 1. Query Rewriting Strategies

- **[HyDE (Hypothetical Document Embeddings)](https://medium.com/@florian_algo/advanced-rag-06-exploring-query-rewriting-23997297f2d1)**: Generate a hypothetical *answer*, embed that, use it for search. Bridges the semantic gap between questions and stored answers.

- **[Step-Back Prompting](https://www.promptingguide.ai/research/rag)**: Ask LLM for a more abstract version of the query. "What's in my biography?" → "What personal information documents exist?"

- **Query Decomposition**: Break multi-part queries into sub-queries. "biography and blog runbook" → two separate searches.

- **Contraction Expansion**: "what's" → "what is" (simple but critical for keyword matching)

### 2. Hybrid Search (Semantic + Keyword)

Every major system combines vector embeddings with BM25/keyword search:

| System | Results |
|--------|---------|
| **[Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)** | Combining contextual embeddings + BM25 gave **49% fewer retrieval failures** |
| **[OpenAI File Search](https://simonwillison.net/2024/Aug/30/openai-file-search/)** | Tunable `embedding_weight` and `text_weight` parameters |
| **[Perplexity](https://vespa.ai/perplexity/)** | "Fuses lexical, vector, and metadata signals in a unified ranking pipeline" |

### 3. Reranking (Post-Retrieval)

Retrieve many, rerank to fewer:

- **[Anthropic](https://www.anthropic.com/engineering/contextual-retrieval)**: Retrieves top **150**, reranks to top **20**, reducing error from 5.7% → **1.9%**
- **[OpenAI](https://platform.openai.com/docs/guides/tools-file-search)**: `ranking_options` with `score_threshold` to filter low-relevance

### 4. Contextual Chunk Enhancement

Don't embed raw chunks - add context first:

- **[Anthropic's approach](https://www.datacamp.com/tutorial/contextual-retrieval-anthropic)**: Prepend 50-100 tokens explaining what the chunk is about *before* embedding
- This alone: **35% reduction in retrieval failures**

### 5. Agentic RAG (Most Advanced)

**[Agentic RAG](https://www.ibm.com/think/topics/agentic-rag)** lets the LLM control retrieval:

- Decides **whether** to search at all
- Chooses **which** knowledge bases to query
- Performs **multi-step** retrieval (search → reason → search again)
- **Validates** retrieved context before using it

This is where [Perplexity](https://blog.bytebytego.com/p/how-perplexity-built-an-ai-google) and [Claude's retrieve()](https://www.anthropic.com/engineering/contextual-retrieval) are heading.

---

# Recommended Architecture for Ragbot

Since cost/tokens are NOT a consideration, optimize for **quality**:

## Tier 1: Implement Now (High Impact, Low Effort)

| # | Feature | Why |
|---|---------|-----|
| **1a** | Query rewriting with Haiku | Expand contractions, detect document names, optimize for search |
| **1b** | Increase context to 16K tokens | Models have 200K context, we use <1%. More context = better answers |
| **1c** | Full document mode | When filename matches strongly, return entire document |

## Tier 2: Implement Soon (High Impact, Medium Effort)

| # | Feature | Why |
|---|---------|-----|
| **2a** | Contextual embeddings | Re-index with context prepended (Anthropic's 35% improvement) |
| **2b** | Reranking with Haiku | Retrieve 50-100, use LLM to rerank to top 10-20 |
| **2c** | HyDE | Generate hypothetical answer, embed that for search |

## Tier 3: Future (Highest Impact, High Effort)

| # | Feature | Why |
|---|---------|-----|
| **3a** | Agentic retrieval | Let LLM decide when/what to search iteratively |
| **3b** | Multi-source routing | Different retrievers for different query types |
| **3c** | CRAG (Corrective RAG) | Validate retrieved content, search again if poor |

---

# Original Brainstormed Options

Below are the original options from initial brainstorming, preserved for reference:

## Option 1: Better Query Understanding

**Concept:** Detect when user is asking for a specific document by name.

**How it would work:**
- Parse query for document identifiers (biography, runbook names, file patterns)
- If detected, prioritize matching documents heavily
- Could use regex patterns or simple heuristics

**Pros:**
- Simple to implement
- Deterministic behavior
- Fast (no LLM call needed)

**Cons:**
- May miss implicit references
- Requires maintaining pattern list
- Doesn't help with content-based queries

**Example:**
```python
def detect_document_request(query):
    # Patterns that suggest document lookup
    patterns = [
        r"show me (?:my |the )?([\w-]+)",
        r"what's in (?:my |the )?([\w-]+)",
        r"use (?:the )?([\w-]+) runbook",
    ]
    # Match and boost those documents
```

---

## Option 2: Full Document Retrieval Mode

**Concept:** When a document name matches strongly, return the ENTIRE document, not just chunks.

**How it would work:**
- After search, check if top result has very high filename match score
- If so, fetch and return the complete source file
- Bypass chunk assembly for targeted queries

**Pros:**
- Solves "show me my biography" perfectly
- User gets complete, coherent content
- No fragmentation

**Cons:**
- Single document may exceed context budget
- Doesn't work for multi-document queries
- Need to balance with semantic search results

**Example:**
```python
def get_relevant_context(workspace_name, query, max_tokens):
    results = search(workspace_name, query, limit=50)

    # Check if top result is a strong document name match
    top = results[0]
    if top['filename_match_score'] > 0.8:
        # Return full document instead of chunks
        return read_full_document(top['metadata']['source_file'])

    # Otherwise, normal chunk assembly
    ...
```

---

## Option 3: Improved Keyword Matching

**Concept:** Smarter text normalization and fuzzy matching.

**How it would work:**
- Handle contractions: "what's" → "what is"
- Fuzzy match: biography ≈ bio ≈ biographical
- Stem words: running → run
- Match on YAML frontmatter fields (title, description, categories)

**Pros:**
- Improves all queries, not just targeted ones
- No behavioral change, just better matching

**Cons:**
- Complexity in normalization
- May over-match (false positives)
- Still chunk-based, not document-based

**Example:**
```python
def normalize_query(query):
    # Expand contractions
    query = query.replace("what's", "what is")
    query = query.replace("where's", "where is")

    # Could add stemming, synonyms, etc.
    return query

def fuzzy_match_score(query_term, filename_term):
    # Levenshtein distance or similar
    ...
```

---

## Option 4: Two-Phase Retrieval

**Concept:** First identify relevant documents, then return their complete content.

**How it would work:**
1. **Phase 1 - Document identification**: Search to find which documents are relevant (not chunks)
2. **Phase 2 - Content assembly**: For top N documents, include their full content

**Pros:**
- Documents stay coherent (no fragmentation)
- Can include multiple complete files
- Matches how Claude Desktop works

**Cons:**
- More complex implementation
- May need document-level embeddings (not chunk-level)
- Token budget management more complex

**Example:**
```python
def get_relevant_context(workspace_name, query, max_tokens):
    # Phase 1: Find relevant documents
    doc_scores = search_documents(workspace_name, query)  # Document-level

    # Phase 2: Assemble complete documents
    context_parts = []
    tokens_used = 0

    for doc in doc_scores[:5]:
        doc_content = read_full_document(doc['path'])
        doc_tokens = count_tokens(doc_content)

        if tokens_used + doc_tokens <= max_tokens:
            context_parts.append(doc_content)
            tokens_used += doc_tokens
        else:
            break

    return '\n---\n'.join(context_parts)
```

---

## Option 5: Increase Context Budget

**Concept:** Use more of the available context window.

**How it would work:**
- Current: 2000 token RAG budget
- Proposed: 8000-16000 tokens for RAG
- Models have 200K+ context, we're using <1%

**Pros:**
- Simple change (just a number)
- More content = better answers
- Closer to Claude Desktop experience

**Cons:**
- More tokens = higher cost per query
- May include irrelevant content
- Doesn't solve relevance ordering

**Implementation:**
```python
# In core.py
rag_max_tokens: int = 8000  # Up from 2000
```

**Cost analysis:**
- At 2000 tokens RAG: ~$0.006 per query (Claude Sonnet input)
- At 8000 tokens RAG: ~$0.024 per query
- Still very cheap for most use cases

---

## Option 6: Hybrid Approach (Recommended Direction?)

**Concept:** Combine multiple approaches based on query type.

**How it would work:**
1. **Query classification**: Is this asking for a specific document or general info?
2. **If document request**: Use full document retrieval (Option 2)
3. **If general query**: Use improved search with larger context (Options 3 + 5)
4. **Always**: Better keyword matching and normalization

**Pros:**
- Best of all approaches
- Adapts to query intent
- Can be implemented incrementally

**Cons:**
- Most complex to implement
- Query classification could be wrong
- More code paths to test

---

## Evaluation Criteria

| Approach | Complexity | Impact | Incremental? |
|----------|------------|--------|--------------|
| 1. Query understanding | Low | Medium | Yes |
| 2. Full document mode | Medium | High | Yes |
| 3. Better keyword matching | Low | Medium | Yes |
| 4. Two-phase retrieval | High | High | No |
| 5. Increase context | Very Low | Medium | Yes |
| 6. Hybrid | High | High | Yes |

## Test Queries

Any solution should improve these queries:

| Query | Expected Result |
|-------|-----------------|
| "what's in my biography" | Full biography content |
| "show me my biography" | Full biography content |
| "use the author-bios runbook" | Complete author-bios.md |
| "what runbooks do I have" | List of runbook names |
| "how do I write a blog post" | Blog writing runbook content |
| "tell me about my family" | personal-family.md content |

## Questions to Discuss

1. Should we prioritize **document retrieval** (Option 2) or **better search** (Options 3+5)?
2. Is the added complexity of query classification (Option 1/6) worth it?
3. What's an acceptable RAG context budget? 2K? 8K? 16K?
4. Should we index at document level in addition to chunk level?
