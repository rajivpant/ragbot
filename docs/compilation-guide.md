# AI Knowledge Compilation Guide

This guide explains how the AI Knowledge compiler works, including the inheritance system and privacy model.

## Core Concept: Output Repo Determines Content

**The output repo determines what content is included—not who runs the compiler.**

Anyone with write access to a repo can compile into it. The content included depends solely on the output repo's position in the inheritance tree.

```bash
ragbot compile --all-with-inheritance --output-repo ~/ai-knowledge/ai-knowledge-{company}
```

This produces the same output regardless of who runs the command.

## Repository Types

AI Knowledge repos follow a hierarchy:

```
ai-knowledge-{templates}     ← Public templates (root)
    ↓
ai-knowledge-{person}        ← Personal identity
    ↓
ai-knowledge-{company}       ← Company knowledge
    ↓
ai-knowledge-{client}        ← Client-specific content
```

Each repo can contain:
- `source/` — Human-edited content
- `compiled/` — AI-optimized output (auto-generated)
- `compile-config.yaml` — Compilation settings

## Compilation Modes

### Baseline (Single Repo)

Compiles only the content from one repo:

```bash
ragbot compile --repo ~/ai-knowledge/ai-knowledge-{project}
```

Output: `ai-knowledge-{project}/compiled/{project}/`

### With Inheritance (Multiple Repos)

Compiles content from a project and all its ancestors:

```bash
ragbot compile --project {project} --with-inheritance --output-repo ~/ai-knowledge/ai-knowledge-{output}
```

Output: `ai-knowledge-{output}/compiled/{project}/`

### All Projects With Inheritance

Compiles all projects into a single output repo:

```bash
ragbot compile --all-with-inheritance --output-repo ~/ai-knowledge/ai-knowledge-{output}
```

Output: `ai-knowledge-{output}/compiled/{project1}/`, `compiled/{project2}/`, etc.

## Inheritance Configuration

Inheritance relationships are defined in `my-projects.yaml` in your personal repo:

```yaml
# my-projects.yaml
version: 1
base_path: ~/projects/ai-knowledge

projects:
  templates:
    local_path: ~/projects/ai-knowledge/ai-knowledge-templates
    inherits_from: []
    description: Public templates (root)

  personal:
    local_path: ~/projects/ai-knowledge/ai-knowledge-personal
    inherits_from:
      - templates
    description: Personal identity

  company:
    local_path: ~/projects/ai-knowledge/ai-knowledge-company
    inherits_from:
      - personal
    description: Company knowledge

  client-a:
    local_path: ~/projects/ai-knowledge/ai-knowledge-client-a
    inherits_from:
      - company
    description: Client A project
```

## Privacy Model

Content included depends on the output repo's position in the inheritance tree:

| Output Repo | Compiling client-a | Content Included |
|-------------|-------------------|------------------|
| ai-knowledge-personal | compiled/client-a/ | templates + personal + company + client-a |
| ai-knowledge-company | compiled/client-a/ | templates + company + client-a |
| ai-knowledge-client-a | compiled/client-a/ | templates + client-a |

**Private content never leaks.** Each repo only contains compilations with content appropriate for that repo's access level.

## Who Compiles vs Who Uses

The person who compiles may differ from the person who uses the output:

| Scenario | Who Compiles | Output Repo | Who Uses |
|----------|--------------|-------------|----------|
| Personal use | You | ai-knowledge-{you} | You |
| Team use | Anyone with write access | ai-knowledge-{company} | Team members |
| Client use | Anyone with write access | ai-knowledge-{client} | Client |

**Example:** You compile into ai-knowledge-{company} so team members can use the pre-compiled outputs without running the compiler themselves.

## Output Structure

Each compiled project produces:

```
compiled/{project}/
├── instructions/           # LLM-specific custom instructions
│   ├── claude.md           # For Anthropic models (Claude)
│   ├── chatgpt.md          # For OpenAI models (GPT-5.x)
│   └── gemini.md           # For Google models (Gemini)
├── knowledge/              # Individual knowledge files
│   ├── runbooks-*.md
│   └── datasets-*.md
├── all-knowledge.md        # Consolidated (for file-count limits)
└── vectors/                # RAG chunks
    └── chunks.jsonl
```

