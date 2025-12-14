"""
Shared Chunking Library for AI Knowledge System

Provides consistent text chunking for:
- AI Knowledge Compiler (build-time chunking for RAG preparation)
- RAG runtime (indexing and retrieval)
- External consumers (ragenie, Claude Code, etc.)

Public API:
- chunk_text(text, chunk_size, overlap) -> list of chunks
- chunk_file(file_path, ...) -> list of chunks with metadata
- chunk_files(file_paths, ...) -> list of all chunks
- ChunkConfig - configuration dataclass
"""

from .core import (
    chunk_text,
    chunk_file,
    chunk_files,
    chunk_for_compiler,
    chunk_for_rag,
    get_qdrant_point_id,
    ChunkConfig,
    Chunk,
)

__all__ = [
    'chunk_text',
    'chunk_file',
    'chunk_files',
    'chunk_for_compiler',
    'chunk_for_rag',
    'get_qdrant_point_id',
    'ChunkConfig',
    'Chunk',
]
