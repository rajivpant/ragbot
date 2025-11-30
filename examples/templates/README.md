# Ragbot Templates

## Purpose

These are **starter templates** designed to help you get Ragbot running quickly with your own personalized data.

## 🚨 Important: Templates Are Meant to Be COPIED

**Do NOT edit these templates in place!**

These templates live in the public Ragbot repository as examples. Your customizations should be done in YOUR location, not here.

### Correct Workflow

```bash
# ✅ Step 1: Copy templates OUT of ragbot/
cp -r examples/templates/datasets/starter/ datasets/my-data/

# ✅ Step 2: Edit in YOUR location with YOUR information
nano datasets/my-data/about-me.md

# ✅ Step 3: Use with Ragbot (via Docker or direct)
docker-compose up
```

### What NOT to Do

```bash
# ❌ Don't edit templates in place
nano examples/templates/datasets/starter/about-me.md  # WRONG!

# ❌ Don't put your personal data in ragbot/
nano datasets/my-personal-stuff/...  # Risky even though gitignored!
```

## Why This Matters

1. **Your privacy** - Personal data should never be in the public ragbot repository
2. **Clean updates** - You can pull latest Ragbot code without conflicts
3. **Easy backup** - Your data is separate, easy to backup independently
4. **Contributions** - If you improve templates, you can contribute anonymized versions back

See [docs/DATA_ORGANIZATION.md](../../docs/DATA_ORGANIZATION.md) for the philosophy behind this approach.

## What's Included

### 📋 Datasets Starter

**Location:** `datasets/starter/`

**Purpose:** Give Ragbot context about you

**Includes:**
- `about-me.md` - Personal background, interests, family
- `professional.md` - Work history, skills, current role
- `preferences.md` - Communication style, work habits

**When to use:** Personal AI assistant that knows about your life

**How to use:**
```bash
cp -r examples/templates/datasets/starter/ datasets/my-data/
# Edit files in datasets/my-data/ with your info
```

### ⚙️ Instructions Starter

**Location:** `instructions/starter/`

**Purpose:** Configure how Ragbot behaves and responds

**Includes:**
- `default-instructions.md` - Baseline AI behavior configuration

**When to use:** Setting up Ragbot's personality and response style

**How to use:**
```bash
cp examples/templates/instructions/starter/default-instructions.md instructions/
# Edit instructions/default-instructions.md with your preferences
```

### 🎭 Instructions Variations

**Location:** `instructions/variations/`

**Purpose:** Pre-configured instruction sets for specific roles

**Includes:**
- `creative-writer.md` - Writing coach and content creation assistant
- `technical-advisor.md` - Senior engineering advisor for code and architecture

**When to use:** Quick-start configurations for common scenarios

**How to use:**
```bash
# Use a variation as-is
cp examples/templates/instructions/variations/technical-advisor.md instructions/

# Or combine with your own modifications
cat examples/templates/instructions/variations/creative-writer.md >> instructions/my-instructions.md
```

## Recommended Setup Patterns

### Pattern 1: Quick Start (simplest)

Keep data directly in ragbot directory:

```
ragbot/
├── datasets/my-data/     # Your personal info (gitignored)
└── instructions/          # Your AI config (gitignored)
```

**Pros:** Simple, fast to set up
**Cons:** Harder to backup separately, easy to forget it's there

### Pattern 2: Separate Data Directory (recommended)

Keep data outside ragbot directory:

```
~/ragbot/                         # Public application
~/ragbot-data/                    # Your private data
├── datasets/
├── instructions/
└── prompt-library/
```

Connect via `docker-compose.override.yml`:
```yaml
volumes:
  - ~/ragbot-data/datasets:/app/datasets:ro
  - ~/ragbot-data/instructions:/app/instructions:ro
```

**Pros:** Clear separation, easy to backup, can use separate git repo
**Cons:** Slightly more setup

See [README-DOCKER.md](../../README-DOCKER.md) for Docker setup details.

