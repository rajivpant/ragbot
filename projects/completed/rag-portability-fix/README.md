# RAG Portability Fix

**Status:** Complete
**Created:** 2025-12-15
**Completed:** 2025-12-15

## Overview

Fixed critical RAG bugs that prevented retrieval from working in Docker and improved search relevance through hybrid semantic + keyword ranking.

## Problem Statement

Multiple issues prevented RAG from functioning correctly:

1. **Docker portability**: Chunks were indexed with host machine file paths. When running in Docker, the container couldn't access those paths, resulting in "[Content not available]" for all retrieved content.

2. **API compatibility**: qdrant-client 1.16.2 renamed `search()` to `query_points()`, causing "AttributeError: 'QdrantClient' object has no attribute 'search'".

3. **Poor relevance**: Semantic search alone didn't prioritize documents whose filenames matched the query. "Show me my biography" would return "author-bios.md" before "rajiv-pant-biography.md".

## Solution

### 1. Text Storage in Payload

Store chunk text directly in the Qdrant payload during indexing:

```python
# Before
payload = chunk.metadata

# After
payload = {**chunk.metadata, 'text': chunk.text}
```

Retrieval now reads from payload first, with file-based fallback for backwards compatibility.

### 2. Updated qdrant-client API

```python
# Before (deprecated)
results = client.search(collection_name, query_vector, limit)

# After (qdrant-client >= 1.10)
results = client.query_points(collection_name, query=query_vector, limit=limit)
```

### 3. Hybrid Search with Re-ranking

**During indexing** - Include filename/title in embedding text:
```python
embedding_parts = []
if filename:
    readable_filename = filename.rsplit('.', 1)[0].replace('-', ' ')
    embedding_parts.append(f"Document: {readable_filename}")
if title:
    embedding_parts.append(f"Title: {title}")
embedding_parts.append(chunk.text)

embedding_text = '\n'.join(embedding_parts)
embedding = model.encode(embedding_text)
```

**During search** - Keyword boost on results:
```python
for item in results:
    filename_words = set(filename.replace('-', ' ').split())
    matching = query_terms & filename_words
    item['score'] += 0.3 * len(matching)  # Boost for filename match
    item['score'] += 0.2 * len(title_matches)  # Boost for title match

results.sort(key=lambda x: x['score'], reverse=True)
```

**Increased search pool**: Fetch 50 results before re-ranking to ensure documents with low semantic scores but high keyword relevance can surface.

## Files Modified

| File | Changes |
|------|---------|
| `src/rag.py` | Text storage, query_points API, hybrid re-ranking |
| `src/ragbot/core.py` | GPT-5 max_completion_tokens fix, exception handling |
| `src/ragbot/models.py` | Renamed document_count to chunk_count |
| `src/api/routers/workspaces.py` | chunk_count field |
| `web/src/lib/api.ts` | TypeScript interface update |
| `web/src/components/SettingsPanel.tsx` | UI display of chunk_count |
| `tests/test_models_integration.py` | Use model's default_max_tokens |

## Commits

| Commit | Description |
|--------|-------------|
| ef10c67 | Fix RAG portability: store text in Qdrant payload |
| e558792 | Improve RAG search relevance with hybrid ranking |

## Testing

After fixes:
- "show me my biography" correctly returns biography file at top positions
- All 8 workspaces re-indexed with text stored in payloads
- Docker container correctly retrieves content without file access

## Related

- **New Project:** [rag-relevance-improvements](../../active/rag-relevance-improvements/) - Continued work on search quality
