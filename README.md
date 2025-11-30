## 🚀 Ragbot & RaGenie: Two Products, One Ecosystem

**Ragbot continues active development** alongside **RaGenie**, its next-generation sibling. Both are open source and share the same data layer (ragbot-data).

### Choosing Between Ragbot and RaGenie

| Use Case | Recommendation |
|----------|----------------|
| Quick setup, CLI-focused workflow | **Ragbot** |
| Need advanced RAG with vector search | **RaGenie** |
| Prefer Streamlit simplicity | **Ragbot** |
| Need microservices architecture | **RaGenie** |
| Want both CLI and modern web UI | Use both! |

### RaGenie Overview

**RaGenie** ([www.ragenie.com](https://www.ragenie.com) | [www.ragenie.ai](https://www.ragenie.ai)) is a modern microservices platform that complements Ragbot:

| Feature | Ragbot (v1) | RaGenie (v2) |
|---------|-------------|--------------|
| Architecture | Monolithic Streamlit | Microservices (FastAPI + React) |
| Authentication | None | JWT OAuth2 with role-based access |
| Storage | File system | PostgreSQL + MinIO + Qdrant (vectors) |
| RAG | Manual prompt concatenation | Automatic embeddings with semantic search |
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

# 3. Copy starter templates
cp -r examples/templates/datasets/starter/ datasets/my-data/
cp examples/templates/instructions/starter/default-instructions.md instructions/

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

# 4. Organize your data
cp -r examples/templates/datasets/starter/* ~/ragbot-data/datasets/
cp examples/templates/instructions/starter/default-instructions.md ~/ragbot-data/instructions/

# 5. Configure API keys
cp .env.docker .env
# Edit .env with your API keys

# 6. Start Ragbot
docker-compose up -d
```

### What's Next?

- 📖 **New to Ragbot?** Check out [examples/README.md](examples/README.md) for templates and use cases
- 🎯 **Starter templates:** Copy from [examples/templates/](examples/templates/) to get started
- 📚 **Advanced techniques:** Explore the [library](examples/library/) for proven prompts and frameworks
- 🎓 **Understand the philosophy:** Read [docs/DATA_ORGANIZATION.md](docs/DATA_ORGANIZATION.md)
- 🐳 **Docker deployment:** See [README-DOCKER.md](README-DOCKER.md) for deployment guide
- 🤝 **Contributing safely:** Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing
- ⚙️ **Detailed setup:** Follow the [installation guide](INSTALL.md) and [configuration guide](CONFIGURE.md)

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


## Generate Prompt Template

`generate_prompt_template.py` is a Python script that generates a prompt template for AI assistants by concatenating instructions and datasets. It helps users create personalized and context-aware prompts to enhance the effectiveness of their AI-powered tools.

For detailed information on how to use `generate_prompt_template.py` and its benefits, please refer to the [Generate Prompt Template Guide](generate_prompt_template_README.md).


Using the command line interface
--------------------------------

### Command line usage: Getting help

```console
rajivpant@rp-2023-mac-mini ragbot % ./ragbot --help
usage: ragbot.py [-h] [-ls] [-p PROMPT | -f PROMPT_FILE | -i | --stdin]
                 [-profile PROFILE] [-c [CUSTOM_INSTRUCTIONS ...]] [-nc]
                 [-d [CURATED_DATASET ...]] [-nd]
                 [-e {openai,anthropic,google}] [-m MODEL] [-t TEMPERATURE]
                 [-mt MAX_TOKENS] [-l LOAD]

Ragbot.AI is an augmented brain and asistant. Learn more at https://ragbot.ai

options:
  -h, --help            show this help message and exit
  -ls, --list-saved     List all the currently saved JSON files.
  -p PROMPT, --prompt PROMPT
                        The user's input to generate a response for.
  -f PROMPT_FILE, --prompt_file PROMPT_FILE
                        The file containing the user's input to generate a
                        response for.
  -i, --interactive     Enable interactive assistant chatbot mode.
  --stdin               Read the user's input from stdin.
  -profile PROFILE, --profile PROFILE
                        Name of the profile to use.
  -c [CUSTOM_INSTRUCTIONS ...], --custom_instructions [CUSTOM_INSTRUCTIONS ...]
                        Path to the prompt custom instructions file or folder.
                        Can accept multiple values.
  -nc, --nocusom_instructions
                        Ignore all prompt custom instructions even if they are
                        specified.
  -d [CURATED_DATASET ...], --curated_dataset [CURATED_DATASET ...]
                        Path to the prompt context dataset file or
                        folder. Can accept multiple values.
  -nd, --nocurated_dataset
                        Ignore all prompt context dataset even if they
                        are specified.
  -e {openai,anthropic,google}, --engine {openai,anthropic,google}
                        The engine to use for the chat.
  -m MODEL, --model MODEL
                        The model to use for the chat. Defaults to engine's
                        default model.
  -t TEMPERATURE, --temperature TEMPERATURE
                        The creativity of the response, with higher values
                        being more creative.
  -mt MAX_TOKENS, --max_tokens MAX_TOKENS
                        The maximum number of tokens to generate in the
                        response.
  -l LOAD, --load LOAD  Load a previous interactive session from a file.
rajivpant@rp-2023-mac-mini ragbot % 
```

### Using dataset files

To use Ragbot.AI, you can provide dataset files and/or folders containing multiple dataset files. You can view examples of dataset files at <https://github.com/rajivpant/ragbot/tree/main/examples/templates/datasets>

Example 1:

```console
rajivpant@RP-2021-MacBook-Pro ragbot % ./ragbot.py -d instructions/ datasets/public/ ../ragbot-data/datasets/personal/ ../ragbot-data/workspaces/hearst/ -p "Write a short note in Rajiv's voice about Rajiv's job, coworkers, family members, and travel and food preferences for the person temporarily backfilling for his EA." 
datasets being used:
 - instructions/
 - datasets/public/travel-food.md
 - datasets/public/employment-history.md
 - datasets/public/about.md
 - datasets/public/biography.md
 - ../ragbot-data/datasets/personal/accounts.md
 - ../ragbot-data/datasets/personal/contact-info.md
 - ../ragbot-data/datasets/personal/personal-family.md
 - ../ragbot-data/workspaces/hearst/hearst.md
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
rajivpant@RP-2021-MacBook-Pro ragbot % find datasets ../ragbot-data/datasets -print | ./ragbot.py -d instructions/ datasets/public/ ../ragbot-data/datasets/personal/ ../ragbot-data/workspaces/hearst/ -p "What do you guess these files are for?" 
datasets being used:
 - instructions/
 - datasets/public/travel-food.md
 - datasets/public/employment-history.md
 - datasets/public/about.md
 - datasets/public/biography.md
 - ../ragbot-data/datasets/personal/accounts.md
 - ../ragbot-data/datasets/personal/contact-info.md
 - ../ragbot-data/datasets/personal/personal-family.md
 - ../ragbot-data/workspaces/hearst/hearst.md
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
- workspaces/hearst/hearst.md: Non-confidential, publicly available information related to the Hearst corporation, including Rajiv's role there

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
