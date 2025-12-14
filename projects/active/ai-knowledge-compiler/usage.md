# Compiler Usage

> CLI commands and usage examples for the AI Knowledge Compiler.

## Basic Commands

### Compile All Repositories

```bash
python3 src/ragbot.py compile --all --verbose
```

### Compile Specific Project

```bash
python3 src/ragbot.py compile --project example-client
```

### Compile Without LLM API Calls

```bash
python3 src/ragbot.py compile --all --no-llm
```

This skips LLM-based instruction optimization, useful for:
- Quick compilation during development
- When LLM API keys aren't available
- Testing changes to vector generation

## Output Locations

After compilation, output is written to each repo's `compiled/` folder:

```
ai-knowledge-{name}/
└── compiled/
    ├── instructions/
    │   ├── claude/{name}.md
    │   ├── openai/{name}.md
    │   └── gemini/{name}.md
    ├── knowledge/full/
    ├── vectors/{name}.json
    └── manifest.json
```

## Compilation Results Example

From 2025-12-13 compilation:

| Project | Source Files | Tokens | Vector Chunks |
|---------|--------------|--------|---------------|
| rajiv | 38 | 96,830 | 53 |
| ragenie | 3 | 6,077 | 10 |
| example-client | 15 | 18,484 | 29 |
| example-client | 4 | 1,772 | 4 |
| example-client | 2 | 553 | 1 |
| example-client | 6 | 6,031 | 9 |
| ragbot | 1 | 124 | 0 |
| example-client | 8 | 1,832 | 7 |
| example-company | 13 | 9,054 | 11 |

## Configuration

### compile-config.yaml

Each repo can have a `compile-config.yaml` to customize compilation:

```yaml
# Example: ai-knowledge-example-client/compile-config.yaml
inherits_from:
  - example-company

contexts:
  - writing
  - editorial

exclude_patterns:
  - "*.draft.md"
  - "archive/*"
```

### workspace.yaml

Workspace metadata:

```yaml
# Example: ai-knowledge-example-company/workspace.yaml
name: example-company
display_name: Example-Company Software
type: company
```

## Convention-Based Discovery

The compiler automatically discovers repositories by convention:

1. Looks for `ai-knowledge-*` directories
2. No explicit configuration needed
3. Paths checked:
   - `~/projects/my-projects/ai-knowledge/`
   - Environment variable overrides

## Using Compiled Output

### Claude Projects

1. Copy content from `compiled/instructions/claude/{project}.md`
2. Paste into Claude project custom instructions
3. Enable GitHub sync → point to `compiled/knowledge/full/`

### ChatGPT

1. Copy from `compiled/instructions/openai/{project}.md`
2. Upload files from `compiled/knowledge/full/`

### Gemini Gems

1. Copy from `compiled/instructions/gemini/{project}.md`
2. Upload consolidated files (max 10 files)

### RAG (Qdrant)

1. Load `compiled/vectors/{project}.json`
2. Index in Qdrant collection
3. Use ragbot's RAG mode for retrieval

## Troubleshooting

### Compilation fails with "repo not found"

Ensure repos are in expected location:
```bash
ls ~/projects/my-projects/ai-knowledge/
```

### Token count seems wrong

Check for large files that might need exclusion:
```bash
find source/ -name "*.md" -exec wc -w {} \;
```

### Inheritance not working

Verify `compile-config.yaml` syntax:
```bash
cat compile-config.yaml
```

Check that inherited repo exists and is accessible.
