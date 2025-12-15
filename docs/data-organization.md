# Data Organization Philosophy

## Why Ragbot Separates Code from Data

Ragbot follows a fundamental principle in software engineering: **separation of concerns**. Your personal data should never be mixed with application code. This isn't just a best practice—it's essential for privacy, security, and flexibility.

## The AI Knowledge Architecture

Ragbot uses a multi-repository architecture where each context (personal, company, client) has its own repository:

```
ragbot/                          # Application code (public)
├── src/ragbot/                  # Core library
├── web/                         # React frontend
└── api/                         # FastAPI backend

ai-knowledge-{name}/             # Content repositories (private)
├── source/                      # Human-edited content
│   ├── instructions/            # WHO - identity and persona
│   ├── runbooks/                # HOW - task procedures
│   └── datasets/                # WHAT - reference knowledge
├── compiled/                    # AI-optimized output (auto-generated)
│   └── {project}/
│       ├── instructions/        # LLM-specific instructions
│       ├── knowledge/           # Compiled knowledge files
│       └── vectors/             # RAG chunks
└── compile-config.yaml          # Compilation settings
```

## The WHO/HOW/WHAT Framework

AI knowledge is organized into three conceptual categories:

| Folder | Purpose | Question Answered |
|--------|---------|-------------------|
| `instructions/` | Identity and persona | **WHO** is the agent? |
| `runbooks/` | Task procedures | **HOW** does the agent do things? |
| `datasets/` | Reference knowledge | **WHAT** does the agent know? |

### instructions/ — WHO

System-level behavioral guidance that defines the agent's identity:
- Communication style and tone
- Core principles and values
- Response preferences

### runbooks/ — HOW

Task-specific procedures for autonomous AI execution:
- Content creation guidelines
- Automation workflows
- Prompting techniques

### datasets/ — WHAT

Reference knowledge organized by category:
- Personal information
- Professional background
- Domain expertise

## Repository Inheritance

AI Knowledge repos follow a hierarchy with inheritance:

```
ai-knowledge-{templates}     ← Public templates (root)
    ↓
ai-knowledge-{person}        ← Personal identity
    ↓
ai-knowledge-{company}       ← Company knowledge
    ↓
ai-knowledge-{client}        ← Client-specific content
```

Each child repo inherits content from its parent. This enables:
- **Layered identity**: Personal context + company context + client context
- **Privacy control**: Each repo only contains content appropriate for its access level
- **Flexible compilation**: Compile with or without inheritance

## The Philosophy

### Think of Ragbot Like Your Operating System

Just as your operating system (macOS, Linux, Windows) separates:
- **System files** (the OS itself) from **user files** (your documents)
- **Applications** (software) from **data** (what you create)
- **Configuration** (settings) from **secrets** (passwords)

Ragbot separates:
- **Application code** (`ragbot/`) from **your knowledge** (`ai-knowledge-*/`)
- **The AI engine** from **your context and identity**
- **Generic examples** from **personal information**

### Real-World Analogies

**The Library Analogy:**
- Ragbot is the librarian (constant, helpful, knowledgeable about systems)
- Your ai-knowledge repos are the books on the shelves (your unique knowledge)
- Instructions are how you want the librarian to help you (your preferences)

**The Assistant Analogy:**
- Ragbot is your assistant (the person with skills and tools)
- Your ai-knowledge content is the briefing materials (context about your life/work)
- Instructions are the working relationship (how you collaborate)

## Benefits of This Approach

### 1. Privacy and Security

**What stays private:**
- Your personal information (in private ai-knowledge repos)
- Work/client data (in separate repos per client)
- Your AI instructions (your "secret sauce")

**What's public:**
- The application code (open source)
- Generic examples and templates
- Prompting techniques and frameworks

### 2. Flexibility

**Multiple Contexts:**
- Personal repo for personal use
- Company repo for work projects
- Client repos for client-specific work
- Each compiled independently or with inheritance

**Version Control:**
- Update Ragbot code without affecting your knowledge
- Rollback knowledge changes independently
- Branch knowledge for experiments
- Share repos selectively

