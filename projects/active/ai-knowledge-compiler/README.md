# AI Knowledge Compiler

**Status:** Complete (v0.2.0)
**Created:** 2025-12-13
**Last Updated:** 2025-12-14

## Overview

The AI Knowledge Compiler transforms human-edited source content from `ai-knowledge-*` repositories into AI-optimized compiled output. It handles inheritance, LLM-specific formatting, and vector chunk generation.

## Problem Statement

Human-edited knowledge bases are organized for human convenience (folders, READMEs, granular files). AI assistants need content optimized for their consumption:
- Token-efficient (no redundancy)
- Platform-specific formatting
- Pre-assembled for contexts
- Ready for RAG vector search

## Solution

A compilation pipeline that:
1. Discovers all `ai-knowledge-*` repos via convention
2. Resolves inheritance chains (personal → team → project)
3. Generates LLM-specific instruction formats
4. Creates vector chunks for RAG
5. Produces manifests for validation

## Documents

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Compiler architecture and module design |
| [usage.md](usage.md) | CLI commands and usage examples |

## Quick Links

- **Source Code:** `ragbot/src/compiler/`

## Related Projects

| Project | Location | Description |
|---------|----------|-------------|
| **AI Knowledge Architecture** | [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture) | Repository architecture this compiler supports |
| **Ragbot UI Redesign** | [ragbot/projects/active/ui-redesign](../ui-redesign/) | UI that uses compiler output |

## Current Status (v0.2.0)

| Feature | Status |
|---------|--------|
| Convention-based discovery | Complete |
| Inheritance resolution | Complete |
| Inheritance content merging | Complete |
| Claude instruction compilation | Complete |
| ChatGPT instruction compilation | Complete |
| Gemini instruction compilation | Complete |
| Vector chunk generation | Complete |
| Manifest generation | Complete |
| CLI interface | Complete |
| knowledge/full/ output (GitHub sync) | Complete |
| knowledge/by-context/ output | Complete |
| Context filtering | Complete |
| Personalized compilation | Complete |
| CI/CD integration | Pending |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.2.0 | 2025-12-14 | Inheritance merging, context filtering, knowledge/full/ and by-context/ output |
| 0.1.0 | 2025-12-13 | Initial compiler with convention-based discovery and LLM compilation |

## Future Considerations

These items are documented for potential future projects. They don't block current project completion.

### CI/CD Integration

**Current state**: Compiler runs manually via `ragbot compile` CLI.

**Future project**: GitHub Actions workflow for auto-compilation:
- Trigger on changes to `source/` in any ai-knowledge repo
- Run `--dry-run` validation first
- Commit compiled output if validation passes
- Post-compilation hooks (e.g., sync to Claude Projects)

### Token Budget Enforcement

**Current state**: No hard limits on compiled output size.

**Future enhancement**: Prevent output exceeding LLM context windows:
- Token counting during compilation
- Per-LLM limits (Claude 200K, GPT 400K, Gemini 1M)
- Warnings at 80%, errors at limit

### Dry-Run / Validation Mode

**Current state**: Compiler writes output directly.

**Future enhancement**: `ragbot compile --dry-run` to validate without writing:
- Check inheritance chains
- Report missing files
- Catch privacy leaks before they happen

### Sync Status Dashboard

**Future enhancement**: Visibility into compilation state:
- Last compile time per repo
- Files changed since last compile
- Inheritance tree visualization
