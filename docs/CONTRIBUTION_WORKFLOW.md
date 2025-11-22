# Contribution Workflow Guide

This detailed guide explains how to safely contribute improvements back to Ragbot while protecting your personal data.

## Table of Contents

- [The Core Principle](#the-core-principle)
- [Three Types of Contributions](#three-types-of-contributions)
- [Detailed Workflows](#detailed-workflows)
- [Common Mistakes](#common-mistakes)
- [Review Process](#review-process)

## The Core Principle: Separation

Ragbot follows strict separation between public code and private data:

```
┌─────────────────────────────┐    ┌─────────────────────────────┐
│  ragbot/ (PUBLIC)           │    │  ragbot-data/ (PRIVATE)     │
│  ├── Application code       │    │  ├── Your personal info     │
│  ├── Documentation          │    │  ├── Your customizations    │
│  ├── Generic examples       │    │  ├── Your prompts           │
│  └── Anonymous templates    │    │  └── Your work data         │
└─────────────────────────────┘    └─────────────────────────────┘
         ↓ Contribute                        ↓ NEVER commit
   Code & anonymous examples              Personal data stays here
```

**Golden Rule:** Code and generic examples go in `ragbot/`. Your personal data stays in `ragbot-data/` (or `curated-datasets/`).

## Three Types of Contributions

### 1. Code Contributions
**What:** Bug fixes, features, improvements to the application
**Risk Level:** 🟢 Low (no personal data involved)
**Workflow:** Standard GitHub pull request

### 2. Template Contributions
**What:** New starter templates for getting started
**Risk Level:** 🟡 Medium (must use placeholders only)
**Workflow:** Create anonymously, then contribute

### 3. Library Resource Contributions
**What:** Prompts, frameworks, techniques you've developed
**Risk Level:** 🔴 High (easy to leak personal info)
**Workflow:** Copy → Anonymize → Document → Contribute

---

## Detailed Workflows

### Workflow 1: Code Contributions (Standard)

This is the standard open source contribution flow.

**Prerequisites:**
- GitHub account
- Git installed
- Understanding of the codebase

**Steps:**

1. **Fork the repository** on GitHub

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR-USERNAME/ragbot.git
   cd ragbot
   ```

3. **Create a feature branch**
   ```bash
   git checkout -b fix-bug-description
   # or
   git checkout -b feature-new-capability
   ```

4. **Make your changes**
   - Edit code files
   - Write tests if applicable
   - Update documentation if needed

5. **Test locally**
   ```bash
   # For Python changes
   pytest

   # For Docker changes
   docker-compose build
   docker-compose up -d
   ```

6. **Commit your changes**
   ```bash
   git add [files]
   git commit -m "Fix: [description of fix]"
   # or
   git commit -m "Feature: [description of feature]"
   ```

7. **Push to your fork**
   ```bash
   git push origin fix-bug-description
   ```

8. **Create pull request** on GitHub
   - Go to your fork on GitHub
   - Click "Pull Request"
   - Fill in description
   - Submit

**Safety Note:** Since you're only touching code files (`.py`, `.yml`, etc.), there's minimal risk of exposing personal data. Just make sure you're not committing `.env` files or similar!

---

### Workflow 2: Template Contributions

Contributing a new starter template (e.g., a new use case template).

**Example:** You've created a great template for "Fitness Coach" use case and want to share it.

**Steps:**

1. **Create in a TEMP location** (NOT in ragbot/ or ragbot-data/)

   ```bash
   mkdir /tmp/fitness-coach-template
   cd /tmp/fitness-coach-template
   ```

2. **Create template files with placeholders**

   **Good template (about-fitness.md):**
   ```markdown
   # Fitness Profile

   ## Personal Info
   - Name: [Your Name]
   - Age: [Your Age]
   - Current Weight: [Your Weight]
   - Goal Weight: [Target Weight]

   ## Fitness Goals
   [List your fitness goals here]

   ## Exercise Preferences
   [What types of exercise do you enjoy?]
   ```

   **Bad template:**
   ```markdown
   # Fitness Profile
   Name: John Smith
   Age: 35
   Current Weight: 180 lbs
   ```

3. **Add README explaining the template**

   ```markdown
   # Fitness Coach Template

   ## Purpose
   This template configures Ragbot as a personal fitness coach.

   ## How to Use
   1. Copy this template to your curated-datasets:
      `cp -r fitness-coach/ ~/ragbot-data/curated-datasets/`
   2. Fill in your personal fitness information
   3. Use with custom instructions for coaching mode

   ## What to Include
   - Current fitness level
   - Goals (weight loss, muscle gain, endurance)
   - Dietary preferences and restrictions
   - Exercise preferences
   - Schedule and time availability
   ```

4. **Test the template**
   - Copy it to a test location
   - Fill it in with sample data
   - Run Ragbot with it
   - Verify it works as intended

5. **Submit PR**
   ```bash
   cd ~/ragbot
   git checkout -b add-fitness-coach-template

   # Copy template to appropriate location
   cp -r /tmp/fitness-coach-template examples/templates/curated-datasets/fitness-coach/

   git add examples/templates/curated-datasets/fitness-coach/
   git commit -m "Add Fitness Coach template

   This template helps users configure Ragbot as a personal fitness coach.

   Includes:
   - Fitness profile template
   - Exercise preference tracking
   - Goal setting structure
   - Usage instructions"

   git push origin add-fitness-coach-template
   ```

6. **Create PR on GitHub** with clear description of what the template is for

---

### Workflow 3: Library Resource Contributions (Most Common)

This is for contributing prompts, techniques, or frameworks you've developed and want to share.

**Example:** You've created an amazing prompt for "Meeting Minutes Summarization" and want to contribute it.

#### Phase 1: Preparation

1. **Identify what to share**

   You have this file in your private data:
   ```
   ~/ragbot-data/prompts/meeting-summary-prompt.md
   ```

   It works great and could help others!

2. **Create working copy in temp location**

   ```bash
   # IMPORTANT: Don't work directly in ragbot/!
   cp ~/ragbot-data/prompts/meeting-summary-prompt.md /tmp/contribution.md
   ```

#### Phase 2: Anonymization (CRITICAL)

3. **Open `/tmp/contribution.md` and anonymize thoroughly**

   **Check for and remove:**

   - [ ] **Names** - Yours, colleagues, clients
     - ❌ "I use this at Acme Corp for our weekly team meetings"
     - ✅ "This works well for weekly team meetings"

   - [ ] **Companies** - Current, past, clients
     - ❌ "We used this when working with BigCo on the Q2 launch"
     - ✅ "Useful for product launch planning meetings"

   - [ ] **Specific dates**
     - ❌ "Created on January 15, 2024 for the product review"
     - ✅ "Useful for quarterly product reviews"

   - [ ] **Email addresses**
     - ❌ "Send summary to john.smith@company.com and team@company.com"
     - ✅ "Send summary to [relevant stakeholders]"

   - [ ] **Phone numbers, addresses**
     - Remove all contact information

   - [ ] **Project names** (internal codenames)
     - ❌ "Project Phoenix Q4 Deliverables"
     - ✅ "Project deliverables and milestones"

   - [ ] **Specific numbers** (revenue, metrics that could identify company)
     - ❌ "Helped us grow from $1M to $5M ARR"
     - ✅ "Can help track growth metrics"

   - [ ] **Screenshots or embedded data**
     - Remove any images with company logos, real data

   **Replace with placeholders:**

   ```markdown
   # Before (has personal info)
   Ask Claude to summarize the meeting notes from our weekly sync.
   Attendees were Sarah (PM), John (Eng), and me (Design).
   Focus on action items assigned to the engineering team.

   # After (anonymized)
   Ask Claude to summarize meeting notes.
   Participants: [Participant 1 - Role], [Participant 2 - Role], etc.
   Focus on action items assigned to [specific team or person].
   ```

4. **Review multiple times**

   - Read through completely
   - Ask yourself: "If my name wasn't on this, could it identify me?"
   - Check for subtle identifiers (writing style is fine, but specific facts aren't)
   - When in doubt, remove it

#### Phase 3: Documentation

5. **Add comprehensive documentation**

   Transform your prompt into a well-documented resource:

   ```markdown
   # Meeting Minutes Summarization Prompt

   ## Purpose

   This prompt helps you generate concise, actionable meeting summaries from
   rough notes or transcripts.

   ## When to Use

   - After team meetings, client calls, or planning sessions
   - When you have messy notes and need a clean summary
   - To extract action items and decisions from long discussions

   ## When NOT to Use

   - For confidential or sensitive meetings (make sure your notes are safe to process)
   - When you need verbatim transcripts rather than summaries

   ## How to Use

   ### Step 1: Prepare Your Notes

   Copy your meeting notes into a file or prepare to paste them.

   ### Step 2: Use This Prompt

   [Insert your actual prompt here]

   Example:
   ```
   Please summarize the following meeting notes into:
   1. Key decisions made
   2. Action items with owners
   3. Open questions or blockers
   4. Next steps

   Meeting Notes:
   [Paste your notes here]
   ```

   ### Step 3: Review and Customize

   The AI will generate a summary. Review it for accuracy and add any context
   that the AI might have missed.

   ## Customization Ideas

   - Add specific sections your team needs (risks, dependencies, etc.)
   - Include formatting preferences (bullet points, tables, etc.)
   - Specify output length (brief, detailed, executive summary)

   ## Example Input

   ```
   Meeting: Product Planning Discussion
   Date: [Date]
   Attendees: [List]

   - Discussed new feature ideas
   - Team raised concerns about timeline
   - Decided to prototype option B first
   - Need to schedule follow-up with design team
   ```

   ## Example Output

   ```
   **Key Decisions:**
   - Will prototype option B before full implementation

   **Action Items:**
   - [Person A]: Schedule design review by [date]
   - [Person B]: Create technical spec for option B

   **Open Questions:**
   - Timeline concerns need to be addressed
   - Resource allocation TBD

   **Next Steps:**
   - Follow-up meeting in 2 weeks
   ```

   ## Tips

   - The more structured your input notes, the better the summary
   - Consistent meeting note format helps the AI learn your style
   - You can save the output as a template for future meetings

   ## Credits

   Technique inspired by common meeting facilitation practices.
   ```

#### Phase 4: Pre-Submission Review

6. **Self-review checklist**

   Before submitting, go through this checklist:

   - [ ] I've read the entire file from top to bottom
   - [ ] There are NO personal names (mine or others)
   - [ ] There are NO company names (current, past, clients)
   - [ ] There are NO email addresses or phone numbers
   - [ ] There are NO specific dates that could identify me
   - [ ] There are NO project codenames or internal terminology
   - [ ] All examples use placeholder data like `[Name]`, `[Company]`
   - [ ] Documentation clearly explains the purpose
   - [ ] Documentation includes when to use / when not to use
   - [ ] Documentation includes examples (with placeholder data!)
   - [ ] I'm comfortable with this being public forever
   - [ ] I've tested this works as described

7. **Peer review** (optional but recommended)

   Ask a friend or colleague to review:
   - "Does this contain anything that could identify me?"
   - "Is the documentation clear?"
   - "Would you find this useful?"

#### Phase 5: Submission

8. **Choose the right location**

   Where should this contribution go?

   ```
   examples/library/
   ├── prompts/
   │   ├── engineering/          # Prompting techniques (Tree of Thought, etc.)
   │   ├── ai-configuration/     # System-level AI configs
   │   └── communication/        # Communication frameworks
   ├── content-templates/
   │   ├── social-media/         # Social post templates
   │   └── blog-enhancement/     # Blog writing
   └── workflows/                # Agentic workflows (future)
   ```

   For our meeting summary example:
   ```bash
   examples/library/content-templates/meeting-summaries/
   ```

9. **Add to your fork**

   ```bash
   cd ~/ragbot
   git checkout -b add-meeting-summary-prompt

   # Create directory if needed
   mkdir -p examples/library/content-templates/meeting-summaries

   # Copy your anonymized contribution
   cp /tmp/contribution.md examples/library/content-templates/meeting-summaries/meeting-minutes-summarization.md

   # Add a README for the directory (if new category)
   echo "# Meeting Summary Templates

   Prompts and templates for summarizing various types of meetings.
   " > examples/library/content-templates/meeting-summaries/README.md

   # Stage files
   git add examples/library/content-templates/meeting-summaries/

   # Commit with descriptive message
   git commit -m "Add meeting minutes summarization prompt

   This prompt helps generate concise, actionable meeting summaries from
   rough notes or transcripts.

   Features:
   - Extracts key decisions
   - Identifies action items with owners
   - Highlights open questions and next steps
   - Includes usage examples and customization ideas"

   # Push to your fork
   git push origin add-meeting-summary-prompt
   ```

10. **Create Pull Request on GitHub**

    - Go to your fork on GitHub
    - Click "New Pull Request"
    - Base repository: `rajivpant/ragbot` base: `main`
    - Head repository: `YOUR-USERNAME/ragbot` compare: `add-meeting-summary-prompt`

    **PR Title:**
    ```
    Add meeting minutes summarization prompt
    ```

    **PR Description:**
    ```markdown
    ## Description

    Adds a new prompt template for generating meeting summaries from rough notes.

    ## Use Case

    Helps teams quickly create actionable meeting summaries with:
    - Key decisions
    - Action items with owners
    - Open questions
    - Next steps

    ## Files Added

    - `examples/library/content-templates/meeting-summaries/meeting-minutes-summarization.md`
    - `examples/library/content-templates/meeting-summaries/README.md`

    ## Testing

    - [x] Tested with sample meeting notes
    - [x] Verified all examples use placeholder data
    - [x] Confirmed no personal information included
    - [x] Documentation is clear and complete

    ## Checklist

    - [x] Read CONTRIBUTING.md
    - [x] Anonymized all personal data
    - [x] Included usage documentation
    - [x] Added examples with placeholders
    - [x] Ready for public use
    ```

    - Click "Create Pull Request"

11. **Respond to feedback**

    - Maintainers may request changes
    - Address feedback promptly
    - Be open to suggestions

---

## Common Mistakes

### Mistake 1: Working in the Wrong Place

❌ **Wrong:**
```bash
cd ~/ragbot-data/
# Edit file
cd ~/ragbot
cp ~/ragbot-data/my-prompt.md examples/library/
git add examples/library/my-prompt.md
# DANGER: File might still have personal info!
```

✅ **Right:**
```bash
# Copy to temp FIRST
cp ~/ragbot-data/my-prompt.md /tmp/anonymized.md

# Edit /tmp/anonymized.md thoroughly
# Review multiple times
# Remove all personal info

# THEN copy to ragbot
cd ~/ragbot
cp /tmp/anonymized.md examples/library/my-contribution.md
```

### Mistake 2: Insufficient Anonymization

❌ **Wrong:**
```markdown
I developed this technique when I was PM at TechStartup Inc. We used it
for our weekly team syncs with the engineering team led by Sarah Johnson.
It helped us ship the Q2 2024 release 2 weeks early.
```

✅ **Right:**
```markdown
This technique works well for product teams coordinating weekly syncs.
Teams have reported improved alignment and faster shipping cycles.
```

### Mistake 3: Forgetting Embedded References

❌ **Wrong:** (Hidden references)
```markdown
# Example Meeting Notes

From: john.smith@techcorp.com
To: product-team@techcorp.com
Subject: Sprint Planning - Project Phoenix

Attendees: Sarah (PM), Mike (Eng Lead), Jennifer (Design)
Location: SF Office, Room 5B
```

✅ **Right:**
```markdown
# Example Meeting Notes

Type: Sprint Planning
Attendees: [Product Manager], [Engineering Lead], [Designer]

[Example content here...]
```

### Mistake 4: No Documentation

❌ **Wrong:**
```markdown
Ask Claude to summarize this meeting and create action items.

Meeting notes:
[placeholder]
```

✅ **Right:**
```markdown
# Meeting Summarization Prompt

## Purpose
This prompt helps you...

## When to Use
- Situation 1
- Situation 2

## How to Use
Step 1...

## Example
[Complete example with explanation]
```

---

## Review Process

After you submit a PR, here's what happens:

### 1. Automated Checks (Immediate)

- **CI/CD runs** - Linting, formatting checks
- **Basic validation** - File structure, markdown syntax

### 2. Maintainer Review (1-3 days typically)

A maintainer will review for:

- **Personal information** - Scanning for any data that could identify someone
- **Documentation quality** - Is it clear and helpful?
- **File organization** - Is it in the right place?
- **Value to community** - Will others find this useful?

Possible outcomes:

- ✅ **Approved** - Looks good, will merge!
- 🔄 **Changes Requested** - Please address these concerns
- ❌ **Closed** - Not suitable for inclusion (rare, with explanation)

### 3. Community Feedback (Ongoing)

Other contributors may:

- Comment on the PR
- Suggest improvements
- Test your contribution
- Ask clarifying questions

### 4. Merge (After approval)

- Maintainer merges your PR
- Changes become part of Ragbot
- You're credited as a contributor
- Appears in next release

---

## Questions?

### "Not sure if something is safe to contribute?"

Open a GitHub issue and ask! We're happy to help you anonymize or determine if something is appropriate.

### "Found personal data in existing examples?"

This is serious! Open a private security advisory immediately:
- Go to Security tab on GitHub
- Click "Report a vulnerability"
- Describe what you found (don't include the actual data in the report)

### "Want to contribute but worried about privacy?"

When in doubt:
1. Ask in a GitHub issue first
2. Over-anonymize rather than under-anonymize
3. Don't contribute if you're not 100% comfortable

**Your privacy > any contribution**

---

## Additional Resources

- [CONTRIBUTING.md](../CONTRIBUTING.md) - Quick reference guide
- [DATA_ORGANIZATION.md](DATA_ORGANIZATION.md) - Philosophy behind data separation
- [examples/README.md](../examples/README.md) - How to use examples and library

---

**Thank you for contributing to Ragbot safely and responsibly!**
