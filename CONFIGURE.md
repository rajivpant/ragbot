Configuration and personalization instructions for rbot
=======================================================

### Configuring rbot
If you haven't already downloaded and installed rbot, read the [installation guide](INSTALL.md).

After successfully installing the dependencies, rbot needs to be configured using an environment file (.env). This file contains important configuration settings, such as API keys and the paths to decorator files.

1.  Navigate to the rbot directory (if not already there):

```bash
cd rbot
```

2.  Make a copy of the `example.env` file and name it `.env`:

```bash
cp example.env .env
```

3.  Open the `.env` file in your preferred text editor. Replace `<Your-OpenAI-API-Key>` and `<Your-Anthropic-API-Key>` with your actual API keys. Also, replace the sample paths inside `DECORATORS` with the paths to your decorator files or folders.

4.  Save the `.env` file and close it.

* * * * *

Remember, the `.env` file contains sensitive information such as API keys, so it should never be shared or published. Make sure to add `.env` to your `.gitignore` file to prevent it from being tracked by git.

### Running rbot

1.  View the rbot help file to see how to use its capabilities:

Command line version rbot.py
```bash
./rbot --help
```

2. Run rbot to execute a prompt including knowledge from a file. (We'll personalize this later with your own data.)
```bash
./rbot -p "What is rbot?" -d ./README.md
```

```bash
./rbot -p "Why should I use rbot?" -d ./README.md
```

You can also specify the model which you wish to use:

```bash
./rbot -p "Why should I use rbot?" -d ./README.md -m gpt-4
```

You can also run rbot in a web browser locally on your computer:

```bash
./rbot-web
```
![](screenshots/Cursor_and_rbot-streamlit_%C2%B7_Streamlit.png)

Read the [main documentation](README.md) for examples and more information about rbot.

### Personalizing rbot

To personalize rbot and make it reflect your own user preferences, you can follow the steps below:

1.  Edit the `1st-prompt-decorator.md` file: This file contains the initial system-level prompt that sets the context for the conversation. You can modify this file to include any specific information or instructions you want to provide to rbot before starting the conversation.

2.  Replace the sample files in the `fine-tuning/` folder: The `fine-tuning/` folder contains sample decorator files that provide additional context and information to rbot. You can replace these sample files with your own decorator files that reflect your personal preferences, such as your job details, family information, travel and food preferences, or any other information you want rbot to be aware of.

    You can create new decorator files or modify the existing ones to match your own needs. Each decorator file should contain relevant information related to a specific topic or aspect of your life. For example, you can create a `work.md` file to provide details about your work or a `hobbies.md` file to share information about your hobbies and interests.

    Make sure to follow the Markdown format when creating or modifying decorator files, as rbot relies on Markdown syntax to parse and process the information.

By personalizing the `1st-prompt-decorator.md` file and replacing the sample files in the `fine-tuning/` folder with your own decorator files, you can customize rbot to better understand your preferences and provide more accurate and relevant responses.

Remember to update the paths to your decorator files in the `.env` configuration file to ensure that rbot uses the correct files during conversations.

Feel free to experiment and iterate on your decorator files to refine the context and information provided to rbot, making it an even more personalized AI assistant.

Now, rbot is configured, personalized, and ready to be run!