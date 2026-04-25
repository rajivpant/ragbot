---
name: ragbot-demo-skill
description: >
  A bundled sample skill that ships with the ragbot demo. Demonstrates
  the SKILL.md format and shows up in `ragbot skills list` when
  RAGBOT_DEMO=1. Replace with your own skills when building a real
  knowledge base; see the synthesis-skills repository for community
  examples.
license: CC0-1.0
metadata:
  author: ragbot demo
  version: 1.0.0
  source_type: bundled-demo
---

# Ragbot Demo Skill

This is a self-contained sample skill that the ragbot demo ships with.
Its job is to show how ragbot discovers, indexes, and lists skills
without requiring the user to install or configure anything.

## When to use this skill

Use this when:

- You are evaluating ragbot for the first time and want a working
  example of a skill.
- You want to see how skill content appears in the chat retrieval
  results — try asking "what skills do I have?" in the demo chat and
  this entry should come back.

## Anatomy of a skill

A skill is a directory containing at least a `SKILL.md` with YAML
frontmatter (name, description, optional metadata). Skills can also
contain:

- A `references/` directory of additional markdown documents.
- Bundled scripts (`*.py`, `*.sh`, etc.) that are indexed for
  searchability but not inlined into compiled instructions.
- Other text artifacts: configs, sample data, READMEs in
  subdirectories.

The ragbot indexer walks the whole tree, classifies each file (skill_md,
reference, script, other), and tags every chunk with the skill name so
queries can land on the right place.

## How discovery works

By default, skills are discovered from:

1. `~/.synthesis/skills/` — synthesis-engineering shared install
2. `~/.claude/skills/` — Claude Code private skills
3. `~/.claude/plugins/cache/<vendor>/skills/` — plugin-installed
4. Per-workspace roots declared in `compile-config.yaml`

When `RAGBOT_DEMO=1`, ragbot ignores those locations and uses only the
bundled `demo/skills/` directory inside the repo. This is what lets
the demo run on any machine without leaking real skills into
screenshots.

## Replacing this skill

This skill exists only so the demo has something to display. When you
build a real knowledge base, write your own skills as directories
under `~/.synthesis/skills/` (or your equivalent) and they'll be
discovered automatically.
