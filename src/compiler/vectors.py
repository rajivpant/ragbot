"""
Vector Store Generator for AI Knowledge Compiler

Chunks content for RAG systems and optionally generates embeddings.
Uses the shared chunking library for consistent chunking behavior.

Library API:
- chunk_content(content, chunk_size, overlap) -> list (deprecated, use chunking library)
- generate_chunks_for_rag(assembled, config) -> list
- save_chunks(chunks, output_path)
"""

import os
import json
from typing import Optional
from pathlib import Path

# Import from shared chunking library
# Use try/except to handle both package import (from src/) and direct import scenarios
try:
    from chunking import chunk_text, chunk_for_compiler, ChunkConfig, Chunk
except ImportError:
    from ..chunking import chunk_text, chunk_for_compiler, ChunkConfig, Chunk


def chunk_content(content: str, chunk_size: int = 1000,
                  chunk_overlap: int = 200, tokenizer: str = 'cl100k_base') -> list:
    """
    Split content into overlapping chunks.

    DEPRECATED: Use chunking.chunk_text() directly for new code.

    This function is kept for backward compatibility with existing callers.

    Args:
        content: Text content to chunk
        chunk_size: Target size of each chunk in tokens
        chunk_overlap: Number of tokens to overlap between chunks
        tokenizer: Tokenizer name (unused, kept for API compatibility)

    Returns:
        List of chunk dictionaries with 'text', 'start_char', 'end_char', 'tokens'
    """
    config = ChunkConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        extract_title=False
    )
    return chunk_text(content, config)


def chunk_file(file_info: dict, chunk_size: int = 1000,
               chunk_overlap: int = 200) -> list:
    """
    Chunk a file and add metadata.

    Args:
        file_info: File info dict with 'content', 'relative_path', 'category'
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunks with metadata (as dictionaries for JSON serialization)
    """
    content = file_info.get('content', '')
    rel_path = file_info.get('relative_path', '')
    category = file_info.get('category', 'other')

    chunks = chunk_for_compiler(
        content=content,
        source_path=rel_path,
        category=category,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    # Convert Chunk objects to dictionaries for backward compatibility
    return [chunk.to_dict() for chunk in chunks]


def generate_chunks_for_rag(assembled: dict, config: dict = None) -> list:
    """
    Generate RAG-ready chunks from assembled content.

    Args:
        assembled: Assembled content dict from assembler
        config: Vector store config (chunk_size, chunk_overlap)

    Returns:
        List of all chunks with metadata
    """
    if config is None:
        config = {}

    chunk_size = config.get('chunk_size', 1000)
    chunk_overlap = config.get('chunk_overlap', 200)

    # Only chunk datasets and (optionally) runbooks
    # Instructions should not go in vector stores
    categories_to_chunk = ['datasets', 'runbooks']

    all_chunks = []

    for file_info in assembled.get('files', []):
        category = file_info.get('category', 'other')

        if category not in categories_to_chunk:
            continue

        file_chunks = chunk_file(file_info, chunk_size, chunk_overlap)
        all_chunks.extend(file_chunks)

    return all_chunks


def save_chunks(chunks: list, output_dir: str) -> dict:
    """
    Save chunks to disk for RAG ingestion.

    Args:
        chunks: List of chunk dictionaries
        output_dir: Directory to save chunks

    Returns:
        Dictionary with output file paths and stats
    """
    os.makedirs(output_dir, exist_ok=True)

    # Save individual chunks as markdown files
    chunks_dir = os.path.join(output_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    chunk_files = []
    for chunk in chunks:
        chunk_id = chunk['id']
        chunk_path = os.path.join(chunks_dir, f'{chunk_id}.md')

        with open(chunk_path, 'w') as f:
            f.write(chunk['text'])

        chunk_files.append(chunk_path)

    # Save metadata
    metadata_path = os.path.join(output_dir, 'chunks-metadata.json')
    metadata = [{
        'id': c['id'],
        'tokens': c['tokens'],
        **c['metadata']
    } for c in chunks]

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    # Save as single JSONL file (common format for RAG ingestion)
    jsonl_path = os.path.join(output_dir, 'chunks.jsonl')
    with open(jsonl_path, 'w') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + '\n')

    return {
        'chunks_dir': chunks_dir,
        'metadata_path': metadata_path,
        'jsonl_path': jsonl_path,
        'total_chunks': len(chunks),
        'total_tokens': sum(c['tokens'] for c in chunks)
    }


def load_chunks(jsonl_path: str) -> list:
    """
    Load chunks from a JSONL file.

    Args:
        jsonl_path: Path to chunks.jsonl

    Returns:
        List of chunk dictionaries
    """
    chunks = []
    with open(jsonl_path, 'r') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks
