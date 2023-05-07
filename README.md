# rbot
🤖 rbot: Rajiv's chatbot utilizing the GPT-4 model to offer engaging conversations with a personalized touch and advanced context understanding.
🚀 Rajiv's GPT-4 based chatbot that processes user prompts and custom conversation decorators, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.
🧠 Custom conversation decorators help the chatbot better understand the context, resulting in more accurate and relevant responses, surpassing the capabilities of standard GPT-4 implementations.

This repository contains two versions of the chatbot:
1. A fully functional command line version (`rbot.py`)
2. A work-in-progress Django-based web application

## Prerequisites

The environment variable `OPENAI_API_KEY` needs to be set in your shell for this application to work. The instructions for doing that can be found at [OpenAI's Support Page for Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety).

## Installation

No installation is required for the command line version `rbot.py`. Simply clone this repository and ensure you have Python 3.x installed on your system.

The Web page based application built using Django requires setup and configuration. Instructions for the Django-based web application will be provided upon its completion.

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

