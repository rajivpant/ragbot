Configuration and personalization instructions for RagBot.AI
============================================================

### Configuring RagBot.AI
If you haven't already downloaded and installed RagBot.AI, read the [installation guide](INSTALL.md).

After successfully installing the dependencies, RagBot.AI needs to be configured with API keys.

1.  Create the synthesis-engineering shared config directory:

```bash
mkdir -p ~/.synthesis
```

2.  Create the API keys file:

```bash
cat > ~/.synthesis/keys.yaml << 'EOF'
# Synthesis API Keys (shared across synthesis-engineering products: ragbot, ragenie, etc.)
default:
  anthropic: "sk-ant-your-key-here"
  openai: "sk-your-key-here"
  google: "your-gemini-key-here"
EOF
chmod 600 ~/.synthesis/keys.yaml
```

3.  Edit `~/.synthesis/keys.yaml` with your actual API keys.

* * * * *

Remember, the keys file contains sensitive information such as API keys, so it should never be shared or published. The file is stored in your home directory at `~/.synthesis/` and is NOT part of the ragbot repository.

The legacy location `~/.config/ragbot/keys.yaml` continues to work as a fallback if `~/.synthesis/keys.yaml` does not exist.

### Configuring the vector backend (pgvector)

Ragbot's default vector store is PostgreSQL with the `pgvector` extension. For Docker Compose users, the database container starts automatically (see [README-DOCKER.md](README-DOCKER.md)).

For native CLI use, point ragbot at any reachable Postgres instance:

```bash
# 1. Install pgvector for your Postgres (example: PostgreSQL 16 via Homebrew)
brew install postgresql@16
brew services start postgresql@16
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector && PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make && PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config make install

# 2. Create the ragbot database and enable the extension
createuser -s ragbot
createdb -O ragbot ragbot
psql -U ragbot -d ragbot -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Point ragbot at it
export RAGBOT_DATABASE_URL=postgresql://ragbot:CHANGE_ME@localhost:5432/ragbot

# 4. Verify
ragbot db status
```

To run on the legacy embedded Qdrant backend instead, set `RAGBOT_VECTOR_BACKEND=qdrant`. No database setup needed; Qdrant data is stored under `$QDRANT_PATH` (default `/app/qdrant_data` in containers).

### Discovering and indexing Agent Skills

Ragbot reads Agent Skills (directories containing `SKILL.md`) as first-class content. The full directory tree is honoured — `references/**/*.md` and bundled scripts are all indexed and queryable via RAG.

```bash
ragbot skills list                          # show discovered skills
ragbot skills info <skill-name>             # inspect a specific skill
ragbot skills index                         # index every skill into the 'skills' workspace
ragbot skills index --only synthesis-foo    # narrow to one skill
ragbot skills index --force                 # clear and re-index
```

Default discovery roots:

1. `~/.synthesis/skills/`            (shared install for synthesis-engineering tools)
2. `~/.claude/skills/`                (Claude Code private)
3. `~/.claude/plugins/cache/*/skills/` (plugin-installed)
4. Per-workspace roots from `compile-config.yaml` `sources.skills.roots`

When the `skills` workspace has indexed content, `ragbot chat` automatically merges its results with the user's selected workspace. Override per-call with `--no-skills` (opt out) or `--workspace foo --workspace bar` (explicit list).

### Reasoning / thinking modes

Flagship models with thinking support (Claude Opus 4.7, GPT-5.5-pro, Gemini 3.1 Pro) automatically use `reasoning_effort: medium`. Non-flagship thinking-capable models (Claude Sonnet 4.6, GPT-5.5, etc.) default to off but accept overrides. Models without a `thinking` block in `engines.yaml` (e.g., Claude Haiku 4.5, GPT-5.4-mini) silently ignore the parameter.

```bash
# Per-call override
ragbot chat --thinking-effort high -p "explain this..."

# Globally
export RAGBOT_THINKING_EFFORT=low

# Disable on a flagship model
ragbot chat --thinking-effort off -p "..."
```

LiteLLM normalises `reasoning_effort` per provider — Claude 4.x receives `thinking={"type": "adaptive"}`, OpenAI receives `reasoning_effort` directly, Gemini receives the corresponding thinking level.

### Running RagBot.AI

1.  View the RagBot.AI help file to see how to use its capabilities:

Command line version rbot.py
```bash
./rbot --help
```

