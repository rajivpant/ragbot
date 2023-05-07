#!/usr/local/bin/python

# rbot.py
# Developed by Rajiv Pant (https://github.com/rajivpant)
# Inspired by prior work done by Jim Mortko (https://github.com/jskills) and Alexandria Redmon (https://github.com/alexdredmon)


import os
import sys
import argparse
import openai

# Load the OpenAI API key from an environment variable or secret management service
openai.api_key = os.getenv("OPENAI_API_KEY")


def chat(prompt,
         history=None,
         conversation_decorator=None,
         model='gpt-4',
         max_tokens=1000,
         stream=True,
         request_timeout=15,
         temperature=0.75):
    """
    Send a request to the OpenAI API with the provided prompt and optional parameters.

    :param prompt: The user's input to generate a response for.
    :param history: A list of prior messages in the conversation, if any.
    :param conversation_decorator: Additional context to provide for the model.
    :param model: The name of the GPT model to use (default is 'gpt-4').
    :param max_tokens: The maximum number of tokens to generate in the response (default is 1000).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response, with higher values being more creative (default is 0.75).
    :return: The generated response text from the model.
    """
    if history is None:
        history = []

    if conversation_decorator and not history:
        history.append({
            'role': 'system',
            'content': conversation_decorator,
        })

    history = history + [{
        'role': 'user',
        'content': prompt
    }]

    args = {
        'max_tokens': max_tokens,
        'model': model,
        'request_timeout': request_timeout,
        'stream': stream,
        'temperature': temperature,
        'messages': history
    }

    completion_method = openai.ChatCompletion.create

    response = ''

    for token in completion_method(**args):
        text = token['choices'][0]['delta'].get('content')
        if text:
            response += text

    return response


def main():
    parser = argparse.ArgumentParser(description="A GPT-4 based chatbot that generates responses based on user prompts.")
    parser.add_argument('-p', '--prompt', required=True, help="The user's input to generate a response for.")
    parser.add_argument('-d', '--decorator', help="Path to the conversation decorator file.")
    args = parser.parse_args()

    if args.decorator:
        with open(args.decorator, 'r') as file:
            conversation_decorator = file.read()
    else:
        conversation_decorator = None

    reply = chat(prompt=args.prompt, conversation_decorator=conversation_decorator)

    print(reply)


if __name__ == "__main__":
    main()
