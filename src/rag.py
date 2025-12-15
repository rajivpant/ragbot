# rag.py
# RAG (Retrieval-Augmented Generation) support for Ragbot
# Uses Qdrant for vector storage and sentence-transformers for embeddings
# Uses shared chunking library for consistent text chunking
#
# Author: Rajiv Pant

import os
import logging
from typing import Optional
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

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


def search(workspace_name: str, query: str, limit: int = 5,
           content_type: Optional[str] = None) -> list:
    """
    Search for relevant content using semantic similarity.

    Args:
        workspace_name: Name of the workspace to search
        query: Search query
        limit: Maximum number of results
        content_type: Filter by content type ('datasets', 'runbooks', or None for all)

    Returns:
        List of search results with text and metadata
    """
    client = _get_qdrant_client()
    model = _get_embedding_model()

    if not client or not model:
        return []

    collection_name = get_collection_name(workspace_name)

    try:
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if collection_name not in collection_names:
            logger.warning(f"Collection {collection_name} not found")
            return []

        # Generate query embedding
        query_vector = model.encode(query).tolist()

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
        query_terms = set(query.lower().split())
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
                # Significant boost for filename matches
                item['score'] += 0.3 * len(matching_filename_terms)
            if matching_title_terms:
                # Moderate boost for title matches
                item['score'] += 0.2 * len(matching_title_terms)

        # Re-sort by boosted score
        formatted.sort(key=lambda x: x['score'], reverse=True)

        return formatted
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


def get_relevant_context(workspace_name: str, query: str,
                         max_tokens: int = 2000) -> str:
    """
    Get relevant context for a query, formatted for LLM consumption.

    This is the main entry point for RAG-augmented prompts.

    Args:
        workspace_name: Name of the workspace
        query: User's query
        max_tokens: Maximum tokens for retrieved context

    Returns:
        Formatted context string to include in the prompt
    """
    # Fetch more results than needed to allow re-ranking to surface keyword matches
    # Using 50 ensures we capture documents where filename matches query terms
    # even if semantic similarity is low
    results = search(workspace_name, query, limit=50)

    if not results:
        return ""

    # Build context string within token budget
    context_parts = []
    current_tokens = 0

    for result in results:
        text = result['text']
        # Rough token estimate
        text_tokens = len(text) // 4

        if current_tokens + text_tokens > max_tokens:
            break

        source = result['metadata'].get('filename', 'unknown')
        content_type = result['metadata'].get('content_type', 'content')
        score = result['score']

        context_parts.append(f"[{content_type}: {source} (relevance: {score:.2f})]\n{text}\n")
        current_tokens += text_tokens

    if not context_parts:
        return ""

    return "<retrieved_context>\n" + "\n---\n".join(context_parts) + "</retrieved_context>"


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
