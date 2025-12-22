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
│   │       ├── CONTEXT.md       # AI context snapshot (for session continuity)
│   │       ├── architecture.md  # Design decisions (optional)
│   │       ├── implementation.md # Phase-by-phase guide (optional)
│   │       └── roadmap.md       # Future work (optional)
│   ├── completed/               # Finished projects (archived)
│   │   └── {project-name}/
│   │       ├── README.md
│   │       └── plan.md          # Original plan for reference
│   │   └── index.md             # Semantic index of completed projects
│   ├── work-logs/               # Chronological session history
│   │   └── {project-name}/
│   │       └── YYYY-MM-DD-{summary}.md
│   │   └── summaries/           # Tiered summaries
│   │       ├── weekly/          # YYYY-WNN.md
│   │       ├── monthly/         # YYYY-MM.md
│   │       └── quarterly/       # YYYY-QN.md
│   ├── lessons-learned/         # Cross-cutting insights
│   │   ├── index.md             # Index of all lessons
│   │   └── {topic}.md
│   ├── meta/                    # Cross-project observations
│   │   ├── patterns.md          # Recurring patterns across projects
│   │   └── insights.md          # Productivity observations
│   └── templates/               # Reusable templates
└── src/                         # Source code (separate from docs)
```

## Public vs Private Repository Split

When working with both public (open source) and private repositories, split content by confidentiality:

### Public Repositories (e.g., ragbot, ragenie)

```
projects/
├── active/           # Project plans, architecture, implementation guides
├── completed/        # Archived project docs
└── templates/        # Reusable templates (shared across all projects)
```

**What goes here:** Architecture decisions, implementation guides, roadmaps—anything helpful for contributors and safe to share publicly.

### Private Knowledge Repository (e.g., ai-knowledge-{personal})

```
projects/
├── active/           # Private-only projects
├── completed/        # Archived private projects
├── work-logs/        # ALL work logs (for any project, any repo)
│   ├── ragbot/
│   ├── ragenie/
│   └── {other-project}/
└── lessons-learned/  # ALL lessons (cross-cutting insights)
```

**What goes here:** Work logs and lessons learned contain raw thinking, confidential details, and unfiltered notes. These are personal knowledge artifacts that belong in your private knowledge base, even when they reference public projects.

### Cross-References

Link between public project docs and private work logs:

**In public project README:**
```markdown
## Work Logs
Work logs for this project are in the private knowledge base.
```

**In private work log:**
```markdown
**Project:** ragbot/ai-knowledge-compiler
**Public docs:** https://github.com/rajivpant/ragbot/tree/main/projects/active/ai-knowledge-compiler
```

### Why This Split?

| Content Type | Location | Reason |
|--------------|----------|--------|
| Architecture | Public repo | Helps contributors understand the project |
| Implementation plan | Public repo | Documents the approach for collaboration |
| Work logs | Private repo | Contains raw notes, mistakes, confidential context |
| Lessons learned | Private repo | May reference clients, contain sensitive insights |

Work logs capture the messy journey. Public docs show the polished destination.

---

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

## Synthesis Project Management

These features optimize the documentation system for AI coding assistants like Claude Code.

### Context Snapshots (CONTEXT.md)

Every active project should have a `CONTEXT.md` file that enables instant context recovery:

```markdown
# Current Context: {Project Name}

**Last session:** YYYY-MM-DD
**State:** {Phase X complete, starting Phase Y}

## Immediate Next Steps
1. {Most important next action}
2. {Second priority}

## Key Decisions Still Open
- {Decision}: {options being considered}

## Files Currently In Progress
| File | Status | Notes |
|------|--------|-------|
| `path/to/file.py` | 60% complete | {what remains} |

## Blockers
- {Blocker or "None currently"}

