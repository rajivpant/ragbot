# Ragbot RAG Architecture: Quality-First Design

## Executive Summary

This document synthesizes research from OpenAI, Anthropic, Perplexity, Gemini, and industry best practices to define a **quality-first RAG architecture** for Ragbot. Cost and latency are secondary to response quality.

**Key Insight**: Leading AI systems treat every query as a "mission to be solved, not a string to be matched." They use multi-stage pipelines with distinct responsibilities: **Plan → Transform → Retrieve → Rerank → Synthesize → Verify**.

---

## Research Synthesis: What the Giants Actually Do

### Perplexity (Most Transparent, Closest to Our Goal)

| Stage | What They Do |
|-------|--------------|
| **Query Understanding** | "Tens of LLMs (ranging from big to small) work in parallel" - separate models for intent detection, query classification |
| **Query Decomposition** | Break "Compare MacBook M4 vs X1 Carbon for ML dev" into multiple focused search queries |
| **Hybrid Retrieval** | Dense (semantic) + Sparse (BM25) with Vespa, fetches dozens of candidates |
| **Reranking** | Cross-encoder or ML-based reranking to surface best results |
| **Grounding Policy** | "Don't say anything you didn't retrieve" - strict citation requirements |

**Source**: [Latenode](https://latenode.com/blog/ai-technology-language-models/ai-in-business-applications/what-is-perplexity-ai-best-ways-to-use-it-how-it-works), [Vespa Case Study](https://vespa.ai/perplexity/)

### Anthropic Claude

| Feature | What They Do |
|---------|--------------|
| **Tool Search Tool** | Don't dump all tools into prompt; use a search tool to discover relevant tools on demand |
| **Programmatic Orchestration** | Let Claude write code to call tools, filter/aggregate results, pass only distilled summaries to context |
| **Contextual Retrieval** | Prepend 50-100 tokens of context to each chunk before embedding = **35% fewer retrieval failures** |
| **Hybrid + Reranking** | Semantic + BM25 + reranker = **67% fewer retrieval failures** |

**Source**: [Anthropic Engineering](https://www.anthropic.com/engineering/contextual-retrieval), [Claude Docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)

### OpenAI / ChatGPT

| Feature | What They Do |
|---------|--------------|
| **Query Rewriting** | "Rewrites user queries to optimize them for search, breaks down complex user queries into multiple searches it can run in parallel" |
| **Hybrid Search** | Tunable `embedding_weight` and `text_weight` parameters |
| **Iterative Refinement** | Often performs 2-3 searches silently, refining terms before answering |
| **Unified Model** | Single strong model with tools, but internally orchestrates multiple retrieval passes |

**Source**: [OpenAI Docs](https://platform.openai.com/docs/guides/tools-file-search)

### Microsoft Azure AI Search (Concrete Benchmarks)

| Component | Performance | Improvement |
|-----------|-------------|-------------|
| Query Rewriting (10 variations) | 147ms for 32-token query | — |
| Semantic Reranking (50 docs) | 158ms | — |
| Combined QR + SR | ~305ms total | **+21 NDCG@3 points** (range +12 to +28) |

**Source**: Microsoft Azure AI Search November 2024 benchmarks

---

## The Six-Stage Architecture

Based on all research, the optimal quality-first architecture has **six distinct stages**, each with a specific responsibility:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            USER QUERY                                    │
│                   "what's in my biography"                               │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 1: PLANNER (Haiku/Flash - Fast Model)                            │
│                                                                          │
│  Purpose: Understand intent, create execution plan                       │
│                                                                          │
│  Outputs:                                                                │
│  • query_type: "document_lookup" | "factual_qa" | "multi_step_reasoning" │
│  • retrieval_plan: ["search biography file", "search personal datasets"] │
│  • tools_needed: ["vector_search", "full_document_fetch"]                │
│  • sub_queries: ["rajiv pant biography", "personal biographical info"]  │
│  • answer_style: "return_full_document" | "synthesize_from_chunks"       │
│                                                                          │
│  Latency: ~80-150ms                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 2: QUERY TRANSFORMER (Same Fast Model)                           │
│                                                                          │
│  Purpose: Optimize queries for retrieval (not generation)                │
│                                                                          │
│  Techniques:                                                             │
│  • Contraction expansion: "what's" → "what is"                           │
│  • Multi-query generation: 5-10 variations for better recall             │
│  • HyDE: Generate hypothetical answer, embed that for search             │
│  • Entity extraction: "biography" → filename pattern "biography"         │
│  • Abbreviation expansion: "IA deck" → "Intelligent Automation deck"     │
│                                                                          │
│  Latency: ~50-100ms                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 3: HYBRID RETRIEVAL                                              │
│                                                                          │
│  Purpose: Cast a wide net with multiple search strategies                │
│                                                                          │
│  For EACH transformed query:                                             │
│  • Vector search (semantic similarity via embeddings)                    │
│  • BM25/keyword search (exact term matching)                             │
│  • Metadata search (filename, title, category matching)                  │
│                                                                          │
│  Merge results using Reciprocal Rank Fusion (RRF)                        │
│  Return top 50-100 candidates                                            │
│                                                                          │
│  Latency: ~100-200ms                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 4: RERANKER (Haiku or Cross-Encoder Model)                       │
│                                                                          │
│  Purpose: Filter noise, surface truly relevant content                   │
│                                                                          │
│  • Score each (query, document) pair for relevance                       │
│  • Consider source authority/trust                                       │
│  • Filter chunks below quality threshold                                 │
│  • Return top 10-20 high-signal chunks                                   │
│                                                                          │
│  Option A: LLM-based (Haiku scores each chunk 0-10)                      │
│  Option B: Cross-encoder model (faster, dedicated reranker)              │
│                                                                          │
│  Latency: ~150-200ms                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 5: CONTEXT ASSEMBLER (Code, Not LLM)                             │
│                                                                          │
│  Purpose: Build optimal context for the generator                        │
│                                                                          │
│  • Group chunks by source document                                       │
│  • If top result is strong filename match → fetch FULL document          │
│  • Deduplicate overlapping content                                       │
│  • Order by relevance score                                              │
│  • Add metadata headers (source, confidence, type)                       │
│  • Compress if needed (summarize long sections)                          │
│                                                                          │
│  Output: Structured context object, not raw chunk dump                   │
│                                                                          │
│  Latency: ~10-50ms                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 6: GENERATOR (Opus/Sonnet/GPT-4 - Best Model)                    │
│                                                                          │
│  Purpose: Synthesize high-quality answer with citations                  │
│                                                                          │
│  Inputs:                                                                 │
│  • ORIGINAL user query (not rewritten - preserves intent)               │
│  • Structured context from Stage 5                                       │
│  • System prompt with grounding instructions                             │
│  • Planner's metadata (query type, answer style)                         │
│                                                                          │
│  Grounding Policy:                                                       │
│  "Only assert things supported by retrieved content.                     │
│   Cite sources explicitly. If unsure, say so."                           │
│                                                                          │
│  Latency: ~500-2000ms (varies by model)                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  STAGE 7 (OPTIONAL): VERIFIER (Haiku - Critic Pass)                     │
│                                                                          │
│  Purpose: Catch hallucinations, ensure quality                           │
│                                                                          │
│  • Compare answer against retrieved context                              │
│  • Flag claims without supporting evidence                               │
│  • Check for contradictions                                              │
│  • Suggest revisions if issues found                                     │
│                                                                          │
│  CRAG (Corrective RAG): If verifier scores answer as "poor",             │
│  trigger new search with refined queries                                 │
│                                                                          │
│  Latency: ~100-200ms                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Two Prompts Per Query (Retrieval vs Generation)

| Purpose | Prompt Type | Example |
|---------|-------------|---------|
| **Retrieval** | Short, explicit, search-optimized | "rajiv pant biography personal information document" |
| **Generation** | Original query + context + instructions | "what's in my biography" + structured context + system prompt |

**Why**: Rewrites are optimized for retrieval, not response. The generator should see what the user actually asked.

### 2. Full Document Mode (Critical for "Show Me X" Queries)

When the planner detects `query_type: "document_lookup"`:
1. Skip chunked retrieval
2. Find the document by filename/title match
3. Return the **entire document** (not chunks)
4. Up to 16K-32K tokens if needed

This solves the "show me my biography" problem perfectly.

### 3. HyDE (Hypothetical Document Embeddings)

For semantic queries where the question doesn't look like the answer:

```
User: "How do neural networks learn?"
↓
LLM generates hypothetical answer:
"Neural networks learn through backpropagation, adjusting weights..."
↓
Embed the HYPOTHETICAL ANSWER
↓
Search for documents similar to that answer
```

**Why**: Questions and answers have different vocabulary. HyDE bridges this semantic gap.

### 4. Multi-Query Expansion

Original: "What's in my biography?"

Expanded queries:
1. "rajiv pant biography"
2. "personal biographical information"
3. "biography document file"
4. "personal history background"
5. "about me personal details"

Each query retrieves candidates; results are merged with RRF.

### 5. Context Budget: 16K Tokens

Current: 2K tokens
Proposed: **16K tokens**

Rationale:
- Models have 200K+ context windows
- We're currently using <1%
- More context = better answers
- Matches Claude Desktop experience
- Cost is not a concern

---

## Prompt Templates

### Stage 1: Planner Prompt

```
You are a query planning assistant. Analyze the user's query and create an execution plan.

User query: "{query}"
Workspace: "{workspace_name}"
Available document types: datasets, runbooks, instructions

Respond with JSON:
{
  "query_type": "document_lookup" | "factual_qa" | "procedural" | "multi_step",
  "retrieval_strategy": "full_document" | "semantic_chunks" | "hybrid",
  "sub_queries": ["query1", "query2", ...],  // 3-7 search variations
  "filename_hints": ["biography", "..."],     // if looking for specific doc
  "answer_style": "return_content" | "synthesize" | "list_sources",
  "complexity": "simple" | "moderate" | "complex"
}
```

### Stage 2: Query Transformer Prompt

```
Rewrite this query for optimal search retrieval.

Original query: "{query}"
Query type: "{query_type}"

Generate 5-7 search query variations that:
1. Expand contractions ("what's" → "what is")
2. Add synonyms and related terms
3. Include likely document/file names
4. Vary phrasing for different matches
5. Extract key entities and concepts

Also generate a hypothetical answer (2-3 sentences) that a good document would contain.

Output JSON:
{
  "expanded_queries": ["query1", "query2", ...],
  "hypothetical_answer": "A good document would say...",
  "key_entities": ["entity1", "entity2"],
  "filename_patterns": ["pattern1", "pattern2"]
}
```

### Stage 6: Generator System Prompt

```
You are a helpful assistant with access to the user's personal knowledge base.

GROUNDING RULES:
1. Only make claims supported by the retrieved content below.
2. Cite sources explicitly: [Source: filename.md]
3. If the content doesn't contain the answer, say "I don't have information about that in your knowledge base."
4. Distinguish between facts from documents and your own reasoning.

RETRIEVED CONTENT:
{structured_context}

---

Now answer the user's question. If they asked to "show" or "display" a document, provide the full content. If they asked a question, synthesize an answer with citations.
```

---

## Implementation Phases

### Phase 1: Foundation (Immediate)
- [ ] Increase context budget to 16K tokens
- [ ] Implement full document mode for filename matches
- [ ] Add contraction expansion ("what's" → "what is")
- [ ] Store and use filename/title in search scoring

### Phase 2: Query Intelligence (Next)
- [ ] Add Planner stage (Haiku) for query analysis
- [ ] Implement multi-query expansion
- [ ] Add HyDE (hypothetical document embeddings)

### Phase 3: Advanced Retrieval (Then)
- [ ] Implement BM25/keyword search alongside vector search
- [ ] Add Reciprocal Rank Fusion for result merging
- [ ] Implement LLM-based reranking

### Phase 4: Verification (Future)
- [ ] Add Verifier/Critic pass
- [ ] Implement CRAG (Corrective RAG) loop
- [ ] Add confidence scoring to responses

---

## Performance Expectations

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| "Show me my biography" | Often fails | Always returns full doc | 100% |
| Retrieval precision | ~60% | ~90% | +30% |
| Hallucination rate | Unknown | <5% | Measurable |
| Total latency | ~800ms | ~1500ms | +700ms (acceptable) |

The added latency (~700ms) is a worthwhile trade for dramatically better response quality.

---

## References

- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [OpenAI: File Search](https://platform.openai.com/docs/guides/tools-file-search)
- [Perplexity: How It Works](https://latenode.com/blog/ai-technology-language-models/ai-in-business-applications/what-is-perplexity-ai-best-ways-to-use-it-how-it-works)
- [Vespa: Perplexity Case Study](https://vespa.ai/perplexity/)
- [IBM: Agentic RAG](https://www.ibm.com/think/topics/agentic-rag)
- [Microsoft Azure: RAG Benchmarks](https://cloud.google.com/blog/products/ai-machine-learning/optimizing-rag-retrieval)
- [HyDE Paper](https://arxiv.org/abs/2212.10496)
- [CRAG Paper](https://arxiv.org/abs/2401.15884)
