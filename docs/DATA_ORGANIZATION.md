# Data Organization Philosophy

## Why Ragbot Separates Code from Data

Ragbot follows a fundamental principle in software engineering: **separation of concerns**. Your personal data should never be mixed with application code. This isn't just a best practice—it's essential for privacy, security, and flexibility.

## The WHO/HOW/WHAT/WHERE Framework

Ragbot organizes AI knowledge into four conceptual categories:

| Folder | Purpose | Question Answered |
|--------|---------|-------------------|
| `instructions/` | Identity and persona | **WHO** is the agent? |
| `runbooks/` | Task procedures | **HOW** does the agent do things? |
| `datasets/` | Reference knowledge | **WHAT** does the agent know? |
| `workspaces/` | Context overlays | **WHERE** is the agent working? |

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

### workspaces/ — WHERE

Context overlays for different organizational contexts:
- Companies you work with
- Products you're building
- Client engagements

## The Philosophy

### Think of Ragbot Like Your Operating System

Just as your operating system (macOS, Linux, Windows) separates:
- **System files** (the OS itself) from **user files** (your documents)
- **Applications** (software) from **data** (what you create)
- **Configuration** (settings) from **secrets** (passwords)

Ragbot separates:
- **Application code** (`ragbot/`) from **your data** (`ragbot-data/`)
- **The AI engine** from **your context and knowledge**
- **Generic examples** from **personal information**

### Real-World Analogies

**The Library Analogy:**
- Ragbot is the librarian (constant, helpful, knowledgeable about systems)
- Your datasets are the books on the shelves (your unique knowledge)
- Instructions are how you want the librarian to help you (your preferences)

**The Assistant Analogy:**
- Ragbot is your assistant (the person with skills and tools)
- Your data is the briefing materials (context about your life/work)
- Instructions are the working relationship (how you collaborate)

## How Ragbot Implements Separation

### The Two-Repository Pattern

```
ragbot/ (public GitHub)
├── src/                    # Application code
├── docker-compose.yml      # Base configuration
├── examples/               # Generic templates
├── datasets/               # Empty (gitignored)
└── instructions/           # Empty (gitignored)

ragbot-data/ (private - yours or private GitHub)
├── instructions/           # WHO - your identity/persona
├── runbooks/               # HOW - your procedures
├── datasets/               # WHAT - your knowledge
└── workspaces/             # WHERE - your contexts
```

### How They Connect

**Via Docker Volumes** (recommended):
```yaml
# docker-compose.override.yml (gitignored, on your machine only)
volumes:
  - /path/to/your/ragbot-data/datasets:/app/datasets:ro
  - /path/to/your/ragbot-data/instructions:/app/instructions:ro
```

**Via Symlinks** (simple alternative):
```bash
ln -s /path/to/your/ragbot-data/datasets ./datasets
ln -s /path/to/your/ragbot-data/instructions ./instructions
```

## Workspaces: Context Overlays

Workspaces allow you to organize knowledge by context (companies, products, clients) with inheritance relationships.

### Workspace Structure

```
workspaces/
├── acme-corp/
│   ├── workspace.yaml      # Configuration and inheritance
│   ├── datasets/           # Company-specific knowledge
│   ├── runbooks/           # Company-specific procedures
│   └── instructions.md     # Company-specific identity tweaks
├── side-project/
│   ├── workspace.yaml
│   └── datasets/
└── client-engagement/
    ├── workspace.yaml
    └── datasets/
```

### workspace.yaml Schema

```yaml
name: Acme Corp
description: Enterprise client engagement
status: active              # active | completed | archived
type: company               # company | engagement | product | personal

# Inherit from other workspaces
inherits_from:
  - parent-workspace

# Include content from root folders
include_from_root:
  - runbooks/voice-and-style/
  - datasets/professional-public/
```

### Why Workspaces?

**Flexible relationships:** A client engagement can inherit from a parent company without being nested inside it.

**Easy reconfiguration:** When relationships change, edit YAML instead of moving folders.

**Future multi-user support:** Each user could have their own root identity with shared workspaces.

**Selective sync:** Sync only relevant workspaces to different machines.

## Benefits of This Approach

### 1. Privacy and Security

**What stays private:**
- Your personal information (family, contacts, preferences)
- Work/client data (projects, confidential information)
- Your AI instructions (your "secret sauce")

**What's public:**
- The application code (open source)
- Generic examples and templates
- Prompting techniques and frameworks

### 2. Flexibility

**Multiple Contexts:**
```bash
# Personal life
docker-compose.override.yml → ~/ragbot-data-personal/

# Work projects
docker-compose.override.yml → ~/ragbot-data-work/

# Client A
docker-compose.override.yml → ~/client-a-ragbot-data/
```

**Version Control:**
- Update Ragbot code without affecting your data
- Rollback data changes independently
- Branch data for experiments
- Share data selectively (anonymized versions)

### 3. Portability

**Your data travels with you:**
- Same data works on laptop, desktop, server
- Easy backup (just your data repository)
- Migrate to new machine (clone both repos)
- Share setup without sharing data

### 4. Collaboration

**You can share:**
- The application (public ragbot repo)
- Generic prompts (examples directory)
- Anonymized templates (datasets without personal info)

**You keep private:**
- Personal data
- Client information
- Your instructions
- Your personal runbooks

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
- Difficult to manage multiple contexts

