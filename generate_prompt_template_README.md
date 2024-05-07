# Generate Prompt Template

`generate_prompt_template.py` is a Python script that generates a prompt template for AI assistants by concatenating custom instructions and curated datasets for a given profile as defined in your Ragbot.AI configuration. The script is designed to help you create personalized and context-aware prompts for use with the standard web UIs of ChatGPT, Anthropic Claude Chat, Google Gemini, and others, enhancing the effectiveness and reliability of the AI's responses.

## Features

- Concatenates custom instruction files and curated dataset files for a profile into a single prompt template that can be copied and pasted into the standard web UIs of ChatGPT, Anthropic Claude Chat, Google Gemini, and others
- Generates a prompt template with placeholders for the user query, i.e. main prompt
- Provides guidelines for the AI assistant to follow when responding to queries
- Customizable and reusable for various AI assistants and use cases

## Prerequisites

- Python 3.x installed on your system

## Usage

```bash
./generate_prompt_template.py -h
```

```text
usage: generate_prompt_template.py [-h] --profile {Rajiv Personal,Rajiv
                                   Project 1,Rajiv Project 2,Ragbot Source
                                   Code} --output OUTPUT

Generates a prompt template for AI assistants.

options:
  -h, --help            show this help message and exit
  --profile {Rajiv Personal,Rajiv Project 1,Rajiv Project 2,Ragbot Source Code}
                        Name of the profile to use.
  --output OUTPUT       Output file name for the prompt template.
```

1. Prepare your custom instruction files and curated dataset files in markdown format (`.md`).

2. Open a terminal and navigate to the directory containing the `generate_prompt_template.py` script.

3. Run the script with the command-line arguments as described above.

4. The script will concatenate the contents of the markdown files found in the specified directories and generate a prompt template with placeholders for user queries.

5. The generated prompt template will be saved to the specified output file.

6. Open the output file and copy the entire prompt template.

7. Paste the prompt template into your AI assistant or chatbot interface.

8. Replace `[User Query Here]` with your specific question or request.

9. The AI assistant will now have access to the custom instructions and curated datasets within the prompt template, providing more informed and personalized responses based on the provided context.

## Benefits

- Enhances the effectiveness of AI assistants by providing them with custom instructions and curated datasets specific to your domain or use case.
- Saves time and effort in manually composing prompt templates for each interaction with the AI assistant.
- Allows for easy maintenance and updating of custom instructions and datasets by separating them into individual files.
- Promotes consistency and accuracy in AI responses by providing guidelines and context through the prompt template.
- Facilitates collaboration and sharing of prompt templates among team members or the wider community.

## Customization

You can customize the `generate_prompt_template.py` script to fit your specific needs:

- Modify the prompt template in the `generate_prompt_template` function to include additional guidelines or placeholders.
- Adjust the file extension (currently `.md`) in the `concatenate_files` function to support other file formats.
- Extend the script to handle additional command-line arguments or options based on your requirements.

## Contributing

If you encounter any issues, have suggestions for improvements, or would like to contribute to the development of `generate_prompt_template.py`, please feel free to open an issue or submit a pull request on the [RagBot.AI GitHub repository](https://github.com/rajivpant/ragbot).

## License

This script is released under the [MIT License](LICENSE.md).
