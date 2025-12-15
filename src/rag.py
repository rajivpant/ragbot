# rag.py
# RAG (Retrieval-Augmented Generation) support for Ragbot
# Uses Qdrant for vector storage and sentence-transformers for embeddings
# Uses shared chunking library for consistent text chunking
#
# Phase 1 Improvements (December 2025):
# - Increased context budget from 2K to 16K tokens
# - Full document retrieval for targeted queries
# - Query preprocessing (contraction expansion)
# - Enhanced filename/title matching
#
# Author: Rajiv Pant

import os
import re
import logging
from typing import Optional, Dict, List, Tuple
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Query Preprocessing (Phase 1 Improvements)
# =============================================================================

# Common contractions to expand for better keyword matching
CONTRACTIONS = {
    "what's": "what is",
    "where's": "where is",
    "who's": "who is",
    "how's": "how is",
    "that's": "that is",
    "there's": "there is",
    "here's": "here is",
    "it's": "it is",
    "let's": "let us",
    "can't": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "couldn't": "could not",
    "wouldn't": "would not",
    "shouldn't": "should not",
    "i'm": "i am",
    "you're": "you are",
    "we're": "we are",
    "they're": "they are",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "i'll": "i will",
    "you'll": "you will",
    "we'll": "we will",
    "they'll": "they will",
    "i'd": "i would",
    "you'd": "you would",
    "we'd": "we would",
    "they'd": "they would",
}

# Patterns that indicate a document lookup request (not semantic search)
DOCUMENT_LOOKUP_PATTERNS = [
    r"^show\s+(?:me\s+)?(?:my\s+|the\s+)?(.+)$",
    r"^display\s+(?:my\s+|the\s+)?(.+)$",
    r"^get\s+(?:me\s+)?(?:my\s+|the\s+)?(.+)$",
    r"^read\s+(?:my\s+|the\s+)?(.+)$",
    r"^open\s+(?:my\s+|the\s+)?(.+)$",
    r"^use\s+(?:the\s+)?(.+?)(?:\s+runbook)?$",
    r"^what(?:'s| is)\s+in\s+(?:my\s+|the\s+)?(.+)$",
    r"^what\s+does\s+(?:my\s+|the\s+)?(.+?)\s+(?:say|contain|have).*$",
]


def expand_contractions(query: str) -> str:
    """
    Expand contractions in a query for better keyword matching.

    Example: "what's in my biography" -> "what is in my biography"

    Args:
        query: Original user query

    Returns:
        Query with contractions expanded
    """
    result = query.lower()
    for contraction, expansion in CONTRACTIONS.items():
        # Use word boundaries to avoid partial matches
        result = re.sub(r'\b' + re.escape(contraction) + r'\b', expansion, result)
    return result


