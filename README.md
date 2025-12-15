## 🚀 Ragbot & RaGenie: Two Products, One Ecosystem

**Ragbot continues active development** alongside **RaGenie**, its next-generation sibling. Both are open source and share the same data layer (ragbot-data).

### Choosing Between Ragbot and RaGenie

| Use Case | Recommendation |
|----------|----------------|
| Quick setup, CLI-focused workflow | **Ragbot** |
| Need RAG with vector search | **Both** (Ragbot now has Qdrant RAG) |
| Prefer Streamlit simplicity | **Ragbot** |
| Need microservices architecture | **RaGenie** |
| Want both CLI and modern web UI | Use both! |

### RaGenie Overview

**RaGenie** ([www.ragenie.com](https://www.ragenie.com) | [www.ragenie.ai](https://www.ragenie.ai)) is a modern microservices platform that complements Ragbot:

| Feature | Ragbot (v1) | RaGenie (v2) |
|---------|-------------|--------------|
| Architecture | Monolithic Streamlit | Microservices (FastAPI + React) |
| Authentication | None | JWT OAuth2 with role-based access |
| Storage | File system + Qdrant | PostgreSQL + MinIO + Qdrant (vectors) |
| RAG | Qdrant vector search | Automatic embeddings with semantic search |
| Scalability | Single container | Horizontal scaling with load balancing |
| Monitoring | None | Prometheus + Grafana dashboards |
| Caching | None | Redis with smart invalidation |
| API | None | RESTful APIs with documentation |

### Key Benefits

- **Automatic Synchronization:** Edit markdown files and see changes indexed within 45 seconds
- **Advanced RAG:** Vector embeddings for semantic search across all your knowledge
- **Production Ready:** Built-in monitoring, health checks, and backup strategies
- **Secure by Default:** Authentication, encryption, and access control
- **Developer Friendly:** Interactive API docs, database migrations, comprehensive testing

### Seamless Migration

Your existing workflow doesn't change:
- ✅ ragbot-data repository remains your source of truth
- ✅ Edit markdown files as you always have
- ✅ Same directory structure (datasets/, instructions/, runbooks/, workspaces/)
- ✅ Git workflow unchanged
- ✅ RaGenie mounts ragbot-data read-only (never modifies your files)

**Migration Resources:**
- **RaGenie Repository:** [github.com/rajivpant/ragenie](https://github.com/rajivpant/ragenie)
- **Integration Guide:** [RAGENIE_INTEGRATION.md](https://github.com/rajivpant/ragbot-data/blob/main/RAGENIE_INTEGRATION.md)
- **Quick Start:** [RaGenie QUICKSTART.md](https://github.com/rajivpant/ragenie/blob/main/QUICKSTART.md)

### Development Status

Both products are actively developed:

**Ragbot:**
- ✅ Bug fixes and security updates
- ✅ Compatibility updates for new LLM models
- ✅ New features including RAG capabilities (using Qdrant, same as RaGenie)
- ✅ Continued CLI and Streamlit UI improvements

**RaGenie:**
- ✅ Modern microservices architecture
- ✅ Advanced RAG with automatic indexing
- ✅ Production-ready deployment features

**Choose the product that fits your workflow - or use both!**

---

Ragbot.AI
=========

🤖 [Ragbot.AI (formerly named rbot)](https://github.com/rajivpant/ragbot): Rajiv's open source AI augmented brain assistant combines the power of large language models (LLMs) with [Retrieval Augmented Generation](https://ai.meta.com/blog/retrieval-augmented-generation-streamlining-the-creation-of-intelligent-natural-language-processing-models/) (RAG).

🚀 Ragbot.AI processes user prompts along with instructions, datasets, and runbooks, enabling context-aware responses. Powered by the latest LLMs including OpenAI's GPT-4o and o-series models, Anthropic's Claude Sonnet 4.5 and Claude Opus 4.5, and Google's Gemini 2.5 series, Ragbot.AI uses RAG, a technique that combines the power of pre-trained dense retrieval and sequence-to-sequence models to generate more factual and informative text.

🧠 Instructions and datasets help Ragbot.AI better understand context, resulting in personalized, more accurate, and relevant responses, surpassing the capabilities of out of the box LLMs.

Developed by [Rajiv Pant](https://github.com/rajivpant)

## Development Methodology

Ragbot is developed using **Synthesis Engineering** (also known as **Synthesis Coding**)—a systematic approach that combines human architectural expertise with AI-assisted implementation. This methodology ensures that while AI accelerates development velocity, engineers maintain architectural authority, enforce quality standards, and deeply understand every component of the system.

Key principles applied in Ragbot's development:
- Human-defined architecture with AI-accelerated implementation
- Systematic quality assurance regardless of code origin
- Context preservation across development sessions
- Iterative refinement based on real-world usage

Learn more about this approach:
- [Synthesis Engineering: The Professional Practice](https://rajiv.com/blog/2025/11/09/synthesis-engineering-the-professional-practice-emerging-in-ai-assisted-development/)
- [The Organizational Framework](https://rajiv.com/blog/2025/11/09/the-synthesis-engineering-framework-how-organizations-build-production-software-with-ai/)
- [Technical Implementation with Claude Code](https://rajiv.com/blog/2025/11/09/synthesis-engineering-with-claude-code-technical-implementation-and-workflows/)

Code Contributors & Collaborators
- [Alexandria Redmon](https://github.com/alexdredmon)
- [Ishaan Jaffer](https://www.linkedin.com/in/reffajnaahsi/)
- [Trace Wax](https://github.com/tracedwax)
- [Jim Mortko](https://github.com/jskills)
- [Vik Pant](https://www.linkedin.com/in/vikpant/)

How to Contribute

Your code contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for important safety guidelines (especially about not committing personal data), then fork the repository and submit a pull request with your improvements.

[![](https://img.shields.io/badge/Chat_with_Ragbot.ai-Ask_Cody-%238A16D7?labelColor=%23383838)](https://sourcegraph.com/github.com/rajivpant/ragbot)

Blog Post Introducing Ragbot.AI
--------------------------

[Introducing Ragbot.AI: A Personalized AI Assistant, Written by Ragbot.AI](https://rajiv.com/blog/2023/05/08/introducing-rbot-a-personalized-ai-assistant-written-by-rbot/)

Excerpt from the blog post:

### Ragbot.AI: Offering Personalized Assistance Beyond ChatGPT Plus, Bing Chat, and Google Bard Currently Offer

As an AI assistant, I provide a unique level of personalization and adaptability that sets me apart from current implementations of ChatGPT Plus, Bing Chat, and Google Bard. By using folders containing customized dataset files, I can cater to multiple use cases, such as personal life, work, education, and specific projects. This customization enables me to understand and support you in a way that is tailored to your unique needs.

#### Serving as Your Personal Life Assistant

You can create a folder with dataset files that include personal information, family details, travel and food preferences, and more. By using this information, I can function as your personal life assistant, offering AI-powered recommendations and support tailored to your specific context.

#### Assisting You in Your Professional Life

Similarly, you can develop another folder containing dataset files related to your work life. These files might include details about your job, industry, colleagues, projects, and other work-related information. With this context, I can help you with various tasks, such as drafting emails, scheduling meetings, conducting research, and more, enhancing your efficiency and organization.

#### Supporting Your Educational Goals

You can also customize me for educational purposes by creating a folder with dataset files containing information about your academic background, subjects of interest, courses, and other educational details. In this role, I can provide personalized educational support, from helping with homework to explaining complex concepts or recommending learning resources.

#### Providing Project-Specific Help

In addition to the use cases mentioned above, I can be tailored to support you on specific projects. By creating a workspace folder with dataset files containing project-related information, such as objectives, team members, deadlines, and relevant resources, I can assist you throughout the project lifecycle, offering valuable insights and support tailored to each unique project.

My ability to create distinct profiles for different needs using customized dataset files and workspaces sets me apart from ChatGPT Plus, Bing Chat, and Google Bard. This versatility enables me to offer personalized assistance across multiple aspects of your life, ensuring that I can understand and cater to your specific requirements.

Quick Start
-----------

Get Ragbot running in 5 minutes:

### Option 1: Quick Start with Example Data (Fastest)

```bash
# 1. Clone this repository
git clone https://github.com/rajivpant/ragbot.git
cd ragbot

# 2. Set up your API keys
cp .env.docker .env
# Edit .env and add at least one API key (OpenAI, Anthropic, or Gemini)

# 3. Get starter templates from ai-knowledge-ragbot
git clone https://github.com/rajivpant/ai-knowledge-ragbot.git ~/ai-knowledge-ragbot
cp -r ~/ai-knowledge-ragbot/source/datasets/templates/ datasets/my-data/
cp ~/ai-knowledge-ragbot/source/instructions/templates/default.md instructions/

# 4. Customize with your information
# Edit the files in datasets/my-data/ with your personal details

# 5. Start Ragbot with Docker
docker-compose up -d

# 6. Access the web interface
open http://localhost:8501
```

### Option 2: Using Your Own Data Repository (Recommended for Production)

If you want to keep your data in a separate directory or private repository:

```bash
# 1. Clone Ragbot
git clone https://github.com/rajivpant/ragbot.git
cd ragbot

# 2. Create your data directory
mkdir ~/ragbot-data
# Or clone your private data repo: git clone <your-private-repo> ~/ragbot-data

# 3. Set up Docker override
cp docker-compose.override.example.yml docker-compose.override.yml
# Edit docker-compose.override.yml to point to your data directory

# 4. Organize your data (get templates from ai-knowledge-ragbot)
git clone https://github.com/rajivpant/ai-knowledge-ragbot.git ~/ai-knowledge-ragbot
cp -r ~/ai-knowledge-ragbot/source/datasets/templates/* ~/ragbot-data/datasets/
cp ~/ai-knowledge-ragbot/source/instructions/templates/default.md ~/ragbot-data/instructions/

# 5. Configure API keys
cp .env.docker .env
# Edit .env with your API keys

# 6. Start Ragbot
docker-compose up -d
```

### What's Next?

- 📖 **Knowledge Base:** Get templates and runbooks from [ai-knowledge-ragbot](https://github.com/rajivpant/ai-knowledge-ragbot)
- 🎓 **Understand the philosophy:** Read [docs/DATA_ORGANIZATION.md](docs/DATA_ORGANIZATION.md)
- 🐳 **Docker deployment:** See [README-DOCKER.md](README-DOCKER.md) for deployment guide
- 🤝 **Contributing safely:** Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing
- ⚙️ **Detailed setup:** Follow the [installation guide](INSTALL.md) and [configuration guide](CONFIGURE.md)

RAG (Retrieval-Augmented Generation)
------------------------------------

Ragbot now includes built-in RAG capabilities using **Qdrant** vector database and **sentence-transformers** for semantic search. This allows Ragbot to intelligently retrieve relevant content from your knowledge base when answering questions.

### How RAG Works

1. **Indexing**: Your workspace content (datasets, knowledge files) is chunked and embedded into vectors
2. **Storage**: Vectors are stored in a local Qdrant database (persisted in Docker volume)
3. **Retrieval**: When you ask a question, relevant chunks are retrieved by semantic similarity
4. **Augmentation**: Retrieved context is added to your prompt for more accurate responses

### Using RAG in the Web UI

1. Select a workspace in the sidebar
2. Click **"Index Workspace"** in Advanced Settings to build the index (first time only)
3. Enable **"Enable RAG"** checkbox
4. Adjust **"RAG context tokens"** slider to control how much context is retrieved

### RAG Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Enable RAG | On | Toggle RAG-augmented responses |
| RAG context tokens | 16000 | Maximum tokens for retrieved context (Phase 1: 8x increase from 2000) |
| Embedding model | all-MiniLM-L6-v2 | 384-dimension embeddings, fast and effective |

### Technical Details

- **Vector Database**: Qdrant (local file-based storage at `/app/qdrant_data`)
- **Embedding Model**: sentence-transformers `all-MiniLM-L6-v2` (80MB, 384 dimensions)
- **Chunking**: ~500 tokens per chunk with 50-token overlap
- **Similarity**: Cosine distance for semantic matching

AI Knowledge Integration
------------------------

Ragbot integrates with the **AI Knowledge** ecosystem for managing knowledge bases across multiple workspaces.

### Open Source Knowledge Base

The **[ai-knowledge-ragbot](https://github.com/rajivpant/ai-knowledge-ragbot)** repository contains open-source runbooks, templates, and guides that ship with Ragbot:

- **Instruction templates** - Starter configurations for AI assistants
- **Dataset templates** - Personal and professional profile templates
- **Runbooks** - Procedures for content creation, communication, system configuration
- **Guides** - Reference materials for working with AI

Personal ai-knowledge repos can inherit from ai-knowledge-ragbot to get these shared resources while adding private content.

### AI Knowledge Compiler

The AI Knowledge Compiler transforms source content into optimized formats for AI consumption.

**Key concept:** The output repo determines what content is included—not who runs the compiler. Anyone with write access can compile into a repo. See [docs/compilation-guide.md](docs/compilation-guide.md) for details.

```
ai-knowledge-{workspace}/
├── source/                    # Your source files
│   ├── instructions/          # WHO - Identity, persona, rules
│   ├── runbooks/             # HOW - Procedures, workflows
│   └── datasets/             # WHAT - Reference knowledge
└── compiled/                  # Generated by compiler
    └── {project}/             # One folder per compiled project
        ├── instructions/      # LLM-specific (claude.md, chatgpt.md, gemini.md)
        ├── knowledge/         # Individual knowledge files
        └── vectors/           # Chunked for RAG
```

Quick compilation examples:

```bash
# Baseline (single repo content only)
ragbot compile --repo ~/ai-knowledge/ai-knowledge-{project}

# With inheritance (output repo determines content)
ragbot compile --all-with-inheritance --output-repo ~/ai-knowledge/ai-knowledge-{output}
```

For detailed setup instructions, see the [LLM Project Setup Guide](https://github.com/rajivpant/ai-knowledge-ragbot/blob/main/source/runbooks/system-config/llm-project-setup.md).

### Convention-Based Discovery

Ragbot automatically discovers AI Knowledge repositories by convention:

1. Mount your `ai-knowledge` parent directory to `/app/ai-knowledge`
2. Ragbot scans for directories matching `ai-knowledge-{workspace}`
3. Each discovered repo provides instructions and knowledge for that workspace

### Docker Setup with AI Knowledge

```yaml
# docker-compose.override.yml
services:
  ragbot-web:
    volumes:
      - ${HOME}/projects/my-projects/ai-knowledge:/app/ai-knowledge:ro
      - ./workspaces:/app/workspaces:ro
```

### Workspace Configuration

Create `workspace.yaml` files to customize workspace behavior:

```yaml
# workspaces/my-project/workspace.yaml
name: My Project
description: Project-specific AI assistant
status: active
type: work
inherits_from:
  - personal  # Inherit from personal workspace
```

### Content Loading Strategy

| Content Type | Loading Method | Use Case |
|--------------|----------------|----------|
| Instructions | Always loaded | Core identity and behavior |
| Datasets | Direct or RAG | Small: direct, Large: RAG |
| Runbooks | RAG retrieval | Retrieved when relevant |

Supported AI Models
-------------------

Ragbot.AI supports the latest models from three leading AI providers (as of October 2025):

**OpenAI Models:**

- **o3 Series**: o3-mini, o3-pro, o3-deep-research - Most advanced reasoning models
- **o1 Series**: o1, o1-pro, o1-mini, o1-preview - Advanced reasoning capabilities
- **GPT-4o Series**: gpt-4o (default), gpt-4o-mini - Latest multimodal flagship models
- **GPT-4o Audio**: gpt-4o-audio-preview, gpt-4o-mini-audio-preview - Multimodal with audio support
- **GPT-4 Turbo**: Previous generation model

**Anthropic Models:**

- **Claude 4.5 Sonnet** (default): claude-sonnet-4-5 - Latest and most capable
- **Claude 4.5 Opus**: claude-opus-4-5 - Most powerful reasoning
- **Claude 4 Series**: claude-4-opus, claude-4-sonnet - Extended context versions
- **Claude 3.7 Sonnet**: Hybrid reasoning capabilities
- **Claude 3.5 Series**: claude-3-5-sonnet, claude-3-5-haiku - High performance
- **Claude 3 Series**: claude-3-opus, claude-3-haiku - Previous generation

**Google Gemini Models:**

- **Gemini 2.5 Series**: gemini-2.5-pro, gemini-2.5-flash (default), gemini-2.5-flash-lite
- **Gemini 2.0 Series**: gemini-2.0-flash, gemini-2.0-flash-lite, gemini-2.0-pro-exp
- **Experimental**: gemini-2.0-flash-thinking-exp, gemini-exp-1206

All models are configured in [engines.yaml](engines.yaml) with their respective capabilities, token limits, and default settings.

Installation, Configuration, and Personalization
------------------------------------------------
Read the [installation guide](INSTALL.md) and the [configuration and personaliation guide](CONFIGURE.md).

Using the Web version
---------------------
![](screenshots/Screenshot%202023-06-16%20at%2010.53.12%20PM.png)
![](screenshots/Screenshot%202024-04-10%20at%2010.46.02 PM.png)
![](screenshots/Screenshot%202023-08-02%20at%2010.30.37%20PM.png)


Using the command line interface
--------------------------------

The CLI uses workspaces with RAG (Retrieval-Augmented Generation) and automatically loads LLM-specific instructions based on the model you're using.

### Key CLI Options

```
ragbot chat [options]

Input Options:
  -p, --prompt PROMPT          Prompt text
  -f, --prompt_file FILE       Read prompt from file
  -i, --interactive            Interactive mode with history
  --stdin                      Read prompt from stdin

Workspace & Knowledge:
  -profile NAME                Workspace to use (auto-loads instructions and enables RAG)
  --rag / --no-rag            Enable/disable RAG retrieval (default: enabled)

Model Selection:
  -e {openai,anthropic,google} Engine/provider
  -m MODEL                     Model name (or 'flagship' for best)

Custom Instructions:
  -c PATH [PATH ...]           Explicit instruction files (overrides auto-loading)
  -nc                          Disable all instructions
```

### Using Workspaces with RAG

The recommended way to use the CLI is with workspaces:

```bash
# Chat with a workspace - instructions auto-loaded, RAG enabled
ragbot chat -profile personal -p "What are my travel preferences?"

# Use Anthropic Claude (loads claude.md instructions)
ragbot chat -profile personal -e anthropic -p "Summarize my work history"

# Use OpenAI GPT-5.2 (loads chatgpt.md instructions)
ragbot chat -profile personal -e openai -m gpt-5.2 -p "Summarize my work history"

# Use Google Gemini (loads gemini.md instructions)
ragbot chat -profile personal -e google -p "Summarize my work history"
```

### LLM-Specific Instructions

The system automatically loads the correct instruction file based on the LLM:

| Engine | Instruction File |
|--------|------------------|
| anthropic | `compiled/{workspace}/instructions/claude.md` |
| openai | `compiled/{workspace}/instructions/chatgpt.md` |
| google | `compiled/{workspace}/instructions/gemini.md` |

### Interactive Mode

Maintain conversation history across multiple prompts:

```bash
ragbot chat -profile personal -i

> Tell me about my professional background
Ragbot.AI: [response based on RAG-retrieved knowledge]

> Summarize it in 3 bullet points
Ragbot.AI: [continues with context]

> /save session.json
Conversation saved to ...

> /quit
```

### Legacy CLI Usage

The following options show the full help output for reference. Note that dataset files (`-d`) are no longer supported - use workspaces with RAG instead.

```console
$ ragbot chat --help
usage: ragbot chat [-h] [-ls] [-p PROMPT | -f PROMPT_FILE | -i | --stdin]
                 [-profile PROFILE] [-c [CUSTOM_INSTRUCTIONS ...]] [-nc]
                 [--rag] [--no-rag]
                 [-e {openai,anthropic,google}] [-m MODEL] [-t TEMPERATURE]
                 [-mt MAX_TOKENS] [-l LOAD]

Ragbot.AI is an augmented brain and assistant. Learn more at https://ragbot.ai

options:
  -h, --help            show this help message and exit
  -ls, --list-saved     List all the currently saved JSON files.
  -p, --prompt          The user's input prompt
  -f, --prompt_file     Read prompt from a file
  -i, --interactive     Enable interactive mode with conversation history
  --stdin               Read prompt from stdin
  -profile              Workspace name (enables RAG and auto-loads instructions)
  -c                    Custom instruction file paths (overrides auto-loading)
  -nc                   Disable custom instructions
  --rag                 Enable RAG retrieval (default)
  --no-rag              Disable RAG - instructions only
  -e {openai,anthropic,google}  LLM engine/provider
  -m MODEL              Model name or 'flagship'
  -t TEMPERATURE        Creativity (0-2)
  -mt MAX_TOKENS        Max response tokens
  -l LOAD               Load previous session from file
```

### Knowledge Retrieval (RAG)

Knowledge is retrieved via RAG (Retrieval-Augmented Generation) from indexed workspace content:

```bash
ragbot chat -profile personal -p "What are my travel preferences?"
# RAG enabled for workspace: personal
# [Response based on retrieved knowledge]
```

---

**Note:** The legacy `-d` (dataset) flag has been removed. Use workspaces with RAG instead.

<details>
<summary>Legacy examples (deprecated)</summary>

Example 1:

```console
rajivpant@RP-2021-MacBook-Pro ragbot % ./ragbot.py -d instructions/ datasets/public/ ../ragbot-data/datasets/personal/ ../ragbot-data/workspaces/my-employer/ -p "Write a short note in Rajiv's voice about Rajiv's job, coworkers, family members, and travel and food preferences for the person temporarily backfilling for his EA." 
datasets being used:
 - instructions/
 - datasets/public/travel-food.md
 - datasets/public/employment-history.md
 - datasets/public/about.md
 - datasets/public/biography.md
 - ../ragbot-data/datasets/personal/accounts.md
 - ../ragbot-data/datasets/personal/contact-info.md
 - ../ragbot-data/datasets/personal/personal-family.md
 - ../ragbot-data/workspaces/my-employer/company.md
Using AI engine openai with model gpt-4o
[redacted in this example]
```

Example 2:

```console
rajivpant@RP-2021-MacBook-Pro ragbot % ./ragbot.py -d instructions/ datasets/public/ -p "Write a short resume of Rajiv" 
datasets being used:
 - instructions/
 - datasets/public/travel-food.md
 - datasets/public/employment-history.md
 - datasets/public/about.md
 - datasets/public/biography.md
Using AI engine openai with model gpt-4o
[truncated in this example]
```

Example 3:

```console
./ragbot.py -p "Tell me a story about a brave knight and a wise wizard." -d datasets/story_characters
```

### Interactive mode

To use Ragbot.AI in interactive mode, use the `-i` or `--interactive` flag without providing a prompt via command line or input file. In this mode, you can enter follow-up prompts after each response.

Example:

```console
./ragbot.py -i -d datasets/story_characters
```

In the first example, Ragbot.AI generates a short note in Rajiv's voice using the dataset files in the `../ragbot-data/datasets` folder. In the second example, Ragbot.AI provides information on good practices for software development using the `datasets/software_development.txt` dataset file. In the third example, Ragbot.AI tells a story about a brave knight and a wise wizard using the dataset files in the `datasets/story_characters` folder.

### Using Ragbot.AI to suggest changes to its own code!

```console
rajivpant@RP-2021-MacBook-Pro ragbot % ./ragbot.py -d ragbot.py -p "if no dataset files are being used, then I want the code to show that."
datasets being used:
 - ragbot.py
Using AI engine openai with model gpt-4o
To modify the code to show a message when no dataset files are being used, you can add an else statement after checking for the dataset files. Update the code in the `main()` function as follows:

\```python
if curated_dataset_files:
    print("datasets being used:")
    for file in curated_dataset_files:
        print(f" - {file}")
else:
    print("No dataset files are being used.")
\```

This will print "No dataset files are being used." when there are no dataset files detected.
rajivpant@RP-2021-MacBook-Pro ragbot % 

```

### Examples of using with Linux/Unix pipes via the command line

Asking it to guess what some of the dataset files I use are for

```console
rajivpant@RP-2021-MacBook-Pro ragbot % find datasets ../ragbot-data/datasets -print | ./ragbot.py -d instructions/ datasets/public/ ../ragbot-data/datasets/personal/ ../ragbot-data/workspaces/my-employer/ -p "What do you guess these files are for?" 
datasets being used:
 - instructions/
 - datasets/public/travel-food.md
 - datasets/public/employment-history.md
 - datasets/public/about.md
 - datasets/public/biography.md
 - ../ragbot-data/datasets/personal/accounts.md
 - ../ragbot-data/datasets/personal/contact-info.md
 - ../ragbot-data/datasets/personal/personal-family.md
 - ../ragbot-data/workspaces/my-employer/company.md
Using AI engine openai with model gpt-4o
These files appear to be related to the datasets of an AI system, likely for generating text or providing assistance based on the provided information. The files seem to be divided into two categories: public and private.

Public files:
- datasets/public/travel-food.md: Rajiv's travel and food preferences
- datasets/public/employment-history.md: Rajiv's employment history
- datasets/public/about.md: General information about Rajiv
- datasets/public/biography.md: Biography of Rajiv

Private files (stored in a separate private folder):
- datasets/personal/accounts.md: Semi-private personal account information, such as frequent flyer numbers or loyalty programs. Does not contain any confidential or sensitive information.
- datasets/personal/contact-info.md: Personal contact information, such as phone numbers and email addresses. Does not contain any confidential or sensitive information.
- datasets/personal/personal-family.md: Personal and family information, such as family members and relationships. Does not contain any confidential or sensitive information.

Workspace-specific files:
- workspaces/my-employer/company.md: Non-confidential, publicly available information related to the employer, including your role

Overall, these files seem to contain various information about a person, their preferences, and professional background, likely used to tailor the AI system's responses and assistance.
rajivpant@RP-2021-MacBook-Pro ragbot % 
```

Asking technical questions about a project

> ❗️ In the current version of Ragbot.AI, the --stdin and --prompt options are mutually exclusive, so the following example no longer works as is. In a future update to this README file, I will give an alternate example to obtain the similar results.
```console
alexredmon@ar-macbook ~/s/scribe > cat docker-compose.yml | ragbot --stdin -p "which services will be exposed on which ports by running all services in the following docker-compose.yml file?" 
In the given docker-compose.yml file, the following services are exposed on their respective ports:
1. "scribe" service: - Exposed on port 80 - Exposed on port 9009 (mapped to internal port 9009)
2. "scribe-feature" service: - Exposed on port 80
3. "scribe-redis" service: - Exposed on port 6379 (mapped to internal port 6379)
alexredmon@ar-macbook ~/s/scribe >
```

</details>

### Just for fun

Using the Anthropic engine with the Claude Instant model

```console
rajivpant@RP-2021-MacBook-Pro ragbot % ./ragbot.py -e anthropic -m "claude-instant-v1" -p "Tell me 5 fun things to do in NYC."
No dataset files are being used.
Using AI engine anthropic with model claude-instant-v1
 Here are 5 fun things to do in NYC:

1. Visit Central Park. Walk the paths, rent a paddle boat, visit the zoo, catch a Shakespeare in the Park performance.

2. Catch a Broadway show. New York is the center of the theater world with some of the greatest plays and musicals on Broadway and off Broadway. 

3. Go to the top of the Empire State Building. Take in the panoramic views of all of NYC from one of its most famous landmarks. 

4. Shop and dine in SoHo and the West Village. Explore trendy boutique shops and dig into meals at charming sidewalk cafes.  

5. Take a free walking tour. There are numerous companies that offer guided walking tours of various NYC neighborhoods, covering history, culture, architecture and more.
rajivpant@RP-2021-MacBook-Pro ragbot % 
```


Random Creativity

> ❗️ In the current version of Ragbot.AI, the --stdin and --prompt options are mutually exclusive, so the following example no longer works as is. In a future update to this README file, I will give an alternate example to obtain the similar results.
```console
alexredmon@ar-macbook ~ > cat names.csv 
rajiv,
jim,
dennis,
alexandria
alexredmon@ar-macbook ~ > catnames.csv | ragbot.py --stdin -p "Generate a creative nickname for each of the following people" 
rajiv, Rajiv Razzle-Dazzle
jim, Jolly JimJam
dennis, Daring Denmaster
alexandria, All-Star Alexi
alexredmon@ar-macbook ~ >
```
