Configuration and personalization instructions for RagBot.AI
============================================================

### Configuring RagBot.AI
If you haven't already downloaded and installed RagBot.AI, read the [installation guide](INSTALL.md).

After successfully installing the dependencies, RagBot.AI needs to be configured with API keys.

1.  Create the configuration directory:

```bash
mkdir -p ~/.config/ragbot
```

2.  Create the API keys file:

```bash
cat > ~/.config/ragbot/keys.yaml << 'EOF'
# Ragbot API Keys
default:
  anthropic: "sk-ant-your-key-here"
  openai: "sk-your-key-here"
  google: "your-gemini-key-here"
EOF
chmod 600 ~/.config/ragbot/keys.yaml
```

3.  Edit `~/.config/ragbot/keys.yaml` with your actual API keys.

* * * * *

Remember, the keys file contains sensitive information such as API keys, so it should never be shared or published. The file is stored in your home directory at `~/.config/ragbot/` and is NOT part of the ragbot repository.

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