## Use Case Examples

### Personal Life Assistant

```bash
# Copy starter template
cp -r examples/templates/datasets/starter/ datasets/personal/

# Add family info, schedule, preferences
nano datasets/personal/about-me.md

# Configure for helpful assistant
cp examples/templates/instructions/starter/default-instructions.md instructions/
```

**Good for:** Family coordination, personal productivity, life planning

### Work Project Companion

```bash
# Create project-specific data
mkdir datasets/work-project/

# Add project context
cat > datasets/work-project/project-overview.md <<EOF
# Project: [Name]
## Team: [Members]
## Goals: [Objectives]
EOF

# Use technical advisor instructions
cp examples/templates/instructions/variations/technical-advisor.md instructions/
```

**Good for:** Project tracking, technical problem-solving, documentation

### Content Creation Studio

```bash
# Copy starter for bio/background
cp -r examples/templates/datasets/starter/ datasets/creator/

# Add writing samples
mkdir datasets/creator/writing-samples/

# Use creative writer instructions
cp examples/templates/instructions/variations/creative-writer.md instructions/
```

**Good for:** Blog writing, social media, marketing content

## Contributing Templates

Have a great template configuration to share?

### ✅ What to Contribute

- Generic, anonymized templates
- Clear usage instructions
- Placeholder data only (no personal info!)
- Proven to work well

### ❌ What NOT to Contribute

- Templates with your personal information
- Company-specific or proprietary content
- Anything you wouldn't want public

### How to Contribute

1. Create anonymized template in temp location
2. Use placeholders: `[Your Name]`, `[Company]`, etc.
3. Add clear README explaining the template
4. Read [CONTRIBUTING.md](../../CONTRIBUTING.md) for safety guidelines
5. Submit pull request

Example anonymized template:
```markdown
# About Me Template

Name: [Your Full Name]
Location: [City, State/Country]
Occupation: [Your Job Title]

## Background
[Write a paragraph about yourself...]
```

## Privacy and Security

### What Stays Local

Everything you put in your datasets and instructions stays on your machine:
- ✅ Not committed to git (these directories are .gitignored)
- ✅ Not uploaded anywhere (except to AI API when you use Ragbot)
- ✅ Under your control

### What Gets Sent to AI

When you use Ragbot:
- Your datasets are included in prompts sent to the AI service (OpenAI, Anthropic, etc.)
- Make sure you're comfortable with this information being processed by the AI provider

### Best Practices

1. **Keep truly sensitive data out** - Passwords, SSNs, financial details should NOT be in datasets
2. **Use separate data repo** - Consider keeping your data in `~/ragbot-data/` as a private git repo
3. **Review regularly** - Periodically audit what's in your datasets
4. **Don't commit personal data** - The ragbot directory is public, your data should never be here

## Troubleshooting

**Q: I edited the template in place and want to reset it**

Pull fresh copy from main branch:
```bash
cd ~/ragbot
git checkout main -- examples/templates/
```

**Q: My personal data showed up in git status**

This shouldn't happen (datasets/ and instructions/ are gitignored). If it does:
```bash
# Remove from staging
git reset HEAD datasets/ instructions/

# Make sure .gitignore is correct
cat .gitignore | grep datasets
# Should show: /datasets
```

**Q: Where should I keep my data for production use?**

Best practice: Separate directory or private repo
```bash
mkdir ~/ragbot-data
# Or: git clone your-private-repo ~/ragbot-data
```

Then use `docker-compose.override.yml` to mount it. See [README-DOCKER.md](../../README-DOCKER.md).

## Next Steps

1. **Copy templates** to your working directory
2. **Customize with your info** in your location (not here!)
3. **Run Ragbot** via `docker-compose up` or directly
4. **Explore the library** - See [../library/](../library/) for advanced prompts and techniques

---

**Remember: Copy these templates OUT, customize externally, never commit personal data!**
