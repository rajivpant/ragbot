# Ragbot Library

## Purpose

The **Library** contains reusable prompts, frameworks, and techniques that you can **reference, adapt, or incorporate** into your Ragbot setup.

Unlike [templates](../templates/) which you copy and fill in, library resources are meant to be:
- Referenced in place
- Used as-is when they fit your needs
- Adapted and customized when needed
- Combined with other techniques

Think of this as a **toolkit of proven techniques** rather than a starting point.

## 📚 Library vs Templates

| Aspect | Templates (../templates/) | Library (here) |
|--------|---------------------------|----------------|
| **Purpose** | Get started quickly | Enhance and refine |
| **Usage** | Copy OUT and fill in | Reference or adapt |
| **Customization** | Required (has placeholders) | Optional (already complete) |
| **When to use** | First time setup | Ongoing improvement |
| **Example** | "About me template with [Your Name]" | "Tree of Thought prompting technique" |

## 🗂️ What's in the Library?

### Prompts

**Location:** `prompts/`

Advanced prompting techniques and frameworks:

#### Engineering (`prompts/engineering/`)
- **Tree of Thought** - Multi-path reasoning for complex problems
- **Chain of Thought** - Step-by-step problem decomposition
- **Few-Shot Learning** - Teaching AI through examples
- **Meta-Prompting** - Prompts that generate prompts

**When to use:** Complex problem-solving, technical challenges, multi-step reasoning

#### AI Configuration (`prompts/ai-configuration/`)
- **Code Generation** - Optimized settings for coding tasks
- **Anti-Watermarking** - Natural, human-like writing
- **Research Mode** - Deep analysis and fact-finding
- **Creative Mode** - Ideation and brainstorming

**When to use:** Configuring AI behavior for specific domains

#### Communication Frameworks (`prompts/communication/`)
- **Situation-Complication-Resolution** - Structured problem communication
- **BLUF (Bottom Line Up Front)** - Executive summary style
- **Five Ws** - Comprehensive information gathering
- **STAR Method** - Behavioral storytelling

**When to use:** Structured thinking, clear communication, professional writing

### Content Templates

**Location:** `content-templates/`

Ready-to-use frameworks for content creation:

- **Blog Post Enhancement** - Transform ideas into engaging posts
- **Social Media** - Platform-specific content strategies
- **Email Campaigns** - Effective email writing
- **Documentation** - Technical writing frameworks

**When to use:** Content creation, marketing, professional communication

### Workflows (Coming Soon)

**Location:** `workflows/`

Multi-step agentic processes:

- **Research → Outline → Draft → Edit** - Complete writing workflow
- **Problem → Analysis → Solution → Implementation** - Engineering workflow
- **Idea → Validate → Plan → Execute** - Product development workflow

**When to use:** Complex multi-stage projects

## 🎯 How to Use Library Resources

### Pattern 1: Reference in Place

Use library resources directly without copying:

```bash
# In your custom-instructions file, reference library techniques
See /app/examples/library/prompts/engineering/tree-of-thought.md for approach
```

**Good for:** One-off uses, experimentation

### Pattern 2: Use As-Is

Incorporate library content directly into your prompts:

```bash
# Copy specific technique into your curated datasets
cp examples/library/prompts/communication/scr-framework.md \
   curated-datasets/my-data/frameworks/
```

**Good for:** Techniques you use regularly

### Pattern 3: Copy and Customize

Adapt library resources to your specific needs:

```bash
# Copy to your data directory, then modify
cp examples/library/content-templates/blog-post.md \
   /path/to/ragbot-data/my-templates/
# Edit to add your personal style, industry specifics, etc.
```

**Good for:** Resources that need personalization

## 📖 Detailed Directory Guide

### Prompts/Engineering

**Purpose:** Advanced reasoning and problem-solving techniques

**Files:**
- `tree-of-thought.md` - Explore multiple solution paths simultaneously
- `chain-of-thought.md` - Break complex problems into steps
- `few-shot-learning.md` - Teach through examples
- `self-consistency.md` - Generate and compare multiple answers

**Example Use Case:**
You're solving a complex architecture problem. Use Tree of Thought to explore multiple approaches, then use Self-Consistency to validate the best solution.

### Prompts/AI-Configuration

**Purpose:** Configure AI behavior for specific tasks

**Files:**
- `code-generation.md` - Optimized for coding (concise, commented, tested)
- `anti-watermarking.md` - Natural writing without AI tells
- `research-mode.md` - Deep, thorough analysis
- `creative-mode.md` - Ideation and brainstorming

**Example Use Case:**
When writing code, reference code-generation.md in your custom instructions. When writing blog posts, switch to anti-watermarking.md for natural tone.

### Prompts/Communication

**Purpose:** Structured frameworks for clear communication

**Files:**
- `scr-framework.md` - Situation-Complication-Resolution
- `bluf.md` - Bottom Line Up Front (executive style)
- `five-ws.md` - Who, What, When, Where, Why, How
- `star-method.md` - Situation, Task, Action, Result

**Example Use Case:**
Writing a project proposal? Use SCR framework. Writing to executives? Use BLUF. Telling a story about your achievements? Use STAR method.

### Content-Templates

**Purpose:** Ready-to-use content creation frameworks

**Files:**
- `blog-enhancement.md` - Transform rough ideas into polished posts
- `social-media-strategy.md` - Platform-specific content approaches
- `email-campaigns.md` - Effective email writing
- `technical-documentation.md` - Clear technical writing

