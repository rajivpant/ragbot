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


1.  Set up your personalized custom instuctions for rbot.

Create a `custom-instructions` folder containing files with your custom instructions that rbot should follow. The files int this folder contains the initial system instructions that set the context for the conversation. You can make a copy of the Rajiv's examples and modify those files to include any specific information or instructions you want to provide to rbot before starting the conversation.

To make a copy of Rajiv's own example custom instructions to modify for your own use, make a copy of the example folder for your own custom-instructions and then edit the files using a text or markdown editor.

```bash
cp -rp example-custom-instructions custom-instructions
```


2.  Set up your curated datasets for rbot.

Make a copy of Rajiv's sample files in the `example-curated-datasets/` folder to your own `curated-datasets/` folder. This folder contains files that provide additional context and information to rbot. You can replace these sample files with your own information that reflect your personal preferences, such as your job details, family information, travel and food preferences, or any other information you want rbot to be aware of.

    You can create new informational files or modify the existing ones to match your own needs. Each  file should contain relevant information related to a specific topic or aspect of your life. For example, you can create a `job-at-company-name.md` file to provide details about your work or a `hobbies.md` file to share information about your hobbies and interests.

    Make sure to follow the Markdown format when creating or modifying these files, as rbot relies on Markdown syntax to parse and process the information.

```bash
cp -rp example-curated-datasets curated-datasets
```

By personalizing the files in the `custom-instructions/` and the `curated-datasets/` folders with your own information, you can customize rbot to better understand your preferences and provide more accurate and relevant responses.

Remember to update the paths to your `custom-insturctions` and `curated-datasets` folders and files in the `.env` configuration file to ensure that rbot uses the correct files during conversations.

Feel free to experiment and iterate on your personalized files to refine the context and information provided to rbot, making it an even more personalized AI assistant.

Now, rbot is configured, personalized, and ready to be run!