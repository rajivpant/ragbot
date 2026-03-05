# Compiler Architecture

> Technical design of the AI Knowledge Compiler.

## Current Architecture (as of March 2026)

The compiler has been simplified to instructions-only compilation. Knowledge concatenation moved to CI/CD (GitHub Actions). RAG indexing reads source directly.

## Location

The compiler lives in `ragbot/src/compiler/` as a library-first design, with CLI integration via the main ragbot command.

## Module Structure

```
src/
├── chunking/               # Shared chunking library
│   ├── __init__.py         # Public API exports
│   └── core.py             # Core chunking algorithms
├── compiler/
│   ├── __init__.py         # Public API exports (instructions-only)
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration parsing
│   ├── cache.py            # Compilation caching
│   ├── assembler.py        # Content assembly
│   ├── inheritance.py      # Inheritance resolution
│   ├── instructions.py     # LLM-specific instruction compilation
│   └── manifest.py         # Manifest generation
└── rag.py                  # RAG runtime (uses chunking/, reads source directly)
```

**Removed modules:**
- `vectors.py` — Deleted. RAG reads source directly via `rag.py`.

## Module Responsibilities

### `config.py`
- Parses `compile-config.yaml` files
- Resolves inheritance declarations
- Validates configuration

### `assembler.py`
- Discovers source files in `source/` folders
- Assembles content from multiple repos based on inheritance
- Respects privacy boundaries (private content stays in private repos)

### `inheritance.py`
- Resolves inheritance chains
- Example: `client` inherits from `company` inherits from `personal`
- Handles circular dependency detection

### `instructions.py`
- Generates LLM-specific instruction formats
- **Each platform's model compiles its own instructions** for best results:
  - Claude's flagship model compiles Claude instructions
  - OpenAI's flagship model compiles ChatGPT instructions
  - Gemini's flagship model compiles Gemini instructions
- Platform-specific formatting:
  - **Claude:** XML tags, verbose OK (200K context)
  - **ChatGPT:** Markdown headers, more concise (128K context)
  - **Gemini:** Aggressive consolidation (10 file limit for Gems)
- Model names come from `engines.yaml` — never hardcoded

### `chunking/` (Shared Library)
- Single source of truth for text chunking
- Used by RAG runtime (`rag.py`)
- Provides `ChunkConfig` for configurable chunk sizes
- Exports `chunk_text()`, `chunk_file()`, `chunk_files()`

### `manifest.py`
- Generates manifest with compilation metadata
- Includes file counts, token counts, timestamps
- Used for cache validation

### `cache.py`
- Tracks source file hashes
- Skips recompilation when sources unchanged
- Invalidates on config changes

## Compilation Flow

```
1. Discovery
   └─> Find ai-knowledge-* directory for project

2. Config Resolution
   └─> Read compile-config.yaml
   └─> Resolve inheritance chains

3. Assembly
   └─> Collect source files from repo + inherited repos
   └─> Respect privacy boundaries

4. Instruction Compilation
   └─> Generate LLM-specific instructions
       ├─> compiled/{project}/instructions/claude.md
       ├─> compiled/{project}/instructions/chatgpt.md
       └─> compiled/{project}/instructions/gemini.md

5. Manifest
   └─> Write compilation manifest
```

**Knowledge concatenation** is handled separately by CI/CD (GitHub Actions), not the compiler.

## Three Dimensions of Compilation

### Dimension 1: By LLM (Format Optimization)

| LLM | Context | Optimization |
|-----|---------|--------------|
| Claude | 200K tokens | Verbose OK, XML tags |
| ChatGPT | 128K tokens | More condensed, markdown |
| Gemini | 10 file limit | Aggressive consolidation |

### Dimension 2: By Project (Multi-Source Assembly)

| Project | Sources |
|---------|---------|
| personal | personal only |
| company | personal + company |
| client | personal + company + client |

## Privacy Model

**Private content NEVER leaves private repos.**

- Shared baseline compilation: Only content from that repo
- Personalized compilation: Full inheritance, output to personal repo

## Configuration Principles

### Single Source of Truth for Models

**Model names are NEVER hardcoded in the compiler.**

All model information comes from `engines.yaml`:
- Model names, categories, and capabilities
- Token limits and context windows
- Cost information

The compiler only knows about **platform names** (anthropic, openai, google). It uses `resolve_model(platform, category)` to get actual model IDs at runtime.

### Platform-Native Compilation

Each platform's flagship model compiles its own instructions:
- Ensures output matches platform conventions
- Models understand their own strengths
- Better optimization than cross-platform compilation
