# rbot

Rajiv's chat bot utilizing the GPT-4 model to generate responses based on user prompts.

## Prerequisites

The environment variable `OPENAI_API_KEY` needs to be set in your shell for this application to work. The instructions for doing that can be found at [OpenAI's Support Page for Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

## Installation

No installation is required. Simply clone this repository and ensure you have Python 3.x installed on your system.

## Usage

To use the chatbot, run the `rbot.py` script from the command line with the following arguments:

- `-p`/`--prompt`: The user's input to generate a response for (required).
- `-d`/`--decorator`: Path to the conversation decorator file (optional).

### Example
```
./rbot.py -p "Show me an org chart of Rajiv and his colleagues." -d ../rajiv-llms/fine-tuning/example-client.md
```

## Acknowledgments

- Developed by Rajiv Pant (https://github.com/rajivpant).
- Inspired by prior work done by Jim Mortko (https://github.com/jskills) and Alexandria Redmon (https://github.com/alexdredmon).
