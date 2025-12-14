# Compiler Architecture

> Technical design of the AI Knowledge Compiler.

## Location

The compiler lives in `ragbot/src/compiler/` as a library-first design, with CLI integration via the main ragbot command.

## Module Structure

```
src/compiler/
├── __init__.py         # Public API exports
├── cli.py              # Command-line interface
├── config.py           # Configuration parsing
├── cache.py            # Compilation caching
├── assembler.py        # Content assembly
├── inheritance.py      # Inheritance resolution
├── instructions.py     # LLM-specific instruction compilation
├── manifest.py         # Manifest generation
└── vectors.py          # Vector chunk generation
```

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
- Example: `example-client` inherits from `example-company` inherits from `rajiv`
- Handles circular dependency detection

### `instructions.py`
- Generates LLM-specific instruction formats
- **Claude:** XML tags, verbose OK (200K context)
- **ChatGPT:** Markdown headers, more concise (128K context)
- **Gemini:** Aggressive consolidation (10 file limit for Gems)

### `vectors.py`
- Chunks content for RAG vector search
- Uses sentence-transformers for embeddings
- Generates JSON chunks for Qdrant indexing

### `manifest.py`
- Generates `manifest.json` with compilation metadata
- Includes file counts, token counts, timestamps
- Used for cache validation

### `cache.py`
- Tracks source file hashes
- Skips recompilation when sources unchanged
- Invalidates on config changes

## Compilation Flow

```
1. Discovery
   └─> Find all ai-knowledge-* directories

2. Config Resolution
   └─> Read compile-config.yaml from each repo
   └─> Resolve inheritance chains

3. Assembly (per project)
   └─> Collect source files from repo + inherited repos
   └─> Respect privacy boundaries

4. Compilation
   ├─> Generate LLM-specific instructions
   │   ├─> compiled/instructions/claude/{project}.md
   │   ├─> compiled/instructions/openai/{project}.md
   │   └─> compiled/instructions/gemini/{project}.md
   │
   └─> Generate vector chunks
       └─> compiled/vectors/{project}.json

5. Manifest
   └─> Write compiled/manifest.json
```

## Output Structure

```
ai-knowledge-{name}/
└── compiled/
    ├── instructions/
    │   ├── claude/
    │   │   └── {name}.md
    │   ├── openai/
    │   │   └── {name}.md
    │   └── gemini/
    │       └── {name}.md
    ├── knowledge/
    │   └── full/
    │       └── {assembled-files}
    ├── vectors/
    │   └── {name}.json
    └── manifest.json
```

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
| rajiv | rajiv only |
| example-company | rajiv + example-company |
| example-client | rajiv + example-company + example-client |

### Dimension 3: By Context (Task-Specific Filtering)

Future feature for filtering content by context tags:
- `writing-mode`: Voice/style instructions
- `coding-mode`: Technical instructions
- `meeting-prep`: Meeting runbooks, people datasets

## Privacy Model

**Private content NEVER leaves private repos.**

- Shared baseline compilation: Only content from that repo
- Personalized compilation: Full inheritance, output to personal repo

## Related

- [AI Knowledge Architecture](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture) - The repository architecture the compiler supports