## LLM-Specific Instructions

The compiler generates separate instruction files for each major LLM platform. Each file is optimized for that platform's capabilities and conventions.

### Automatic Instruction Selection

When using Ragbot (CLI or Web UI), the correct instruction file is **automatically loaded based on the model being used**:

| Model Type | Instruction File |
|------------|------------------|
| Anthropic models (Claude, claude-sonnet, claude-opus, etc.) | `instructions/claude.md` |
| OpenAI models (GPT-5.x, etc.) | `instructions/chatgpt.md` |
| Google models (Gemini, gemini-2.5-pro, etc.) | `instructions/gemini.md` |

### Mid-Conversation Model Switching

When users switch models mid-conversation in the Web UI, the system automatically loads the appropriate instructions for the new model. This happens transparently on each request.

**Example flow:**
1. User selects workspace "personal" and Claude model
2. System loads `claude.md` instructions
3. User switches to GPT-5.2 mid-conversation
4. On next message, system automatically loads `chatgpt.md` instructions
5. Conversation continues with GPT-5.2-optimized instructions

### Implementation Details

This behavior is centralized in `ragbot/core.py`:

```python
# core.py automatically determines which instructions to load
chat(
    prompt="Hello",
    model="anthropic/claude-sonnet-4",  # → loads claude.md
    workspace_name="personal"
)

chat(
    prompt="Hello",
    model="gpt-5.2",  # → loads chatgpt.md
    workspace_name="personal"
)
```

The instruction selection happens in the shared library, ensuring consistent behavior between CLI, API, and Web UI.

### Adding Support for New LLM Providers

When adding a new LLM provider to `engines.yaml`:

1. **Create instruction template** in the compiler's instruction generator
2. **Add mapping** in `ragbot/workspaces.py`:
   ```python
   ENGINE_TO_INSTRUCTION_FILE = {
       'anthropic': 'claude.md',
       'openai': 'chatgpt.md',
       'google': 'gemini.md',
       'new_provider': 'new_provider.md',  # Add new mapping
   }
   ```
3. **Update model detection** in `ragbot/core.py`:
   ```python
   if "new_model_pattern" in model_lower:
       return "new_provider"
   ```
4. **Recompile** all projects to generate the new instruction files

## CLI Reference

```bash
# Baseline compilation
ragbot compile --repo ~/ai-knowledge/ai-knowledge-{project}

# Single project with inheritance
ragbot compile --project {project} --with-inheritance

# All projects with inheritance (into personal repo)
ragbot compile --all-with-inheritance

# All projects with inheritance (into specific repo)
ragbot compile --all-with-inheritance --output-repo ~/ai-knowledge/ai-knowledge-{output}

# Target specific LLM
ragbot compile --project {project} --llm claude

# Force recompilation (ignore cache)
ragbot compile --project {project} --force

# Verbose output
ragbot compile --project {project} --verbose
```

## Best Practices

1. **Use `--all-with-inheritance` for personal repos** — Compiles everything you need in one command

2. **Compile into shared repos for team use** — Others can use pre-compiled outputs without running the compiler

3. **Keep inheritance config in personal repo only** — Prevents leaking private repo references

4. **Check output before committing** — Verify no private content leaked into shared repos

## Troubleshooting

### "No my-projects.yaml found"

The inheritance config must exist in your personal repo. Create it with:

```yaml
version: 1
base_path: ~/projects/ai-knowledge
projects:
  # ... your projects
```

### "Repository not found"

Check that `local_path` in my-projects.yaml points to existing directories.

### Content not appearing in output

1. Check the inheritance chain in my-projects.yaml
2. Verify the source repo has content in `source/`
3. Check `compile-config.yaml` include/exclude patterns

## Further Reading

- [Data Organization Philosophy](./data-organization.md) — Why separate code from data
- [Repository Structure](./repository-structure.md) — Detailed structure documentation
