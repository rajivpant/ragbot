# Project Documentation Convention

A consistent structure for organizing project documentation across repositories.

## Overview

This convention separates **project documentation** (plans, logs, lessons) from **source code** and **AI knowledge content**. It provides a predictable structure that works for both human engineers and AI coding assistants.

## Folder Structure

```
{repository}/
├── projects/                    # Project documentation (human reference)
│   ├── active/                  # Currently in-progress projects
│   │   └── {project-name}/
│   │       ├── README.md        # Overview, status, quick links
│   │       ├── architecture.md  # Design decisions (optional)
│   │       ├── implementation.md # Phase-by-phase guide (optional)
│   │       └── roadmap.md       # Future work (optional)
│   ├── completed/               # Finished projects (archived)
│   │   └── {project-name}/
│   │       ├── README.md
│   │       └── plan.md          # Original plan for reference
│   ├── work-logs/               # Chronological session history
│   │   └── {project-name}/
│   │       └── YYYY-MM-DD-{summary}.md
│   ├── lessons-learned/         # Cross-cutting insights
│   │   ├── index.md             # Index of all lessons
│   │   └── {topic}.md
│   └── templates/               # Reusable templates
└── src/                         # Source code (separate from docs)
```

## Why This Structure?

### Separation of Concerns

| Folder | Purpose | Audience |
|--------|---------|----------|
| `projects/` | Documentation, planning, history | Humans, AI assistants |
| `src/` | Executable code | Compilers, runtimes |
| `source/` (in ai-knowledge repos) | AI knowledge content | AI compilation pipeline |

Project documentation is **not** source code. Mixing them creates confusion about what gets compiled, deployed, or consumed by AI tools.

### Active vs Completed

Moving projects to `completed/` instead of deleting them:
- Preserves institutional knowledge
- Enables learning from past work
- Provides templates for similar future projects
- Supports blog post writing and retrospectives

### Work Logs vs Project Docs

| Work Logs | Project Docs |
|-----------|--------------|
| Chronological (by date) | Conceptual (by topic) |
| What happened in a session | What the design is |
| May become stale | Should stay current |
| Raw material for learning | Refined reference |

Work logs capture the journey. Project docs capture the destination.

## Naming Conventions

### Folders
- **kebab-case**: `ai-knowledge-compiler`, `ui-redesign`
- **Descriptive**: Name describes the project, not the date

### Work Log Files
- **Date prefix**: `YYYY-MM-DD-{summary}.md`
- **Summary**: 3-5 words describing the session focus
- Example: `2025-12-13-initial-architecture-and-migration.md`

### Lesson Files
- **Topic-based**: `sensitive-data-in-git-history.md`
- **No dates in filename**: Lessons are timeless (date goes in content)

## Project README Template

```markdown
# {Project Name}

**Status:** {In Progress | Complete | On Hold}
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

## Overview

{2-3 sentences describing what this project is and why it exists}

## Problem Statement

{What problem does this solve? Why is it needed?}

## Solution

{High-level approach, not implementation details}

## Documents

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | {description} |
| [implementation.md](implementation.md) | {description} |

## Quick Links

- **Source Code:** `path/to/code/`
- **Related:** [Other Project](link)

## Current Status

| Phase/Feature | Status | Description |
|---------------|--------|-------------|
| Phase 1 | Complete | {what it does} |
| Phase 2 | In Progress | {what it does} |
```

## Work Log Template

```markdown
# {Date}: {Session Summary}

**Project:** {project-name}
**Duration:** {approximate time}
**Focus:** {main goal of session}

## What Was Done

- {Accomplishment 1}
- {Accomplishment 2}

## Decisions Made

- **{Decision}**: {rationale}

## Issues Encountered

- {Problem}: {how it was resolved or status}

## Next Steps

- [ ] {Todo 1}
- [ ] {Todo 2}
```

## Lesson Learned Template

```markdown
# {Title}

> **TL;DR**: {One sentence summary}

## Context

- **Project:** {which project}
- **Date:** YYYY-MM-DD
- **Severity:** {High | Medium | Low}

## The Problem

{What went wrong or what challenge was faced}

## Root Cause

{Why it happened}

## The Solution

{How it was fixed}

## Prevention

{How to prevent it in the future}

## Key Takeaways

1. {Lesson 1}
2. {Lesson 2}

## Technical Details

{Code snippets, commands, etc.}

## Related

- [Other Lesson](link)
- [Project](link)

## Blog Potential

- **Audience:** {who would benefit}
- **Angle:** {what's the story}
```

## Cross-Repository References

When projects span multiple repositories:

```markdown
## Related Projects (in other repos)

| Project | Location | Description |
|---------|----------|-------------|
| AI Knowledge Compiler | [ragbot](https://github.com/user/ragbot/tree/main/projects/active/ai-knowledge-compiler) | Compilation pipeline |
| UI Redesign | [ragbot](https://github.com/user/ragbot/tree/main/projects/active/ui-redesign) | UI improvements |
```

Use full GitHub URLs for cross-repo links so they work from anywhere.

## Integration with AI Assistants

### Claude Code / CLAUDE.md

Add to your global `~/.claude/CLAUDE.md`:

```markdown
## Project Documentation Convention

All repositories use a consistent `projects/` folder structure:
- `projects/active/` - Current projects with README.md
- `projects/completed/` - Archived projects
- `projects/work-logs/` - Session history (YYYY-MM-DD-summary.md)
- `projects/lessons-learned/` - Cross-cutting insights

See: https://github.com/rajivpant/ragbot/blob/main/docs/conventions/project-documentation.md
```

### AI Knowledge Repos

In `ai-knowledge-*` repositories, the `projects/` folder is at the repo root, separate from `source/` (which contains AI knowledge content for compilation).

## Examples

### Active Project Example

```
projects/active/ai-knowledge-compiler/
├── README.md           # Overview and status
├── architecture.md     # Module design
└── usage.md           # CLI commands and examples
```

### Completed Project Example

```
projects/completed/synthesis-article-series/
├── README.md          # Summary of what was accomplished
└── plan.md           # Original detailed plan
```

### Work Log Example

```
projects/work-logs/ai-knowledge-architecture/
├── 2025-12-13-initial-architecture-and-migration.md
└── 2025-12-14-rag-integration-and-docs-reorg.md
```

## Adoption

To adopt this convention in a repository:

1. Create `projects/` folder at repo root
2. Create subfolders: `active/`, `completed/`, `work-logs/`, `lessons-learned/`, `templates/`
3. Add `projects/README.md` listing active projects
4. Move any existing project docs into the structure
5. Update repo's `CLAUDE.md` to reference the convention

## Changelog

- **2025-12-14**: Initial version based on ai-knowledge architecture work
