"""
Vector Store Generator for AI Knowledge Compiler

Chunks content for RAG systems and optionally generates embeddings.

Library API:
- chunk_content(content, chunk_size, overlap) -> list
- generate_chunks_for_rag(assembled, config) -> list
- save_chunks(chunks, output_path)
"""

import os
import json
import hashlib
from typing import Optional
from pathlib import Path


def chunk_content(content: str, chunk_size: int = 1000,
                  chunk_overlap: int = 200, tokenizer: str = 'cl100k_base') -> list:
    """
    Split content into overlapping chunks.

    Uses character-based chunking with approximate token estimates.
    This is simpler and faster than token-based chunking.

    Args:
        content: Text content to chunk
        chunk_size: Target size of each chunk in tokens (converted to ~4 chars/token)
        chunk_overlap: Number of tokens to overlap between chunks
        tokenizer: Tokenizer name (currently unused, kept for API compatibility)

    Returns:
        List of chunk dictionaries with 'text', 'start_char', 'end_char', 'tokens'
    """
    # Use character-based chunking (approx 4 chars per token)
    char_chunk_size = chunk_size * 4
    char_overlap = chunk_overlap * 4

    return _chunk_by_chars(content, char_chunk_size, char_overlap)


def _chunk_by_chars(content: str, chunk_size: int, chunk_overlap: int) -> list:
    """
    Character-based chunking with overlap.

    Args:
        content: Text content
        chunk_size: Size in characters
        chunk_overlap: Overlap in characters

    Returns:
        List of chunk dictionaries
    """
    if not content:
        return []

    chunks = []
    start = 0

    while start < len(content):
        end = min(start + chunk_size, len(content))
        chunk_text = content[start:end]

        chunks.append({
            'text': chunk_text,
            'start_char': start,
            'end_char': end,
            'tokens': len(chunk_text) // 4  # Rough estimate
        })

        # If we've reached the end, we're done
        if end >= len(content):
            break

        # Move to next chunk with overlap
        start = end - chunk_overlap

    return chunks


def chunk_file(file_info: dict, chunk_size: int = 1000,
               chunk_overlap: int = 200) -> list:
    """
    Chunk a file and add metadata.

    Args:
        file_info: File info dict with 'content', 'relative_path', 'category'
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunks with metadata
    """
    content = file_info.get('content', '')
    rel_path = file_info.get('relative_path', '')
    category = file_info.get('category', 'other')

    raw_chunks = chunk_content(content, chunk_size, chunk_overlap)

    chunks = []
    for i, chunk in enumerate(raw_chunks):
        # Generate a unique ID for the chunk
        chunk_id = hashlib.md5(
            f"{rel_path}:{i}:{chunk['start_char']}".encode()
        ).hexdigest()[:12]

        chunks.append({
            'id': chunk_id,
            'text': chunk['text'],
            'tokens': chunk['tokens'],
            'metadata': {
                'source_file': rel_path,
                'category': category,
                'chunk_index': i,
                'total_chunks': len(raw_chunks),
                'start_char': chunk['start_char'],
                'end_char': chunk['end_char']
            }
        })

    return chunks


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