2. Run rbot to execute a prompt including knowledge from a file. (We'll personalize this later with your own data.)
```bash
./rbot -p "What is RagBot.AI?" -d ./README.md
```

```bash
./rbot -p "Why should I use RagBot.AI?" -d ./README.md
```

You can also specify the model which you wish to use:

```bash
./rbot -p "Why should I use RagBot.AI?" -d ./README.md -m gpt-4
```

You can also run RagBot.AI in a web browser locally on your computer:

```bash
./rbot-web
```
![](screenshots/Screenshot%202024-04-10%20at%2010.46.02 PM.png)

Read the [main documentation](README.md) for examples and more information about RagBot.AI.

### Personalizing RagBot.AI

To personalize RagBot.AI and make it reflect your own user preferences, you can follow the steps below:

#### Where to Store Your Ragbot.AI Data

Ragbot.AI uses a dedicated folder to store your custom instructions, datasets, and any saved prompts or conversations. This data may contain personal or sensitive information, so choosing a secure location is crucial.

Here's how to determine the default data storage location for your operating system:

-   macOS/Linux: `~/ragbot-data` (This translates to a folder named `ragbot-data` within your home directory.)
-   Windows: `%USERPROFILE%\ragbot-data` (This translates to a folder named `ragbot-data` within your user profile directory.)

#### Important Considerations for Data Storage

-   Version Control: If you intend to use version control systems like Git to manage your `ragbot-data` folder, it's highly recommended to avoid placing it within a directory that is synchronized with cloud storage services such as iCloud, Dropbox, OneDrive, or similar. Cloud syncing can lead to conflicts and unexpected behavior with version control.

-   Cloud Backups (Optional): If you prefer having cloud-based backups of your Ragbot.AI data and are not using version control, you may choose to place the `ragbot-data` folder within a directory that is synchronized with your preferred cloud storage provider. This ensures your data is backed up and accessible from multiple devices.

#### Organizing Your Ragbot.AI Data

Within the `ragbot-data` folder, it's recommended to create subfolders to organize your custom instructions and datasets:

-   `instructions`: This subfolder will hold your custom instruction files in Markdown format (`.md`). These files provide Ragbot.AI with guidelines and preferences for its responses.
-   `datasets`: This subfolder will contain your dataset files, also in Markdown format. These files offer contextual information and knowledge to Ragbot.AI, allowing it to generate more relevant and informed responses.

Remember: Always prioritize the security and privacy of your Ragbot.AI data by choosing a storage location that aligns with your needs and security preferences.


1.  Set up your personalized custom instuctions for rbot.

Create a `instructions` folder containing files with your custom instructions that RagBot.AI should follow. The files int this folder contains the initial system instructions that set the context for the conversation. You can make a copy of the Rajiv's examples and modify those files to include any specific information or instructions you want to provide to RagBot.AI before starting the conversation.

To make a copy of Rajiv's own example custom instructions to modify for your own use, make a copy of the example folder for your own instructions and then edit the files using a text or markdown editor.

```bash
cp -rp examples/templates/instructions/starter instructions
```


2.  Set up your datasets for RagBot.AI.

Make a copy of Rajiv's sample files in the `examples/templates/datasets/starter/` folder to your own `datasets/` folder. This folder contains files that provide additional context and information to RagBot.AI. You can replace these sample files with your own information that reflect your personal preferences, such as your job details, family information, travel and food preferences, or any other information you want RagBot.AI to be aware of.

You can create new informational files or modify the existing ones to match your own needs. Each  file should contain relevant information related to a specific topic or aspect of your life. For example, you can create a `job-at-company-name.md` file to provide details about your work or a `hobbies.md` file to share information about your hobbies and interests.

Make sure to follow the Markdown format when creating or modifying these files, as RagBot.AI relies on Markdown syntax to parse and process the information.

```bash
cp -rp examples/templates/datasets/starter datasets
```

By personalizing the files in the `instructions/` and the `datasets/` folders with your own information, you can customize RagBot.AI to better understand your preferences and provide more accurate and relevant responses.

Remember to update the paths to your `instructions` and `datasets` folders and files in the `.env` configuration file to ensure that RagBot.AI uses the correct files during conversations.

Feel free to experiment and iterate on your personalized files to refine the context and information provided to RagBot.AI, making it an even more personalized AI assistant.

Now, RagBot.AI is configured, personalized, and ready to be run!