### 3. Portability

**Your knowledge travels with you:**
- Same repos work on any machine
- Easy backup (git push to remote)
- Migrate to new machine (git clone)
- Share setup without sharing content

### 4. Collaboration

**You can share:**
- The application (public ragbot repo)
- Generic templates (examples directory)
- Anonymized techniques

**You keep private:**
- Personal data
- Client information
- Your customizations

## Comparison with Other Approaches

### Approach 1: Everything in One Repo

```
ragbot/
├── src/
├── my-personal-data/    # DANGER: Easy to accidentally commit
├── my-instructions/
└── client-secrets/      # DANGER: Might leak
```

**Problems:**
- High risk of committing sensitive data
- Can't share code without exposing data
- One .gitignore mistake = privacy breach

### Approach 2: Application Only (Generic AI)

```
ragbot/
└── src/    # No customization capability
```

**Problems:**
- AI has no context about you
- Repeat yourself in every conversation
- Generic, not personalized responses

### Approach 3: Multi-Repo Architecture (Ragbot's Approach)

```
ragbot/ (public)                ai-knowledge-*/ (private)
├── src/                        ├── source/
├── web/                        │   ├── instructions/
├── api/                        │   ├── runbooks/
└── examples/                   │   └── datasets/
                                ├── compiled/
                                └── compile-config.yaml
```

**Benefits:**
- Clear separation of concerns
- Privacy by design
- Flexible inheritance model
- Easy to share application, not data

## Implementation Guide

### For New Users

**Quick Start:**
```bash
# 1. Clone Ragbot
git clone https://github.com/rajivpant/ragbot.git
cd ragbot
pip install -e .

# 2. Create your personal ai-knowledge repo
mkdir -p ~/ai-knowledge/ai-knowledge-personal
cd ~/ai-knowledge/ai-knowledge-personal
mkdir -p source/instructions source/runbooks source/datasets

# 3. Add your content
# Edit files in source/

# 4. Compile
ragbot compile --repo ~/ai-knowledge/ai-knowledge-personal

# 5. Chat
ragbot chat --workspace personal
```

### For Advanced Users

**Multiple Contexts with Inheritance:**
```yaml
# my-projects.yaml in your personal repo
version: 1
projects:
  personal:
    local_path: ~/ai-knowledge/ai-knowledge-personal
    inherits_from: []

  company:
    local_path: ~/ai-knowledge/ai-knowledge-company
    inherits_from:
      - personal

  client-a:
    local_path: ~/ai-knowledge/ai-knowledge-client-a
    inherits_from:
      - company
```

**Compile with inheritance:**
```bash
ragbot compile --project client-a --with-inheritance
```

## Best Practices

### DO

1. **Keep repos separate** - One repo per context (personal, company, client)

2. **Use inheritance wisely** - Personal → Company → Client hierarchy

3. **Version control your knowledge** - Git provides history and backup

4. **Use the WHO/HOW/WHAT structure**
   ```
   source/
   ├── instructions/       # WHO
   ├── runbooks/           # HOW
   └── datasets/           # WHAT
   ```

5. **Compile before use** - Generate optimized output for each LLM

### DON'T

1. **Don't commit secrets** - No API keys in content files

2. **Don't mix public and private** - Keep ragbot/ and ai-knowledge-*/ separate

3. **Don't skip compilation** - Compiled output is optimized for LLMs

## Summary

Ragbot's separation of code and data follows proven patterns from:
- Unix dotfiles
- Infrastructure as Code
- Twelve-Factor App methodology
- Security best practices

**The result:**
- Privacy by design
- Flexibility for multiple contexts
- Inheritance for layered identity
- Easy to update and maintain

**Bottom line:** Your knowledge is yours. The application is shared. This separation keeps both better.

---

## Further Reading

- [Compilation Guide](./compilation-guide.md) - How the compiler works
- [Project Documentation Convention](./conventions/project-documentation.md) - Project folder structure
- [The Twelve-Factor App](https://12factor.net/) - Configuration principles
