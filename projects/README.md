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

## Templates

Reusable templates for all projects (public and private):

### Project Documentation
| Template | Purpose |
|----------|---------|
| [project-readme.md](templates/project-readme.md) | Project overview and status |
| [group-project-readme.md](templates/group-project-readme.md) | Parent project with child projects |
| [work-log.md](templates/work-log.md) | Session work log |
| [lesson-learned.md](templates/lesson-learned.md) | Cross-cutting insight |
| [context-snapshot.md](templates/context-snapshot.md) | AI context recovery (CONTEXT.md) |

### Tiered Summaries
| Template | Purpose |
|----------|---------|
| [weekly-summary.md](templates/weekly-summary.md) | Weekly rollup of work logs |
| [monthly-summary.md](templates/monthly-summary.md) | Monthly progress and patterns |
| [quarterly-summary.md](templates/quarterly-summary.md) | Strategic quarterly review |

## Guidelines

- One folder per project in `active/` or `completed/`
- Move projects to `completed/` when done (don't delete)
- Cross-link related projects across repositories
- Work logs and lessons learned → [ai-knowledge-rajiv/projects/](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects)
- Full convention: [docs/conventions/project-documentation.md](../docs/conventions/project-documentation.md)