### Approach 2: Application Only (Generic AI)

```
ragbot/
└── src/    # No customization capability
```

**Problems:**
- AI has no context about you
- Repeat yourself in every conversation
- Generic, not personalized responses
- No way to organize knowledge

### Approach 3: Separate Repos (Ragbot's Approach)

```
ragbot/ (public)           ragbot-data/ (private)
├── src/                   ├── instructions/
├── examples/              ├── runbooks/
└── docs/                  ├── datasets/
                           └── workspaces/
```

**Benefits:**
- Clear separation of concerns
- Privacy by design
- Flexible and portable
- Easy to share application, not data

## Best Practices

### DO

1. **Use .gitignore aggressively**
   ```gitignore
   datasets/
   instructions/
   runbooks/
   workspaces/
   profiles.yaml
   docker-compose.override.yml
   .env
   ```

2. **Separate public and private**
   - Public: Code, examples, documentation
   - Private: Your data, your configs, your secrets

3. **Version control your data separately**
   ```bash
   cd ~/ragbot-data
   git init
   git remote add origin git@github.com:yourname/ragbot-data-private.git
   ```

4. **Use the WHO/HOW/WHAT/WHERE structure**
   ```
   ragbot-data/
   ├── instructions/       # WHO
   ├── runbooks/           # HOW
   ├── datasets/           # WHAT
   │   ├── personal/
   │   └── professional/
   └── workspaces/         # WHERE
       ├── work-project/
       └── side-project/
   ```

5. **Regular backups**
   - Your data is valuable
   - Git provides version history
   - Consider encrypted backups for extra sensitive data

### DON'T

1. **Don't commit secrets**
   - No API keys in code
   - No passwords in data files
   - No client confidential information in public repos

2. **Don't mix concerns**
   - Keep code and data separate
   - Don't hardcode paths to your data
   - Don't put examples in your data repo

3. **Don't skip .gitignore**
   - Always check what's being committed
   - Use `git status` before `git add`
   - Review diffs before pushing

## Implementation Guide

### For New Users

**Quick Start (5 minutes):**
```bash
# 1. Clone Ragbot
git clone https://github.com/rajivpant/ragbot.git
cd ragbot

# 2. Copy examples
cp -r examples/templates/datasets/starter/ datasets/my-data/
cp examples/templates/instructions/starter/default-instructions.md instructions/

# 3. Edit with your info
# Edit files in datasets/my-data/

# 4. Run
docker-compose up
```

**Production Setup (separate data repo):**
```bash
# 1. Create your data repository
mkdir ~/ragbot-data
cd ~/ragbot-data
git init

# 2. Organize your data using WHO/HOW/WHAT/WHERE
mkdir instructions runbooks datasets workspaces

# 3. Add content
cp ~/ragbot/examples/templates/datasets/starter/* datasets/

# 4. Configure Ragbot to use it
cd ~/ragbot
cp docker-compose.override.example.yml docker-compose.override.yml
# Edit docker-compose.override.yml to point to ~/ragbot-data

# 5. Run
docker-compose up
```

### For Advanced Users

**Multiple Environments:**
```bash
# Create environment-specific overrides
# docker-compose.override.personal.yml
# docker-compose.override.work.yml
# docker-compose.override.client-a.yml

# Switch between them
cp docker-compose.override.personal.yml docker-compose.override.yml
docker-compose restart
```

**Encrypted Secrets:**
```bash
# Use git-crypt or similar for sensitive files
cd ~/ragbot-data
git-crypt init
git-crypt add .gitattributes
# Add pattern: "sensitive-data/* filter=git-crypt diff=git-crypt"
```

## The Future: Community and Sharing

### What Gets Shared

As the Ragbot community grows, this separation enables:

**Shareable (in ragbot/examples/):**
- Prompting techniques
- AI configuration patterns
- Content templates
- Use case examples (anonymized)

**Private (in your ragbot-data/):**
- Personal information
- Client work
- Proprietary runbooks
- Sensitive configurations

### Contributing Back

Have a great runbook or template? Share it!

```bash
# 1. Copy from your private repo (anonymize first!)
cp ~/ragbot-data/runbooks/my-great-technique.md ~/ragbot/examples/templates/runbooks/

# 2. Remove personal references
# Edit: Replace personal names with "[Your Name]", etc.

# 3. Submit to public repo
cd ~/ragbot
git add examples/templates/runbooks/my-great-technique.md
git commit -m "Add runbook: [description]"
# Create pull request
```

## Summary

Ragbot's separation of code and data follows proven patterns from:
- Unix dotfiles
- Infrastructure as Code
- Twelve-Factor App methodology
- Security best practices

**The result:**
- Privacy by design
- Flexibility for multiple contexts
- Easy to update and maintain
- Share knowledge without sharing data
- Professional-grade organization

**Bottom line:** Your data is yours. The application is shared. This separation keeps both better.

---

## Further Reading

- [The Twelve-Factor App](https://12factor.net/) - Configuration principles
- [Managing Dotfiles](https://dotfiles.github.io/) - Configuration management patterns
- [Infrastructure as Code Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)
- [Git Best Practices](https://sethrobertson.github.io/GitBestPractices/)

## Questions?

See [examples/README.md](../examples/README.md) for practical guidance, or check the [main README](../README.md) for quick start instructions.