def detect_document_request(query: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if a query is asking for a specific document by name.

    Args:
        query: User's query

    Returns:
        Tuple of (is_document_request, document_hint)
        document_hint is the extracted document name/pattern if detected
    """
    query_lower = query.lower().strip()

    for pattern in DOCUMENT_LOOKUP_PATTERNS:
        match = re.match(pattern, query_lower, re.IGNORECASE)
        if match:
            # Extract the document hint from the match
            doc_hint = match.group(1).strip()
            # Remove common suffixes that aren't part of the name
            doc_hint = re.sub(r'\s*(file|document|doc|content|runbook)s?\s*$', '', doc_hint)
            if doc_hint:
                return True, doc_hint

    return False, None


def preprocess_query(query: str) -> Dict[str, any]:
    """
    Preprocess a query for optimal retrieval.

    This implements Phase 1 query preprocessing:
    1. Expand contractions for keyword matching
    2. Detect document lookup requests
    3. Extract key terms for filename matching

    Args:
        query: Original user query

    Returns:
        Dict with:
        - original_query: The unchanged input
        - processed_query: Query with contractions expanded
        - is_document_request: Whether this looks like a document lookup
        - document_hint: Extracted document name pattern (if applicable)
        - search_terms: Key terms for filename matching
    """
    expanded = expand_contractions(query)
    is_doc_request, doc_hint = detect_document_request(query)

    # Extract meaningful search terms (remove stop words)
    stop_words = {'a', 'an', 'the', 'my', 'your', 'is', 'are', 'was', 'were',
                  'in', 'on', 'at', 'to', 'for', 'of', 'with', 'me', 'show',
                  'tell', 'give', 'get', 'find', 'what', 'where', 'how', 'when',
                  'display', 'open', 'read', 'use', 'about', 'does', 'do'}
    words = re.findall(r'\b[a-z]+\b', expanded.lower())
    search_terms = [w for w in words if w not in stop_words and len(w) > 2]

    return {
        'original_query': query,
        'processed_query': expanded,
        'is_document_request': is_doc_request,
        'document_hint': doc_hint,
        'search_terms': search_terms,
    }

# Lazy import for chunking - handle both relative and absolute imports
_chunking_loaded = False
chunk_file = None
chunk_files = None
ChunkConfig = None
Chunk = None
get_qdrant_point_id = None


def _load_chunking():
    """Lazy load chunking module."""
    global _chunking_loaded, chunk_file, chunk_files, ChunkConfig, Chunk, get_qdrant_point_id
    if _chunking_loaded:
        return True
    try:
        # Try relative import (when used as part of a package)
        from .chunking import chunk_file as cf, chunk_files as cfs, ChunkConfig as CC, Chunk as C, get_qdrant_point_id as gpi
        chunk_file, chunk_files, ChunkConfig, Chunk, get_qdrant_point_id = cf, cfs, CC, C, gpi
        _chunking_loaded = True
        return True
    except ImportError:
        try:
            # Try absolute import (when used standalone)
            from chunking import chunk_file as cf, chunk_files as cfs, ChunkConfig as CC, Chunk as C, get_qdrant_point_id as gpi
            chunk_file, chunk_files, ChunkConfig, Chunk, get_qdrant_point_id = cf, cfs, CC, C, gpi
            _chunking_loaded = True
            return True
        except ImportError:
            logger.warning("chunking module not available. Some RAG features may be limited.")
            return False

# Lazy imports - only load heavy dependencies when needed
_qdrant_client = None
_embedding_model = None


def _get_qdrant_client():
    """Get or create Qdrant client (lazy initialization)."""
    global _qdrant_client
    if _qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            # Check for Qdrant server or use in-memory
            qdrant_url = os.environ.get('QDRANT_URL', None)
            qdrant_path = os.environ.get('QDRANT_PATH', '/app/qdrant_data')

            if qdrant_url:
                # Connect to Qdrant server
                logger.info(f"Connecting to Qdrant server at {qdrant_url}")
                _qdrant_client = QdrantClient(url=qdrant_url)
            else:
                # Use local file-based storage (persists across restarts)
                os.makedirs(qdrant_path, exist_ok=True)
                logger.info(f"Using local Qdrant storage at {qdrant_path}")
                _qdrant_client = QdrantClient(path=qdrant_path)
        except ImportError:
            logger.warning("qdrant-client not installed. RAG features disabled.")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            return None
    return _qdrant_client


def _get_embedding_model():
    """Get or create embedding model (lazy initialization)."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            # Use a small, fast model that works well for retrieval
            # all-MiniLM-L6-v2 is 80MB and produces 384-dim embeddings
            model_name = os.environ.get('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            logger.info(f"Loading embedding model: {model_name}")
            _embedding_model = SentenceTransformer(model_name)
        except ImportError:
            logger.warning("sentence-transformers not installed. RAG features disabled.")
            return None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return None
    return _embedding_model


def is_rag_available() -> bool:
    """Check if RAG dependencies are available."""
    try:
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer
        return True
    except ImportError:
        return False


def get_collection_name(workspace_name: str) -> str:
    """Generate a collection name for a workspace."""
    # Sanitize workspace name for Qdrant collection naming
    safe_name = workspace_name.lower().replace(' ', '_').replace('-', '_')
    return f"ragbot_{safe_name}"


def init_collection(workspace_name: str, vector_size: int = 384) -> bool:
    """
    Initialize a Qdrant collection for a workspace.

    Args:
        workspace_name: Name of the workspace
        vector_size: Dimension of embedding vectors (384 for MiniLM)

    Returns:
        True if collection is ready, False otherwise
    """
    client = _get_qdrant_client()
    if not client:
        return False

    try:
        from qdrant_client.models import Distance, VectorParams

        collection_name = get_collection_name(workspace_name)

        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            logger.info(f"Creating collection: {collection_name}")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
        return True
    except Exception as e:
        logger.error(f"Failed to initialize collection: {e}")
        return False


def index_content(workspace_name: str, content_paths: list, content_type: str = 'datasets') -> dict:
    """
    Index content into the vector store.

    Args:
        workspace_name: Name of the workspace
        content_paths: List of file/directory paths to index
        content_type: Type of content ('datasets', 'runbooks')

    Returns:
        Dictionary with indexing stats
    """
    # Load chunking module
    if not _load_chunking():
        return {'error': 'Chunking module not available', 'indexed': 0}

    client = _get_qdrant_client()
    model = _get_embedding_model()

    if not client or not model:
        return {'error': 'RAG not available', 'indexed': 0}

    collection_name = get_collection_name(workspace_name)

    # Ensure collection exists
    if not init_collection(workspace_name, model.get_sentence_embedding_dimension()):
        return {'error': 'Failed to initialize collection', 'indexed': 0}

    from qdrant_client.models import PointStruct

    # Configure chunking for RAG (smaller chunks, title extraction)
    config = ChunkConfig(
        chunk_size=500,
        chunk_overlap=50,
        extract_title=True,
        category=content_type
    )

    # Chunk all files
    chunks = chunk_files(content_paths, config)

    # Generate embeddings and create points
    points = []
    for chunk in chunks:
        # Build text for embedding that includes filename and title for better semantic matching
        # This helps queries like "show me my biography" match documents about biography
        filename = chunk.metadata.get('filename', '')
        title = chunk.metadata.get('title', '')

        # Create embedding text with document context
        embedding_parts = []
        if filename:
            # Convert filename to readable form: rajiv-pant-biography.md -> rajiv pant biography
            readable_filename = filename.rsplit('.', 1)[0].replace('-', ' ').replace('_', ' ')
            embedding_parts.append(f"Document: {readable_filename}")
        if title:
            embedding_parts.append(f"Title: {title}")
        embedding_parts.append(chunk.text)

        embedding_text = '\n'.join(embedding_parts)
        embedding = model.encode(embedding_text).tolist()

        point_id = get_qdrant_point_id(chunk)
        # Store original text in payload for retrieval (not the embedding text)
        payload = {**chunk.metadata, 'text': chunk.text}
        points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload=payload
        ))

    # Upsert points in batches
    if points:
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(collection_name=collection_name, points=batch)

    return {
        'collection': collection_name,
        'indexed': len(chunks),
        'content_type': content_type
    }