**Example Use Case:**
You have a technical topic to explain. Use blog-enhancement.md for general audience, or technical-documentation.md for developer audience.

## 🔄 Combining Library Resources

Library resources work great together:

**Example: Writing a Technical Blog Post**

```bash
curated-datasets/my-blog-project/
├── topic-research.md          # Your research on the topic
├── target-audience.md         # Who you're writing for
└── instructions.md            # References multiple library resources:

"Use Tree of Thought (examples/library/prompts/engineering/) to explore
different angles for this topic.

Then apply the Blog Enhancement framework
(examples/library/content-templates/blog-enhancement.md) to structure the post.

Finally, use Anti-Watermarking settings
(examples/library/prompts/ai-configuration/anti-watermarking.md) to ensure
natural, engaging tone."
```

**Example: Solving a Complex Engineering Problem**

```bash
curated-datasets/project-x/
├── problem-description.md     # What you're trying to solve
├── constraints.md             # Technical constraints
└── approach.md                # References:

"1. Use Chain of Thought to break down the problem
2. Apply Few-Shot Learning with these 3 similar examples: [...]
3. Use Self-Consistency to validate the solution
4. Document using Technical Documentation framework"
```

## 🆕 Adding Your Own Library Resources

As you develop techniques that work well, you can:

1. **Keep private** - Add to your private ragbot-data/library/
2. **Contribute back** - Anonymize and submit to public ragbot/examples/library/

### Your Private Library

```bash
# Create your own library alongside ragbot's
ragbot-data/
├── curated-datasets/
├── custom-instructions/
└── library/                   # Your private techniques
    ├── my-prompts/
    ├── my-workflows/
    └── proprietary-methods/
```

### Contributing to Public Library

Have a great technique to share? See [CONTRIBUTING.md](../../CONTRIBUTING.md) for how to safely contribute library resources.

**Key steps:**
1. Anonymize thoroughly (remove personal info, company names, etc.)
2. Add clear documentation (purpose, when to use, examples)
3. Use placeholders for any specific data
4. Submit pull request

## 🎓 Learning Path

### Beginner
Start with these accessible techniques:
1. **Communication Frameworks** - Easy to apply, immediate benefit
2. **Blog Enhancement** - Great for content creation
3. **Anti-Watermarking** - Improve writing naturalness

### Intermediate
Once comfortable, explore:
1. **Chain of Thought** - Better problem-solving
2. **Code Generation** - Optimized coding assistance
3. **SCR Framework** - Professional problem communication

### Advanced
Master complex techniques:
1. **Tree of Thought** - Multi-path reasoning
2. **Self-Consistency** - Solution validation
3. **Custom Workflows** - Multi-stage processes

## 💡 Tips for Using the Library

### Do ✅

1. **Experiment** - Try techniques to see what works for your use cases
2. **Combine** - Mix and match techniques for complex tasks
3. **Customize** - Adapt library resources to your specific needs
4. **Document** - Note which techniques work best for which tasks
5. **Contribute** - Share your successful adaptations (anonymized)

### Don't ❌

1. **Don't feel overwhelmed** - Start with one or two techniques
2. **Don't use everything** - Pick what's relevant to your needs
3. **Don't copy blindly** - Understand why a technique works
4. **Don't skip documentation** - Read the full description before using
5. **Don't forget to personalize** - Adapt to your context

## 📊 Quick Reference

| I want to... | Use this resource |
|-------------|-------------------|
| Solve a complex problem | Tree of Thought (prompts/engineering/) |
| Write more naturally | Anti-Watermarking (prompts/ai-configuration/) |
| Structure a presentation | SCR Framework (prompts/communication/) |
| Improve a blog post | Blog Enhancement (content-templates/) |
| Generate better code | Code Generation (prompts/ai-configuration/) |
| Explain my achievements | STAR Method (prompts/communication/) |
| Break down a big task | Chain of Thought (prompts/engineering/) |
| Create social content | Social Media Strategy (content-templates/) |

## ❓ FAQ

**Q: Should I copy library resources to my ragbot-data/?**

A: It depends on usage:
- Use often → Copy to your ragbot-data for easy access
- Use occasionally → Reference from examples/library
- Need to customize → Copy and modify in your ragbot-data

**Q: What's the difference between library and templates?**

A: Templates are starting points you MUST copy and customize (they have placeholders). Library resources are complete techniques you CAN use as-is or adapt.

**Q: Can I modify library resources?**

A: Absolutely! Copy to your ragbot-data and modify as needed. The library versions are reference implementations.

**Q: How do I know which technique to use?**

A: Start with the "When to use" sections in each file. Experiment with a few. Over time you'll develop intuition for which techniques fit which tasks.

**Q: Can I contribute my own techniques?**

A: Yes! See [CONTRIBUTING.md](../../CONTRIBUTING.md). Make sure to anonymize and document clearly.

## 🔗 Related Documentation

- [Templates README](../templates/README.md) - Starter templates to copy and customize
- [Examples README](../README.md) - Overview of all examples
- [CONTRIBUTING.md](../../CONTRIBUTING.md) - How to contribute safely
- [DATA_ORGANIZATION.md](../../docs/DATA_ORGANIZATION.md) - Philosophy of data separation

## 🚀 Next Steps

1. **Browse** - Explore the directories to see what's available
2. **Try** - Pick one technique that interests you
3. **Apply** - Use it in a real task with Ragbot
4. **Iterate** - Refine based on results
5. **Expand** - Add more techniques as needed

---

**Remember: The library is a toolkit. Use what helps, ignore what doesn't, customize what's close, and contribute what works!**
