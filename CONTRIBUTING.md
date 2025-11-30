# Contributing to Ragbot

Thank you for your interest in contributing to Ragbot! This guide will help you contribute safely while protecting your privacy.

## 🚨 CRITICAL: Never Commit Personal Data

**Ragbot is PUBLIC.** Your personal data should **NEVER** be in this repository.

### What NOT to Commit

❌ **Personal information** - Names, addresses, phone numbers, emails
❌ **Work/client data** - Company information, client names, project details
❌ **Customized templates** - Templates filled with YOUR information
❌ **API keys, passwords, secrets** - Any authentication credentials
❌ **Files from datasets/** - These are gitignored for a reason!
❌ **Files from instructions/** - These contain your preferences
❌ **Anything specific to you** - Dates, locations, personal history

### What TO Contribute

✅ **Generic, anonymized templates** - Starter files with placeholders
✅ **Reusable prompts** - Techniques without personal references
✅ **Documentation improvements** - Clarifications, examples, guides
✅ **Bug fixes and features** - Code improvements
✅ **Examples with placeholder data** - `[Your Name]`, `[Company]`, etc.

## How to Contribute

### Step 1: Work Externally

**IMPORTANT:** Your customizations should live OUTSIDE this repository.

```bash
# ✅ GOOD: Your data is separate
~/ragbot/              # Public repo - only code and examples
~/ragbot-data/         # Private location - your personal data

# ❌ BAD: Don't do this
~/ragbot/datasets/my-stuff/  # Risky even though gitignored!
```

### Step 2: Choose Your Contribution Type

#### A. Code Contributions (Bug Fixes, Features)

Standard GitHub workflow:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests if applicable
5. Submit pull request

No special privacy concerns here - you're not touching data files.

#### B. Template Contributions

Contributing a new starter template:

1. **Create in a temp location** (NOT in ragbot/ or your ragbot-data/)
   ```bash
   mkdir /tmp/new-template
   cd /tmp/new-template
   ```

2. **Use placeholders for ALL personal data**
   ```markdown
   # ❌ BAD (contains personal info)
   Name: John Smith
   Email: john@company.com
   Location: San Francisco, CA

   # ✅ GOOD (uses placeholders)
   Name: [Your Full Name]
   Email: [your.email@example.com]
   Location: [City, State/Country]
   ```

3. **Test your template**
   - Verify it works as a starting point
   - Ensure all placeholders are clear
   - Check that instructions are complete

4. **Submit PR**
   - Add to `examples/templates/` directory
   - Include README with usage instructions
   - Describe what the template is for

#### C. Library Resource Contributions (Prompts, Frameworks)

Contributing a prompt or technique you've developed:

1. **Copy to temp location first**
   ```bash
   # DON'T work directly - use temp for anonymization
   cp ~/ragbot-data/my-prompts/great-technique.md /tmp/contribution.md
   ```

2. **Anonymize thoroughly**

   Check for and remove:
   - [ ] Personal names (yours, family, colleagues)
   - [ ] Company names (current, past, clients)
   - [ ] Specific dates that could identify you
   - [ ] Email addresses and phone numbers
   - [ ] Physical addresses
   - [ ] Project names (internal projects)
   - [ ] Proprietary methodologies or "secret sauce"
   - [ ] Any information you wouldn't want public

   Replace with:
   - Generic placeholders: `[Your Name]`, `[Company]`, `[Project]`
   - Broad categories: "tech company" not "Acme Corp"
   - General timeframes: "Q1 2024" not "January 15, 2024"

3. **Add documentation**

   Your contribution should include:

   ```markdown
   # [Technique/Prompt Name]

   ## Purpose
   Brief description of what this solves

   ## When to Use
   - Specific use case 1
   - Specific use case 2
   - When NOT to use this

   ## How to Use
   1. Step-by-step instructions
   2. Where to place this (datasets? instructions?)
   3. How to customize for your needs

   ## Example
   (Show before/after or sample usage - with placeholder data!)

   ## Notes
   Any prerequisites, tips, or gotchas
   ```

4. **Pre-submission checklist**

   Before submitting, verify:

   - [ ] File contains NO personal information
   - [ ] All examples use placeholder data (`[Name]`, `[Company]`, etc.)
   - [ ] Documentation is clear and complete
   - [ ] File is in the correct directory:
     - `examples/library/prompts/engineering/` - Prompting techniques
     - `examples/library/prompts/ai-configuration/` - AI configs
     - `examples/library/prompts/communication/` - Frameworks
     - `examples/library/content-templates/` - Content templates
   - [ ] I've read this entire CONTRIBUTING.md file
   - [ ] I'm comfortable with this being public forever

5. **Submit PR**

   ```bash
   # Fork ragbot on GitHub, then:
   git clone https://github.com/YOUR-USERNAME/ragbot.git
   cd ragbot
   git checkout -b add-my-technique

   # Add your anonymized contribution
   cp /tmp/contribution.md examples/library/prompts/engineering/

   # Commit and push
   git add examples/library/prompts/engineering/contribution.md
   git commit -m "Add [technique name]

   Brief description of what this technique does and when to use it."
   git push origin add-my-technique

   # Then create PR on GitHub
   ```

## Common Mistakes to Avoid

### ❌ Mistake 1: Insufficient Anonymization

```markdown
# BAD: Too specific, identifies you
I developed this at TechCorp when we launched our Q2 product.
My manager Sarah said it increased engagement by 50%.

# GOOD: Generic and reusable
This technique works well for product launches.
Teams have reported significant engagement improvements.
```

### ❌ Mistake 2: Working in the Wrong Location

```bash
# BAD: Working directly with your personal data
cd ~/ragbot-data/
# ... make changes ...
git add .  # DANGER! Personal data might leak!

# GOOD: Work in temp, anonymize, then copy to ragbot
cp ~/ragbot-data/my-file.md /tmp/anonymized.md
# Edit /tmp/anonymized.md thoroughly
# Review multiple times
# THEN copy to ~/ragbot/examples/
```

### ❌ Mistake 3: No Documentation

```markdown
# BAD: Just code/prompt with no context
[Long technical prompt with no explanation]

# GOOD: Clear documentation
# Sales Email Template

## Purpose
Helps sales teams write personalized outreach emails...

## When to Use
- Initial contact with prospects
- Follow-up after demos
...
```

### ❌ Mistake 4: Contributing Your Personal Templates

```bash
# BAD: Your filled-in template
~/ragbot-data/datasets/my-info/about-me.md
# This has YOUR info! Never contribute this!

# GOOD: A new anonymized template
/tmp/new-template/about-me-template.md
# This has placeholders, safe to contribute
```

## Safety Features

Ragbot has multiple layers of protection:

1. **`.gitignore`** - Blocks `datasets/`, `instructions/`, etc.
2. **Separate repo pattern** - Recommended workflow keeps data external
3. **Docker override** - Your data paths in `docker-compose.override.yml` (gitignored)
4. **This guide** - Clear instructions on what NOT to commit

## Review Process

When you submit a PR:

1. **Automated checks** - CI/CD linting and validation
2. **Maintainer review** - Checks for personal data and quality
3. **Community feedback** - Other contributors may suggest improvements
4. **Merge** - Once approved, becomes part of Ragbot!

## Questions?

**Not sure if something is safe to contribute?**
→ Open a GitHub issue and ask! We'll help you.

**Found personal data in existing examples?**
→ Open a private security advisory immediately.

**Want to contribute but worried about privacy?**
→ Better safe than sorry - ask first in an issue.

## Remember

### When in doubt, leave it out.

It's better to:
- Ask questions
- Not contribute
- Over-anonymize

Than to accidentally expose personal information.

**Your privacy > any contribution**

## Additional Resources

- [Contribution Workflow Guide](docs/CONTRIBUTION_WORKFLOW.md) - Detailed process
- [Data Organization Philosophy](docs/DATA_ORGANIZATION.md) - Why we separate code from data
- [Examples README](examples/README.md) - How to use templates and library

## Code of Conduct

Be respectful, be helpful, be kind. We're all here to make Ragbot better for everyone.

## License

By contributing, you agree that your contributions will be licensed under the same license as Ragbot.

---

**Thank you for helping make Ragbot better while keeping everyone's data safe!** 🙏
