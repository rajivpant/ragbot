# Group Project README Template

Use this template for parent projects that contain multiple child projects.

---

```markdown
---
project: {group-project-name}
status: active
type: group-project
created: YYYY-MM-DD
tags:
  - {tag1}
  - {tag2}
  - group-project
children:
  - {child-project-1}
  - {child-project-2}
  - {child-project-3}
completion_rule: all-children  # all-children | any-children | threshold:N | manual
related:
  - {related-project}
---

# {Group Project Name}

**Status:** In Progress
**Type:** Group Project
**Created:** YYYY-MM-DD

## Overview

{2-3 sentences describing what this group of projects accomplishes together}

## Child Projects

| Project | Status | Description |
|---------|--------|-------------|
| [{child-1}](../{child-1}/) | In Progress | {brief description} |
| [{child-2}](../{child-2}/) | Not Started | {brief description} |
| [{child-3}](../{child-3}/) | Complete | {brief description} |

## Completion Criteria

**Rule:** `{completion_rule}`

{Explain what "done" means for this group project}

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}

## Progress Summary

**Overall:** {X of Y children complete}

```
[████████░░░░░░░░] 50% complete
```

## Relationships

- **Related groups:** {other group projects this connects to}
- **Spawned from:** {if this emerged from another project}
- **Depends on:** {external dependencies}

## Notes

{Any additional context about managing this group of projects}
```

---

## Completion Rules Reference

| Rule | When to Use |
|------|-------------|
| `all-children` | Every child must complete (book chapters, feature epic) |
| `any-children` | Success when any child completes (pick-one decisions, experiments) |
| `threshold:N` | Need at least N children complete (quarterly goals: 3 of 5) |
| `manual` | Group completion decided manually (ongoing initiatives) |

## Example Group Projects

### Book Project
```yaml
children:
  - synthesis-book-intro
  - synthesis-book-chapter-1
  - synthesis-book-chapter-2
  - synthesis-book-appendix
completion_rule: all-children
```

### Blog Series
```yaml
children:
  - blog-synthesis-part-1
  - blog-synthesis-part-2
  - blog-synthesis-part-3
completion_rule: all-children
```

### Quarterly Goals
```yaml
children:
  - q1-goal-launch-site
  - q1-goal-publish-book
  - q1-goal-10k-users
  - q1-goal-revenue-target
completion_rule: threshold:3  # 3 of 4 goals = success
```

### Site Launch Bundle
```yaml
children:
  - site-synthesiscoding-org
  - site-synthesisengineering-org
completion_rule: all-children
```