## Recent Progress (last 3 sessions)
- YYYY-MM-DD: {what was accomplished}
```

**Session protocols:**
- **Start:** Read CONTEXT.md first, check blockers, pick up from "Immediate Next Steps"
- **End:** Update all sections to reflect current state

### Semantic Indexing

Add YAML frontmatter to all project READMEs for discoverability:

```yaml
---
tags: [api, authentication, security]
technologies: [python, fastapi, jwt]
outcome: success  # or: in-progress, paused, abandoned
related: [user-management, oauth-integration]
---
```

Maintain a `completed/index.md` semantic index organized by:
- Tags
- Technologies
- Outcomes
- Project relationships

### Tiered Summarization

Roll up work logs into summaries at different time scales:

| Level | Frequency | Purpose |
|-------|-----------|---------|
| **Weekly** | On request | What happened this week across projects |
| **Monthly** | On request | Progress, patterns, decisions |
| **Quarterly** | On request | Strategic review, retrospective |

Templates: `templates/weekly-summary.md`, `monthly-summary.md`, `quarterly-summary.md`

### Pattern Detection

Maintain `meta/patterns.md` to document:
- **Technical patterns** that work well (e.g., "Single Source of Truth")
- **Process patterns** that improve productivity (e.g., "Phased Implementation")
- **Anti-patterns** to avoid (e.g., "Blind Text Replacement")

Update patterns when:
- Completing a project that used a notable approach
- A lesson applies across multiple projects
- Noticing recurring friction or success

### Proactive Intelligence

AI assistants should:
1. **Before starting work:** Search lessons learned, check related projects, consult semantic indexes
2. **When starting new projects:** Check for similar completed projects, learn from predecessors
3. **During sessions:** Watch for patterns to document
4. **At session end:** Update CONTEXT.md, offer to create work log

### Group Projects (Semantic Grouping)

Group related projects without folder nesting using semantic parent/child relationships in frontmatter.

**Parent (group) project frontmatter:**
```yaml
---
tags: [writing, book, group-project]
type: group-project
children:
  - synthesis-chapter-1
  - synthesis-chapter-2
  - synthesis-chapter-3
completion_rule: all-children  # all-children | any-children | threshold:N | manual
---
```

**Child project frontmatter:**
```yaml
---
tags: [writing, book-chapter]
outcome: in-progress
parent: synthesis-engineering-book
related: [synthesis-chapter-1, synthesis-chapter-3]
---
```

**Completion rules:**
| Rule | Meaning |
|------|---------|
| `all-children` | Complete when ALL children are complete |
| `any-children` | Complete when ANY child is complete |
| `threshold:N` | Complete when N children are complete |
| `manual` | Requires explicit completion (default) |

**Benefits:**
- Flat folder structure (all projects in `active/`)
- Multi-membership (project can have multiple parents)
- Searchable relationships via semantic index
- No folder restructuring when changing groups

**Use cases:** Book chapters, blog series, multi-site launches, quarterly goals, feature epics

Template: `templates/group-project-readme.md`

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

## Completing and Reactivating Projects

### Completing a Project

When a project reaches a stable, functional state:

1. **Move the folder** from `active/` to `completed/`:
   ```bash
   git mv projects/active/{project-name} projects/completed/{project-name}
   ```

2. **Update the project README** (optional):
   - Set status to "Complete"
   - Update "Last Updated" date
   - Ensure "Future Considerations" captures remaining ideas

3. **Update `projects/README.md`** if your repo has one:
   - Move project from "Active Projects" table to "Completed Projects" table

4. **Commit** with a descriptive message:
   ```bash
   git commit -m "Complete {project-name} project - move to completed/"
   ```

### Reactivating a Project

If you need to resume work on a completed project:

1. **Move the folder** back to `active/`:
   ```bash
   git mv projects/completed/{project-name} projects/active/{project-name}
   ```

2. **Update status** in the project README

3. **Update `projects/README.md`** tables if applicable

4. **Commit** with context:
   ```bash
   git commit -m "Reactivate {project-name} - {reason for reactivation}"
   ```

### Why This Works

- **Git preserves full history** — Nothing is lost when moving folders
- **No data deletion** — Completed projects remain accessible
- **Easy reversal** — `git mv` in either direction takes seconds
- **Clear status** — Folder location indicates project state

### Future Considerations Section

Before completing a project, ensure it has a "Future Considerations" section documenting:
- Enhancements that could be future projects
- Open questions not blocking completion
- Ideas that emerged during implementation

This prevents losing valuable context when the project moves to `completed/`.

## Adoption

To adopt this convention in a repository:

1. Create `projects/` folder at repo root
2. Create subfolders: `active/`, `completed/`, `work-logs/`, `lessons-learned/`, `templates/`
3. Add `projects/README.md` listing active projects
4. Move any existing project docs into the structure
5. Update repo's `CLAUDE.md` to reference the convention

## Changelog

- **2025-12-16**: Added Group Projects (semantic grouping) pattern and template
- **2025-12-16**: Added synthesis project management section (CONTEXT.md, semantic indexing, tiered summarization, pattern detection, proactive intelligence)
- **2025-12-14**: Initial version based on ai-knowledge architecture work
