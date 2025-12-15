# RAG Relevance Improvements

**Status:** Phase 3 Complete, Phase 4 Pending
**Created:** 2025-12-15
**Last Updated:** 2025-12-15

## Overview

Improve RAG search relevance so queries reliably find and return complete content from datasets and runbooks, matching the quality of Claude Desktop with full knowledge folder access.

## Problem Statement

Current RAG has limitations compared to Claude Desktop with full compiled knowledge:

1. **Vague queries fail**: "what's in my biography" returns fragmented results from multiple files, while "show me my biography" works well
2. **Chunk fragmentation**: RAG returns 2000 tokens of chunks from various files, not complete documents
3. **Runbook retrieval**: Users can't reliably retrieve full runbooks by name or description
4. **Semantic-only search**: MiniLM embeddings don't understand document identity, only content similarity

**Comparison:**
| Query | RAG (current) | Claude Desktop |
|-------|---------------|----------------|
| "what's in my biography" | Fragmented, partial | Complete, comprehensive |
| "show me my biography" | Good | Good |
| "use the author-bios runbook" | May find chunks | Has full file |

## Documents

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | **Comprehensive 6-stage architecture** based on industry research |
| [approaches.md](approaches.md) | Industry research + brainstormed approaches |
| [implementation-phase1.md](implementation-phase1.md) | **Phase 1 implementation details** (completed) |
| [implementation-phase2.md](implementation-phase2.md) | **Phase 2 implementation details** (completed) |
| [implementation-phase3.md](implementation-phase3.md) | **Phase 3 implementation details** (completed) |

## Research Summary

Extensive research on how Perplexity, ChatGPT, Claude, and other leading systems handle RAG reveals a consistent pattern:

**Key Finding**: Leading AI systems use **multi-stage pipelines** with distinct responsibilities, not simple "embed query → search → answer":

1. **Planner** (fast model) - Analyze intent, create execution plan
2. **Query Transformer** - Multi-query expansion, HyDE, contraction handling
3. **Hybrid Retrieval** - Semantic + keyword search combined
4. **Reranker** - Filter noise, surface truly relevant content
5. **Context Assembler** - Build structured context (full docs when appropriate)
6. **Generator** (best model) - Synthesize answer with citations
7. **Verifier** (optional) - Catch hallucinations, ensure quality

**Proven Impact** (from Anthropic/Microsoft benchmarks):
- Contextual embeddings: **35% fewer retrieval failures**
- Hybrid search + reranking: **67% fewer retrieval failures**
- Query rewriting (10 variations): **+21 NDCG points**

See [architecture.md](architecture.md) for the complete design.

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Problem Analysis | ✅ Complete | Identified root causes |
| Industry Research | ✅ Complete | Perplexity, ChatGPT, Claude, Gemini patterns documented |
| Architecture Design | ✅ Complete | 6-stage pipeline with prompt templates |
| **Phase 1 Implementation** | ✅ **Complete** | Foundation improvements (16K context, full doc, contractions) |
| Phase 1 Testing | ✅ Complete | 22 new tests, all passing |
| **Phase 2 Implementation** | ✅ **Complete** | Query intelligence (Planner, HyDE, multi-query) |
| Phase 2 Testing | ✅ Complete | 32 new tests, all passing |
| **Phase 3 Implementation** | ✅ **Complete** | Advanced retrieval (BM25, RRF, reranking) |
| Phase 3 Testing | ✅ Complete | 32 new tests, all passing (180 total) |
| Phase 4 Implementation | Pending | Verification (CRAG, confidence scoring) |

## Quick Links

- **Source Code:** `ragbot/src/rag.py`
- **Related:** [RAG Portability Fix](../../completed/rag-portability-fix/) (prerequisite work)

## Context

### What Works Now

After the RAG portability fix:
- Semantic search with keyword re-ranking
- Filename/title included in embeddings
- 50 results fetched, top ones by boosted score used
- ~2000 token context budget

### The Gap

Claude Desktop with full knowledge folder:
- Has ALL content in context (~40K+ tokens for rajiv workspace)
- Can answer any query about any document
- No retrieval step - everything is "retrieved"

RAG must be selective - but current selection isn't smart enough.

## Implementation Phases

### Phase 1: Foundation ✅ COMPLETE (2025-12-15)
- [x] Increase context budget from 2K to 16K tokens
- [x] Implement full document mode for "show me X" queries
- [x] Add contraction expansion ("what's" → "what is")
- [x] Strengthen filename/title matching
- [x] Write 22 unit tests
- [x] Update all default locations (backend + API + frontend)
- [x] Production tested and verified

See [implementation-phase1.md](implementation-phase1.md) for details.

### Phase 2: Query Intelligence ✅ COMPLETE (2025-12-15)
- [x] Add Planner stage using provider's fast model (category-based, not hardcoded)
- [x] Implement multi-query expansion (5-7 variations)
- [x] Add HyDE (Hypothetical Document Embeddings)
- [x] Provider-agnostic model selection via engines.yaml categories
- [x] Graceful fallback to Phase 1 heuristics when LLM unavailable
- [x] Write 32 unit tests

See [implementation-phase2.md](implementation-phase2.md) for details.

### Phase 3: Advanced Retrieval ✅ COMPLETE (2025-12-15)
- [x] Implement BM25/keyword search alongside vector search
- [x] Add Reciprocal Rank Fusion (RRF) for result merging
- [x] Implement LLM-based reranking with provider's fast model
- [x] Hybrid search function combining vector + BM25 + RRF
- [x] Write 32 unit tests

See [implementation-phase3.md](implementation-phase3.md) for details.

### Phase 4: Verification & Polish (Next)
- [ ] Add Verifier/Critic pass for hallucination detection
- [ ] Implement CRAG (Corrective RAG) loop
- [ ] Add confidence scoring to responses

## Research Foundation

Based on combined research from:
- My web search on Anthropic, OpenAI, Perplexity documentation
- ChatGPT's analysis of Perplexity/Claude/ChatGPT internals
- Claude's analysis with Microsoft Azure benchmarks
- Gemini's "Ragbot Pro" architecture proposal
- Perplexity's meta-analysis of RAG best practices
- Grok's synthesis of leading chatbot patterns

**Consensus**: All sources agree on the multi-stage pipeline approach. The architecture in [architecture.md](architecture.md) represents the best practices from all research combined.

**Next Step**: Test Phase 3 in production, then implement Phase 4.