def find_full_document(workspace_name: str, document_hint: str,
                       search_terms: List[str]) -> Optional[Dict]:
    """
    Find and retrieve a complete document by name/hint.

    This is used when query preprocessing detects a document lookup request
    (e.g., "show me my biography"). Instead of returning chunks, we find
    the best matching document and return its full content.

    Args:
        workspace_name: Name of the workspace
        document_hint: Extracted document name hint (e.g., "biography")
        search_terms: Additional search terms from the query

    Returns:
        Dict with 'content', 'filename', 'source_file' if found, None otherwise
    """
    client = _get_qdrant_client()
    if not client:
        return None

    collection_name = get_collection_name(workspace_name)

    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if collection_name not in collection_names:
            return None

        # Get all unique source files from the collection
        # We scroll through to find documents matching the hint
        all_points = []
        offset = None
        while True:
            result = client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            points, next_offset = result
            all_points.extend(points)
            if next_offset is None:
                break
            offset = next_offset

        if not all_points:
            return None

        # Group chunks by source file and score each file
        file_chunks: Dict[str, List] = {}
        for point in all_points:
            source_file = point.payload.get('source_file', '')
            if source_file:
                if source_file not in file_chunks:
                    file_chunks[source_file] = []
                file_chunks[source_file].append(point.payload)

        # Score each file based on how well it matches the hint and terms
        file_scores = []
        hint_words = set(document_hint.lower().replace('-', ' ').replace('_', ' ').split())
        term_set = set(search_terms)

        for source_file, chunks in file_chunks.items():
            filename = chunks[0].get('filename', '') if chunks else ''
            title = chunks[0].get('title', '') if chunks else ''

            # Convert filename to word set
            filename_clean = filename.lower().rsplit('.', 1)[0] if filename else ''
            filename_words = set(filename_clean.replace('-', ' ').replace('_', ' ').split())

            # Convert title to word set
            title_words = set(title.lower().split()) if title else set()

            score = 0

            # Score based on hint matching
            hint_in_filename = hint_words & filename_words
            hint_in_title = hint_words & title_words
            if hint_in_filename:
                score += 10 * len(hint_in_filename)  # Strong boost for filename match
            if hint_in_title:
                score += 5 * len(hint_in_title)  # Good boost for title match

            # Score based on search terms
            terms_in_filename = term_set & filename_words
            terms_in_title = term_set & title_words
            if terms_in_filename:
                score += 3 * len(terms_in_filename)
            if terms_in_title:
                score += 2 * len(terms_in_title)

            # Check for substring match (e.g., "bio" in "biography")
            if document_hint.lower() in filename_clean:
                score += 15  # Strong boost for substring match

            if score > 0:
                file_scores.append((source_file, filename, score, chunks))

        if not file_scores:
            return None

        # Sort by score and get best match
        file_scores.sort(key=lambda x: x[2], reverse=True)
        best_source, best_filename, best_score, best_chunks = file_scores[0]

        logger.info(f"Full document match: {best_filename} (score: {best_score})")

        # Reconstruct full document from chunks
        # Sort chunks by char_start to maintain order
        sorted_chunks = sorted(best_chunks, key=lambda c: c.get('char_start', 0))

        # Merge chunks, removing overlapping content
        full_content = ""
        last_end = 0
        for chunk in sorted_chunks:
            chunk_start = chunk.get('char_start', 0)
            chunk_text = chunk.get('text', '')

            if chunk_start >= last_end:
                # No overlap, append full chunk
                full_content += chunk_text
            else:
                # Overlap - only add non-overlapping part
                overlap = last_end - chunk_start
                if overlap < len(chunk_text):
                    full_content += chunk_text[overlap:]

            last_end = chunk.get('char_end', chunk_start + len(chunk_text))

        return {
            'content': full_content.strip(),
            'filename': best_filename,
            'source_file': best_source,
            'score': best_score,
            'title': sorted_chunks[0].get('title', '') if sorted_chunks else '',
            'content_type': sorted_chunks[0].get('content_type', 'datasets') if sorted_chunks else 'datasets'
        }

    except Exception as e:
        logger.error(f"Full document retrieval failed: {e}")
        return None


