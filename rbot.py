#!/usr/local/bin/python

# rbot.py - https://github.com/rajivpant/rbot
# Developed by Rajiv Pant (https://github.com/rajivpant)
# Inspired by prior work done by Jim Mortko (https://github.com/jskills) and Alexandria Redmon (https://github.com/alexdredmon)
#
# 🤖 rbot: Rajiv's chatbot utilizing the GPT-4 model to offer engaging conversations with a personalized touch and advanced context understanding.
#
# 🚀 Rajiv's GPT-4 based chatbot processes user prompts and custom conversation decorators,
# enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.
#
# 🧠 Custom conversation decorators help the chatbot better understand the context,
# resulting in more accurate and relevant responses, surpassing the capabilities of standard GPT-4 implementations.

import os
import sys
import argparse
import openai
import glob

# Load the OpenAI API key from an environment variable or secret management service
openai.api_key = os.getenv("OPENAI_API_KEY")


def chat(prompt, decorators, model='gpt-4', max_tokens=1000, stream=True, request_timeout=15, temperature=0.75):
    """
    Send a request to the OpenAI API with the provided prompt and decorators.

    :param prompt: The user's input to generate a response for.
    :param decorators: A list of decorators to provide context for the model.
    :param model: The name of the GPT model to use (default is 'gpt-4').
    :param max_tokens: The maximum number of tokens to generate in the response (default is 1000).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response, with higher values being more creative (default is 0.75).
    :return: The generated response text from the model.
    """
    # Initialize the conversation history
    history = []

    # Add decorators as system messages
    for decorator in decorators:
        history.append({
            'role': 'system',
            'content': decorator,
        })

    # Add the user's prompt as a user message
    history.append({
        'role': 'user',
        'content': prompt
    })

    # Prepare the API request arguments
    args = {
        'max_tokens': max_tokens,
        'model': model,
        'request_timeout': request_timeout,
        'stream': stream,
        'temperature': temperature,
        'messages': history
    }

    # Call the OpenAI API
    completion_method = openai.ChatCompletion.create

    response = ''

    # Collect the generated text from the response
    for token in completion_method(**args):
        text = token['choices'][0]['delta'].get('content')
        if text:
            response += text

    return response


def main():
    # Set up the command line argument parser
    parser = argparse.ArgumentParser(description="A GPT-4 based chatbot that generates responses based on user prompts.")
    parser.add_argument('-p', '--prompt', required=True, help="The user's input to generate a response for.")
    parser.add_argument('-d', '--decorator', help="Path to the conversation decorator file or folder.")
    args = parser.parse_args()

    # Initialize the decorators list
    decorators = []

    # Load the decorator(s) from file or folder
    if args.decorator:
        if os.path.isfile(args.decorator):
            with open(args.decorator, 'r') as file:
                decorators.append(file.read())
        elif os.path.isdir(args.decorator):
            for filepath in glob.glob(os.path.join(args.decorator, '*')):
                with open(filepath, 'r') as file:
                    decorators.append(file.read())

    # Generate the response using the prompt and decorators
    reply = chat(prompt=args.prompt, decorators=decorators)

    # Print the response
    print(reply)


if __name__ == "__main__":
    main()
