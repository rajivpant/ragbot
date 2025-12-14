# rag.py
# RAG (Retrieval-Augmented Generation) support for Ragbot
# Uses Qdrant for vector storage and sentence-transformers for embeddings
#
# Author: Rajiv Pant

import os
import json
import hashlib
import logging
from typing import Optional
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

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
    client = _get_qdrant_client()
    model = _get_embedding_model()

    if not client or not model:
        return {'error': 'RAG not available', 'indexed': 0}

    collection_name = get_collection_name(workspace_name)

    # Ensure collection exists
    if not init_collection(workspace_name, model.get_sentence_embedding_dimension()):
        return {'error': 'Failed to initialize collection', 'indexed': 0}

    from qdrant_client.models import PointStruct

    points = []
    total_chunks = 0

    for path in content_paths:
        if os.path.isfile(path):
            chunks = _chunk_file(path, content_type)
            for chunk in chunks:
                embedding = model.encode(chunk['text']).tolist()
                point_id = _generate_point_id(chunk)
                points.append(PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=chunk['metadata']
                ))
            total_chunks += len(chunks)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for filename in files:
                    if filename.endswith(('.md', '.txt', '.yaml', '.yml')):
                        file_path = os.path.join(root, filename)
                        chunks = _chunk_file(file_path, content_type)
                        for chunk in chunks:
                            embedding = model.encode(chunk['text']).tolist()
                            point_id = _generate_point_id(chunk)
                            points.append(PointStruct(
                                id=point_id,
                                vector=embedding,
                                payload=chunk['metadata']
                            ))
                        total_chunks += len(chunks)

    # Upsert points in batches
    if points:
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(collection_name=collection_name, points=batch)

    return {
        'collection': collection_name,
        'indexed': total_chunks,
        'content_type': content_type
    }


def _chunk_file(file_path: str, content_type: str,
                chunk_size: int = 500, chunk_overlap: int = 50) -> list:
    """
    Read and chunk a file for indexing.

    Args:
        file_path: Path to the file
        content_type: Type of content ('datasets', 'runbooks')
        chunk_size: Target chunk size in tokens (~4 chars/token)
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunk dictionaries with text and metadata
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return []

    if not content.strip():
        return []

    # Character-based chunking (approx 4 chars per token)
    char_chunk_size = chunk_size * 4
    char_overlap = chunk_overlap * 4

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(content):
        end = min(start + char_chunk_size, len(content))
        chunk_text = content[start:end]

        # Extract title from first line if it's a markdown header
        title = None
        lines = chunk_text.split('\n')
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip()

        chunks.append({
            'text': chunk_text,
            'metadata': {
                'source_file': file_path,
                'filename': os.path.basename(file_path),
                'content_type': content_type,
                'chunk_index': chunk_index,
                'title': title,
                'char_start': start,
                'char_end': end
            }
        })

        if end >= len(content):
            break

        start = end - char_overlap
        chunk_index += 1

    return chunks


def _generate_point_id(chunk: dict) -> int:
    """Generate a unique integer ID for a chunk."""
    # Create a hash from file path and chunk index
    key = f"{chunk['metadata']['source_file']}:{chunk['metadata']['chunk_index']}"
    hash_bytes = hashlib.md5(key.encode()).digest()
    # Convert first 8 bytes to int (Qdrant requires int IDs)
    return int.from_bytes(hash_bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF


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

        # Search
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter
        )

        # Format results
        formatted = []
        for result in results:
            # Read the chunk text from the file
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
    results = search(workspace_name, query, limit=10)

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
