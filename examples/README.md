# Ragbot Examples and Templates

Welcome! This directory contains everything you need to get started with Ragbot quickly and effectively.

## 🚀 Quick Start (5 Minutes)

The fastest way to get Ragbot running:

```bash
# 1. Copy the starter template
cp -r examples/curated-datasets/starter-template/ curated-datasets/my-data/

# 2. Copy custom instructions
cp examples/custom-instructions/starter-template/default-instructions.md custom-instructions/

# 3. Edit the files with your information
# Open and customize: curated-datasets/my-data/about-me.md, professional.md, preferences.md

# 4. Start Ragbot
docker-compose up
```

That's it! You now have a personalized AI assistant that knows about you.

## 📁 What's in This Directory?

### Starter Templates

**Perfect for:** First-time users who want to get running immediately

Location: `curated-datasets/starter-template/` and `custom-instructions/starter-template/`

These are minimal, ready-to-use templates. Just copy, fill in your information, and go!

- **about-me.md** - Your personal background and interests
- **professional.md** - Work history, skills, and expertise
- **preferences.md** - How you like to communicate and work
- **default-instructions.md** - How Ragbot should behave

[→ Start here if you're new](curated-datasets/starter-template/)

### Custom Instructions Variations

**Perfect for:** Configuring Ragbot for different roles and tasks

Location: `custom-instructions/variations/`

Pre-configured instruction sets for common use cases:

- **technical-advisor.md** - Senior engineering advisor for code and architecture
- **creative-writer.md** - Writing coach and content creation assistant
- **coach.md** - Personal coach for goals and accountability (coming soon)

[→ Browse custom instruction variations](custom-instructions/variations/)

### Prompt Library

**Perfect for:** Advanced users wanting sophisticated prompting techniques

Location: `prompt-library/`

A curated collection of proven prompts and frameworks:

- **Prompt Engineering** - Tree of Thought, Chain of Thought, and more
- **AI Configuration** - System-level instructions for specific tasks
- **Communication Frameworks** - Structured thinking and communication
- **Content Templates** - Blog posts, social media, and content creation

[→ Explore the prompt library](prompt-library/)

## 🎯 Use Case Examples

### Personal Life Assistant

**What it does:** Helps with personal tasks, family coordination, scheduling, and daily life

**Setup:**
```bash
cp -r examples/curated-datasets/starter-template/ curated-datasets/personal/
# Edit files with family info, schedule, preferences
# Add custom instructions for task management
```

**Good for:**
- Managing family schedules
- Meal planning and recipes
- Travel planning
- Personal productivity

### Work Project Companion

**What it does:** Provides project-specific context and assistance

**Setup:**
```bash
mkdir curated-datasets/work-project/
# Add: project-overview.md, team-members.md, technical-specs.md
cp examples/custom-instructions/variations/technical-advisor.md custom-instructions/
```

**Good for:**
- Project planning and tracking
- Technical problem-solving
- Code reviews
- Documentation

### Content Creation Studio

**What it does:** Helps create and improve written content

**Setup:**
```bash
cp -r examples/curated-datasets/starter-template/ curated-datasets/content-creator/
cp examples/custom-instructions/variations/creative-writer.md custom-instructions/
# Add your writing samples to curated-datasets/content-creator/
```

**Good for:**
- Blog writing
- Social media posts
- Marketing content
- Creative projects

### Learning and Research

**What it does:** Organizes study materials and facilitates learning

**Setup:**
```bash
mkdir curated-datasets/learning/
# Add: course-notes.md, research-papers/, topics.md
# Configure for clear explanations and teaching
```

**Good for:**
- Studying new topics
- Research projects
- Organizing knowledge
- Understanding complex subjects

## 🗂️ How to Organize Your Data

### Recommended Structure

```
curated-datasets/
├── personal/           # Personal information, family, interests
├── professional/       # Work history, skills, projects
├── projects/           # Specific project contexts
│   ├── project-a/
│   └── project-b/
└── learning/           # Study materials, research

custom-instructions/
├── default.md          # Your baseline behavior configuration
├── project-specific.md # Project-specific instructions
└── domain-specific.md  # e.g., code-focused, writing-focused
```

### Tips for Organizing

**Do:**
- ✅ Create separate folders for different contexts (work, personal, projects)
- ✅ Use clear, descriptive file names
- ✅ Keep files focused on one topic
- ✅ Update your data as your life/work changes

**Don't:**
- ❌ Put everything in one giant file
- ❌ Include information you don't want AI to know
- ❌ Mix public and private information without care
- ❌ Forget to update outdated information

## 🔒 Privacy and Security

### What Gets Shared?

**Stays Local:**
- Everything in `curated-datasets/` and `custom-instructions/` stays on your machine
- These directories are in `.gitignore` by default
- Ragbot reads these files but doesn't transmit them anywhere except to the AI API

**Sent to AI API:**
- Your curated datasets are included in prompts sent to the AI service (OpenAI, Anthropic, etc.)
- Make sure you're comfortable with this information being processed by the AI provider

### Best Practices

1. **Separate Sensitive Data** - Keep truly sensitive information (passwords, SSNs, financial details) OUT of curated datasets
2. **Use Private Repo** - Consider keeping your data in a separate private git repository
3. **Review Before Adding** - Ask yourself: "Am I comfortable with an AI knowing this?"
4. **Regular Audits** - Periodically review what's in your datasets

## 📖 Next Steps

### After Quick Start

1. **Try it out** - Ask Ragbot questions that relate to your data
2. **Refine** - Adjust custom instructions based on how it responds
3. **Expand** - Add more context files as needed
4. **Experiment** - Try different custom instruction variations

### Learning More

- **Documentation** - See [docs/DATA_ORGANIZATION.md](../docs/DATA_ORGANIZATION.md) for the philosophy
- **Prompt Library** - Explore [prompt-library/README.md](prompt-library/README.md) for advanced techniques
- **Docker Guide** - Read [README-DOCKER.md](../README-DOCKER.md) for deployment options

## 🤝 Contributing

Have a great example or template to share? Contributions are welcome!

**What we're looking for:**
- Useful templates that others can adapt
- Generic prompts (no personal information)
- Clear documentation and usage examples
- Proven approaches that work well

## 💡 Tips and Tricks

### Getting Better Results

1. **Be Specific** - More context in your curated datasets = better responses
2. **Iterate** - Refine your custom instructions over time
3. **Organize** - Keep related information together
4. **Update** - Keep your data current and relevant

### Common Patterns

**Pattern 1: Multiple Profiles**
Create different data folders for different contexts, switch between them using docker-compose.override.yml

**Pattern 2: Layered Instructions**
Combine multiple custom instruction files for different aspects (base behavior + domain-specific)

**Pattern 3: Template Library**
Build your own collection of prompts and templates in curated-datasets/templates/

## ❓ FAQ

**Q: How much data should I include?**
A: Start small (just the starter template), then add more as you find what's useful. Quality > quantity.

**Q: Can I use Ragbot for work?**
A: Yes! Just be mindful of what company/client information you include. Check your organization's AI usage policies.

**Q: What if I want to keep some data private?**
A: Use docker-compose.override.yml to mount different data directories. Keep private data in a separate location.

**Q: How often should I update my data?**
A: Whenever it changes! Big life/work changes, new projects, updated preferences - keep it current.

**Q: Can I share my setup?**
A: Yes! Just anonymize any personal information first. Consider contributing generic parts back to this examples directory.

---

**Ready to start?** Copy the starter template and customize it with your information. You'll have a personalized AI assistant running in minutes!
