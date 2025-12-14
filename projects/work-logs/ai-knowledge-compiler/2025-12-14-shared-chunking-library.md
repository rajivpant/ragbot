# 2025-12-14: Shared Chunking Library

**Project:** AI Knowledge Compiler
**Duration:** ~2 hours
**Focus:** Extract shared chunking functionality from duplicated code

## What Was Done

1. **Created shared chunking library** (`src/chunking/`)
   - Core chunking algorithms in `core.py`
   - Public API in `__init__.py`
   - Dataclasses: `ChunkConfig`, `Chunk`
   - Functions: `chunk_text()`, `chunk_file()`, `chunk_files()`
   - Convenience: `chunk_for_compiler()`, `chunk_for_rag()`, `get_qdrant_point_id()`

2. **Updated compiler/vectors.py**
   - Now imports from shared chunking library
   - `chunk_content()` marked as deprecated (wraps new API)
   - `chunk_file()` uses `chunk_for_compiler()`
   - Backward compatible with existing callers

3. **Updated rag.py**
   - Removed duplicated `_chunk_file()` function
   - Uses shared `chunk_files()` and `ChunkConfig`
   - Uses `get_qdrant_point_id()` for consistent ID generation

4. **Created project documentation convention**
   - `docs/conventions/project-documentation.md` - Full convention spec
   - Added reference to global `~/.claude/CLAUDE.md`

## Decisions Made

- **Chunk sizes remain different by use case**: Compiler uses 1000 tokens, RAG uses 500 tokens. This is intentional - larger chunks for compilation output, smaller for semantic search.

- **Backward compatibility**: The old `chunk_content()` function is kept but marked deprecated. Existing callers continue to work.

- **Shared ID generation**: Both compiler and RAG now use consistent ID generation from the chunking library.

## Technical Details

### Chunking Library API

```python
from src.chunking import (
    chunk_text,      # Raw text chunking
    chunk_file,      # File chunking with metadata
    chunk_files,     # Multiple files/directories
    chunk_for_compiler,  # Compiler-optimized (1000 tokens)
    chunk_for_rag,       # RAG-optimized (500 tokens)
    get_qdrant_point_id, # Integer ID for Qdrant
    ChunkConfig,     # Configuration dataclass
    Chunk,           # Chunk dataclass
)
```

### Configuration Options

```python
config = ChunkConfig(
    chunk_size=500,        # Tokens
    chunk_overlap=50,      # Tokens
    chars_per_token=4,     # Conversion ratio
    extract_title=True,    # Extract markdown titles
    category='datasets',   # Metadata category
    file_extensions=('.md', '.txt', '.yaml', '.yml')
)
```

## Issues Encountered

- **Import path**: Had to add `chunk_for_compiler`, `chunk_for_rag`, `get_qdrant_point_id` to `__init__.py` exports after initial creation.

## Next Steps

- [ ] Add unit tests for chunking library
- [ ] Consider adding chunk-level caching
- [ ] Document chunking library in ragbot README

## Related

- [AI Knowledge Architecture](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture)
- [Project Documentation Convention](../../docs/conventions/project-documentation.md)