def search(workspace_name: str, query: str, limit: int = 5,
           content_type: Optional[str] = None,
           use_preprocessing: bool = True) -> list:
    """
    Search for relevant content using semantic similarity.

    Args:
        workspace_name: Name of the workspace to search
        query: Search query
        limit: Maximum number of results
        content_type: Filter by content type ('datasets', 'runbooks', or None for all)
        use_preprocessing: If True, preprocess query (expand contractions, extract terms)

    Returns:
        List of search results with text and metadata
    """
    client = _get_qdrant_client()
    model = _get_embedding_model()

    if not client or not model:
        return []

    collection_name = get_collection_name(workspace_name)

    # Preprocess query for better matching
    if use_preprocessing:
        query_info = preprocess_query(query)
        search_query = query_info['processed_query']
        search_terms = query_info['search_terms']
    else:
        search_query = query
        search_terms = set(query.lower().split())

    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if collection_name not in collection_names:
            logger.warning(f"Collection {collection_name} not found")
            return []

        # Generate query embedding using preprocessed query
        query_vector = model.encode(search_query).tolist()

        # Build filter if content_type specified
        search_filter = None
        if content_type:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="content_type",
                        match=MatchValue(value=content_type)
                    )
                ]
            )

        # Search using query_points (qdrant-client >= 1.10)
        results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            query_filter=search_filter
        )

        # Format results
        formatted = []
        for result in results.points:
            # Get text directly from payload (stored during indexing)
            # Fall back to file reading for backwards compatibility
            text = result.payload.get('text', '')
            if not text:
                try:
                    source_file = result.payload.get('source_file', '')
                    char_start = result.payload.get('char_start', 0)
                    char_end = result.payload.get('char_end', 0)

                    with open(source_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        text = content[char_start:char_end]
                except:
                    text = "[Content not available]"

            formatted.append({
                'text': text,
                'score': result.score,
                'metadata': result.payload
            })

        # Re-rank: boost results where query terms appear in filename or title
        # This improves results for queries like "show me my biography" where
        # semantic search might not prioritize exact document name matches
        # Use preprocessed search_terms which have contractions expanded and stop words removed
        query_terms = set(search_terms) if isinstance(search_terms, list) else search_terms
        for item in formatted:
            filename = item['metadata'].get('filename', '').lower()
            title = item['metadata'].get('title', '').lower()

            # Check for exact term matches in filename
            filename_words = set(filename.replace('-', ' ').replace('_', ' ').replace('.md', '').split())
            title_words = set(title.split()) if title else set()

            # Boost score if query terms appear in filename or title
            matching_filename_terms = query_terms & filename_words
            matching_title_terms = query_terms & title_words

            if matching_filename_terms:
                # Significant boost for filename matches (increased from 0.3)
                item['score'] += 0.5 * len(matching_filename_terms)
            if matching_title_terms:
                # Good boost for title matches (increased from 0.2)
                item['score'] += 0.3 * len(matching_title_terms)

        # Re-sort by boosted score
        formatted.sort(key=lambda x: x['score'], reverse=True)

        return formatted
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def get_relevant_context(workspace_name: str, query: str,
                         max_tokens: int = 16000) -> str:
    """
    Get relevant context for a query, formatted for LLM consumption.

    This is the main entry point for RAG-augmented prompts.

    Phase 1 Improvements:
    - Increased default max_tokens from 2000 to 16000 (8x increase)
    - Full document retrieval for targeted queries ("show me my biography")
    - Query preprocessing with contraction expansion
    - Enhanced filename/title matching

    Args:
        workspace_name: Name of the workspace
        query: User's query
        max_tokens: Maximum tokens for retrieved context (default: 16000)

    Returns:
        Formatted context string to include in the prompt
    """
    # Step 1: Preprocess the query
    query_info = preprocess_query(query)

    # Step 2: For document lookup requests, try full document retrieval first
    if query_info['is_document_request'] and query_info['document_hint']:
        logger.info(f"Document request detected: '{query_info['document_hint']}'")

        full_doc = find_full_document(
            workspace_name,
            query_info['document_hint'],
            query_info['search_terms']
        )

        if full_doc:
            # Check if full document fits in budget
            doc_tokens = len(full_doc['content']) // 4
            if doc_tokens <= max_tokens:
                logger.info(f"Returning full document: {full_doc['filename']} ({doc_tokens} tokens)")
                content_type = full_doc.get('content_type', 'datasets')
                filename = full_doc.get('filename', 'unknown')
                title = full_doc.get('title', '')

                header = f"[{content_type}: {filename}]"
                if title:
                    header = f"[{content_type}: {filename} - {title}]"

                return f"<retrieved_context>\n{header}\n\n{full_doc['content']}\n</retrieved_context>"
            else:
                logger.info(f"Full document too large ({doc_tokens} tokens > {max_tokens}), using chunks")

    # Step 3: Fall back to semantic search with chunk retrieval
    # Fetch more results than needed to allow re-ranking to surface keyword matches
    # Using 100 ensures we capture documents where filename matches query terms
    # even if semantic similarity is low
    results = search(workspace_name, query, limit=100)

    if not results:
        return ""

    # Build context string within token budget
    context_parts = []
    current_tokens = 0
    seen_files = set()

    for result in results:
        text = result['text']
        # Rough token estimate
        text_tokens = len(text) // 4

        if current_tokens + text_tokens > max_tokens:
            break

        source = result['metadata'].get('filename', 'unknown')
        content_type = result['metadata'].get('content_type', 'content')
        score = result['score']
        title = result['metadata'].get('title', '')

        # Track which files we've included
        seen_files.add(source)

        header = f"[{content_type}: {source} (relevance: {score:.2f})]"
        if title and source not in title:
            header = f"[{content_type}: {source} - {title} (relevance: {score:.2f})]"

        context_parts.append(f"{header}\n{text}\n")
        current_tokens += text_tokens

    if not context_parts:
        return ""

    # Add summary of sources
    sources_note = f"<!-- Sources: {', '.join(sorted(seen_files)[:10])} -->\n"

    return "<retrieved_context>\n" + sources_note + "\n---\n".join(context_parts) + "</retrieved_context>"


def index_workspace(workspace_name: str, ai_knowledge_paths: dict) -> dict:
    """
    Index all content for a workspace from ai-knowledge paths.

    Args:
        workspace_name: Name of the workspace
        ai_knowledge_paths: Dict with 'instructions', 'datasets' paths

    Returns:
        Indexing stats
    """
    stats = {'workspace': workspace_name, 'datasets': 0, 'runbooks': 0}

    # Index datasets/knowledge
    datasets_path = ai_knowledge_paths.get('datasets')
    if datasets_path and os.path.exists(datasets_path):
        result = index_content(workspace_name, [datasets_path], 'datasets')
        stats['datasets'] = result.get('indexed', 0)

    # Note: We don't index instructions - they should always be in the system prompt
    # Runbooks could be indexed if they exist in a separate path

    return stats


def get_index_status(workspace_name: str) -> tuple[bool, int]:
    """
    Get the index status for a workspace.

    Args:
        workspace_name: Name of the workspace

    Returns:
        Tuple of (is_indexed, chunk_count) where chunk_count is the number of
        vector points in the Qdrant collection.
    """
    client = _get_qdrant_client()
    if not client:
        return False, 0

    try:
        collection_name = get_collection_name(workspace_name)

        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            return False, 0

        # Get collection info
        collection_info = client.get_collection(collection_name)
        doc_count = collection_info.points_count

        return doc_count > 0, doc_count
    except Exception as e:
        logger.error(f"Failed to get index status: {e}")
        return False, 0


def index_workspace_by_name(workspace_name: str, force: bool = False) -> int:
    """
    Index a workspace by name, automatically discovering its paths.

    This is a convenience wrapper that discovers workspace paths from
    the ai-knowledge repository structure.

    Args:
        workspace_name: Name/dir_name of the workspace
        force: If True, clear existing index first

    Returns:
        Number of documents indexed
    """
    # Import here to avoid circular imports
    import sys
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    try:
        from ragbot import get_workspace
        workspace = get_workspace(workspace_name)
    except Exception as e:
        logger.error(f"Failed to get workspace {workspace_name}: {e}")
        return 0

    if force:
        clear_collection(workspace_name)

    # Get datasets paths (may be a list or a single path)
    datasets = workspace.get('datasets', [])
    if isinstance(datasets, str):
        datasets = [datasets]

    # Filter to existing paths
    datasets = [p for p in datasets if p and os.path.exists(p)]

    if not datasets:
        logger.warning(f"No dataset paths found for workspace {workspace_name}")
        return 0

    # Index the content directly
    result = index_content(workspace_name, datasets, 'datasets')
    return result.get('indexed', 0)


def clear_collection(workspace_name: str) -> bool:
    """
    Clear all indexed content for a workspace.

    Args:
        workspace_name: Name of the workspace

    Returns:
        True if successful
    """
    client = _get_qdrant_client()
    if not client:
        return False

    try:
        collection_name = get_collection_name(workspace_name)
        client.delete_collection(collection_name)
        logger.info(f"Cleared collection: {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to clear collection: {e}")
        return False
