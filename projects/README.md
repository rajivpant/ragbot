# Projects

This folder contains project documentation and templates for the Ragbot application.

## Structure

```
projects/
├── active/           # Currently in-progress projects
├── completed/        # Finished projects (archived for reference)
└── templates/        # Project documentation templates
```

> **Note:** Work logs and lessons learned are maintained in [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects) (private repo) to keep potentially sensitive project details separate from the public codebase.

## Active Projects

| Project | Description | Status |
|---------|-------------|--------|
| [AI Knowledge Compiler](active/ai-knowledge-compiler/) | Compilation pipeline for AI Knowledge repos | Complete (Core) |
| [UI Redesign](active/ui-redesign/) | Ragbot UI/UX improvements | Complete (Phase 6) |

## Completed Projects

| Project | Description |
|---------|-------------|
| [RAG Relevance Improvements](completed/rag-relevance-improvements/) | 4-phase RAG pipeline with verification |
| [RAG Portability Fix](completed/rag-portability-fix/) | Fixed RAG to work across machines |

## Related Projects

These projects are documented in other repositories but are related to Ragbot:

- **AI Knowledge Architecture** - [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/completed/ai-knowledge-architecture) - The knowledge repository architecture that the compiler supports

## Guidelines

- One folder per project in `active/` or `completed/`
- Move projects to `completed/` when done (don't delete)
- Cross-link related projects across repositories
- Work logs and lessons learned → [ai-knowledge-rajiv/projects/](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects)
