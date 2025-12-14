"""
Core Chunking Functions

Provides text chunking with consistent behavior for both compiler and RAG use cases.
"""

import os
import hashlib
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class ChunkConfig:
    """Configuration for chunking behavior."""

    # Chunk size in tokens (converted to chars using chars_per_token)
    chunk_size: int = 500

    # Overlap between chunks in tokens
    chunk_overlap: int = 50

    # Approximate characters per token (for character-based chunking)
    chars_per_token: int = 4

    # Whether to extract title from markdown headers
    extract_title: bool = True

    # Content category (for metadata)
    category: str = 'content'

    # File extensions to process when chunking directories
    file_extensions: tuple = ('.md', '.txt', '.yaml', '.yml')

    @property
    def char_chunk_size(self) -> int:
        """Chunk size in characters."""
        return self.chunk_size * self.chars_per_token

    @property
    def char_overlap(self) -> int:
        """Overlap in characters."""
        return self.chunk_overlap * self.chars_per_token


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    id: str
    text: str
    tokens: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'text': self.text,
            'tokens': self.tokens,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Chunk':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            text=data['text'],
            tokens=data['tokens'],
            metadata=data.get('metadata', {})
        )


def chunk_text(
    text: str,
    config: Optional[ChunkConfig] = None
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks.

    Uses character-based chunking with approximate token estimates.
    This is simpler and faster than token-based chunking while being
    accurate enough for most use cases.

    Args:
        text: Text content to chunk
        config: Chunking configuration (uses defaults if None)

    Returns:
        List of chunk dictionaries with:
        - text: The chunk text
        - start_char: Starting character position
        - end_char: Ending character position
        - tokens: Estimated token count
        - title: Extracted markdown title (if extract_title=True and found)
    """
    if config is None:
        config = ChunkConfig()

    if not text:
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + config.char_chunk_size, len(text))
        chunk_text_content = text[start:end]

        # Extract title from markdown header if enabled
        title = None
        if config.extract_title:
            lines = chunk_text_content.split('\n')
            if lines and lines[0].startswith('#'):
                title = lines[0].lstrip('#').strip()

        chunk = {
            'text': chunk_text_content,
            'start_char': start,
            'end_char': end,
            'tokens': len(chunk_text_content) // config.chars_per_token,
            'chunk_index': chunk_index,
        }

        if title:
            chunk['title'] = title

        chunks.append(chunk)

        # If we've reached the end, we're done
        if end >= len(text):
            break

        # Move to next chunk with overlap
        start = end - config.char_overlap
        chunk_index += 1

    return chunks


def _generate_chunk_id(source: str, chunk_index: int, start_char: int) -> str:
    """Generate a unique ID for a chunk."""
    key = f"{source}:{chunk_index}:{start_char}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _generate_point_id(source: str, chunk_index: int) -> int:
    """Generate a unique integer ID for Qdrant points."""
    key = f"{source}:{chunk_index}"
    hash_bytes = hashlib.md5(key.encode()).digest()
    # Convert first 8 bytes to int (Qdrant requires int IDs)
    return int.from_bytes(hash_bytes[:8], byteorder='big') & 0x7FFFFFFFFFFFFFFF


def chunk_file(
    file_path: str,
    config: Optional[ChunkConfig] = None,
    relative_to: Optional[str] = None
) -> List[Chunk]:
    """
    Read and chunk a file.

    Args:
        file_path: Path to the file
        config: Chunking configuration
        relative_to: Base path for computing relative paths in metadata

    Returns:
        List of Chunk objects with metadata including:
        - source_file: File path (relative if relative_to provided)
        - filename: Base filename
        - category: Content category from config
        - chunk_index: Index of this chunk
        - total_chunks: Total number of chunks from this file
        - char_start: Starting character position
        - char_end: Ending character position
        - title: Extracted markdown title (if found)
    """
    if config is None:
        config = ChunkConfig()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to read {file_path}: {e}")
        return []

    if not content.strip():
        return []

    # Compute relative path if base provided
    if relative_to:
        try:
            source_path = str(Path(file_path).relative_to(relative_to))
        except ValueError:
            source_path = file_path
    else:
        source_path = file_path

    raw_chunks = chunk_text(content, config)
    total_chunks = len(raw_chunks)

    chunks = []
    for raw_chunk in raw_chunks:
        chunk_index = raw_chunk['chunk_index']

        # Generate unique ID
        chunk_id = _generate_chunk_id(source_path, chunk_index, raw_chunk['start_char'])

        # Build metadata
        metadata = {
            'source_file': source_path,
            'filename': os.path.basename(file_path),
            'category': config.category,
            'chunk_index': chunk_index,
            'total_chunks': total_chunks,
            'char_start': raw_chunk['start_char'],
            'char_end': raw_chunk['end_char'],
        }

        # Add title if extracted
        if 'title' in raw_chunk:
            metadata['title'] = raw_chunk['title']

        # Also store content_type for RAG compatibility
        metadata['content_type'] = config.category

        chunks.append(Chunk(
            id=chunk_id,
            text=raw_chunk['text'],
            tokens=raw_chunk['tokens'],
            metadata=metadata
        ))

    return chunks


def chunk_files(
    paths: List[str],
    config: Optional[ChunkConfig] = None,
    relative_to: Optional[str] = None
) -> List[Chunk]:
    """
    Chunk multiple files and/or directories.

    Args:
        paths: List of file or directory paths
        config: Chunking configuration
        relative_to: Base path for computing relative paths

    Returns:
        List of all Chunk objects from all files
    """
    if config is None:
        config = ChunkConfig()

    all_chunks = []

    for path in paths:
        if os.path.isfile(path):
            if path.endswith(config.file_extensions):
                chunks = chunk_file(path, config, relative_to)
                all_chunks.extend(chunks)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for filename in files:
                    if filename.endswith(config.file_extensions):
                        file_path = os.path.join(root, filename)
                        chunks = chunk_file(file_path, config, relative_to)
                        all_chunks.extend(chunks)

    return all_chunks


# Convenience functions for common configurations

def chunk_for_compiler(
    content: str,
    source_path: str = '',
    category: str = 'datasets',
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Chunk]:
    """
    Chunk content with compiler-optimized settings.

    Uses larger chunks suitable for compiled output.

    Args:
        content: Text content to chunk
        source_path: Source file path for metadata
        category: Content category ('datasets', 'runbooks')
        chunk_size: Chunk size in tokens (default: 1000)
        chunk_overlap: Overlap in tokens (default: 200)

    Returns:
        List of Chunk objects
    """
    config = ChunkConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        extract_title=False,
        category=category
    )

    raw_chunks = chunk_text(content, config)
    total_chunks = len(raw_chunks)

    chunks = []
    for raw_chunk in raw_chunks:
        chunk_index = raw_chunk['chunk_index']
        chunk_id = _generate_chunk_id(source_path, chunk_index, raw_chunk['start_char'])

        chunks.append(Chunk(
            id=chunk_id,
            text=raw_chunk['text'],
            tokens=raw_chunk['tokens'],
            metadata={
                'source_file': source_path,
                'category': category,
                'chunk_index': chunk_index,
                'total_chunks': total_chunks,
                'start_char': raw_chunk['start_char'],
                'end_char': raw_chunk['end_char']
            }
        ))

    return chunks


def chunk_for_rag(
    file_path: str,
    category: str = 'datasets',
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> List[Chunk]:
    """
    Chunk a file with RAG-optimized settings.

    Uses smaller chunks with title extraction for better retrieval.

    Args:
        file_path: Path to the file
        category: Content category ('datasets', 'runbooks')
        chunk_size: Chunk size in tokens (default: 500)
        chunk_overlap: Overlap in tokens (default: 50)

    Returns:
        List of Chunk objects
    """
    config = ChunkConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        extract_title=True,
        category=category
    )

    return chunk_file(file_path, config)


def get_qdrant_point_id(chunk: Chunk) -> int:
    """
    Get a Qdrant-compatible integer ID for a chunk.

    Qdrant requires integer IDs. This generates a consistent
    ID based on the chunk's source file and index.

    Args:
        chunk: The Chunk object

    Returns:
        Integer ID suitable for Qdrant
    """
    source = chunk.metadata.get('source_file', '')
    index = chunk.metadata.get('chunk_index', 0)
    return _generate_point_id(source, index)
