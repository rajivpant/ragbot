# Projects

This folder contains project documentation, work logs, lessons learned, and templates for the Ragbot application.

## Structure

```
projects/
├── active/           # Currently in-progress projects
├── completed/        # Finished projects (archived for reference)
├── work-logs/        # Chronological session logs
├── lessons-learned/  # Reusable insights and patterns
└── templates/        # Project documentation templates
```

## Active Projects

| Project | Description | Status |
|---------|-------------|--------|
| [AI Knowledge Compiler](active/ai-knowledge-compiler/) | Build compilation pipeline for AI Knowledge repos | In Progress |
| [UI Redesign](active/ui-redesign/) | Ragbot UI/UX improvements | Planning |

## Related Projects

These projects are documented in other repositories but are related to Ragbot:

- **AI Knowledge Architecture** - [ai-knowledge-rajiv](https://github.com/rajivpant/ai-knowledge-rajiv/tree/main/projects/active/ai-knowledge-architecture) - The knowledge repository architecture that the compiler supports

## Guidelines

- One folder per project in `active/` or `completed/`
- Work logs go in `work-logs/{project-name}/YYYY-MM-DD-description.md`
- Move projects to `completed/` when done (don't delete)
- Cross-link related projects across repositories
