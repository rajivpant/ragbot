#!/usr/bin/env python3

# rbot.py - https://github.com/rajivpant/rbot
# Developed by Rajiv Pant (https://github.com/rajivpant)
# The first version was inspired by Jim Mortko (https://github.com/jskills) and Alexandria Redmon (https://github.com/alexdredmon)
#
# 🤖 rbot: Rajiv's chatbot utilizing the GPT-4 model to offer engaging conversations with a personalized touch and advanced context understanding.
#
# 🚀 Rajiv's GPT-4 based chatbot processes user prompts and custom conversation decorators,
# enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.
#
# 🧠 Custom conversation decorators help the chatbot better understand the context,
# resulting in more accurate and relevant responses, surpassing the capabilities of standard GPT-4 implementations.

import glob
import os
import sys
import argparse
import openai
import re
import json

# Load the OpenAI API key from an environment variable or secret management service
openai.api_key = os.getenv("OPENAI_API_KEY")

def chat(
    prompt,
    decorators,
    model="gpt-4",
    max_tokens=1000,
    stream=True,
    request_timeout=15,
    temperature=0.75,
    history=None,
):
    """
    Send a request to the OpenAI API with the provided prompt and decorators.

    :param prompt: The user's input to generate a response for.
    :param decorators: A list of decorators to provide context for the model.
    :param model: The name of the GPT model to use (default is 'gpt-4').
    :param max_tokens: The maximum number of tokens to generate in the response (default is 1000).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response, with higher values being more creative (default is 0.75).
    :param history: The conversation history, if available (default is None).
    :return: The generated response text from the model.
    """
    # Prepare the API request arguments
    args = {
        "max_tokens": max_tokens,
        "model": model,
        "request_timeout": request_timeout,
        "stream": stream,
        "temperature": temperature,
    }

    if history:
        args["messages"] = history
    else:
        # Initialize the conversation history
        history = []

        # Add decorators as system messages
        for decorator in decorators:
            history.append(
                {
                    "role": "system",
                    "content": decorator,
                }
            )

        # Add the user's prompt as a user message
        history.append({"role": "user", "content": prompt})

        args["messages"] = history

    # Call the OpenAI API
    completion_method = openai.ChatCompletion.create

    response = ""

    # Collect the generated text from the response
    for token in completion_method(**args):
        text = token["choices"][0]["delta"].get("content")
        if text:
            response += text

    return response

def main():
    # Set up the command line argument parser
    parser = argparse.ArgumentParser(
        description="A GPT-4 based chatbot that generates responses based on user prompts."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-p", "--prompt", help="The user's input to generate a response for."
    )
    group.add_argument(
        "-f",
        "--prompt_file",
        help="The file containing the user's input to generate a response for.",
    )
    group.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enable interactive chatbot mode.",
    )
    parser.add_argument(
        "-d", "--decorator", help="Path to the conversation decorator file or folder."
    )
    parser.add_argument(
    "-l",
    "--load",
    help="Load a previous session from a file.",
    )
    known_args = parser.parse_known_args()
    args = known_args[0]

    # Initialize the decorators list
    decorators = []

    # Load the decorator(s) from file or folder
    if args.decorator:
        if os.path.isfile(args.decorator):
            with open(args.decorator, "r") as file:
                decorators.append(file.read())
        elif os.path.isdir(args.decorator):
            for filepath in glob.glob(os.path.join(args.decorator, "*")):
                with open(filepath, "r") as file:
                    decorators.append(file.read())

    # Initialize the conversation history
    history = []

    # Add decorators as system messages
    for decorator in decorators:
        history.append(
            {
                "role": "system",
                "content": decorator,
            }
        )

    # Load the conversation history from a file if requested
    if args.load:
        with open(args.load, 'r') as f:
            history = json.load(f)

    if args.interactive:
        print("Entering interactive mode. Type 'quit' to exit.")
        while True:
            prompt = input("User prompt: ")
            if prompt.lower() == "quit":
                break
            elif prompt.lower().startswith("save "):
                filename = prompt[5:]
                with open(filename, 'w') as f:
                    json.dump(history, f)
                print(f"Conversation saved to {filename}")
                continue

            history.append({"role": "user", "content": prompt})

            # Generate the response using the prompt and decorators
            reply = chat(prompt=prompt, decorators=decorators, history=history)

            history.append({"role": "assistant", "content": reply})

            print(f"rbot: {reply}")
    else:
        prompt = args.prompt
        if not sys.stdin.isatty():
            stdin = sys.stdin.readlines()
            if stdin:
                piped_input = "".join(stdin).strip()
                prompt = (
                    prompt
                    + f"""\n\n\nINPUT = \"\"\"
{piped_input}
\"\"\"\n
"""
                )

        history.append({"role": "user", "content": prompt})

        # Generate the response using the prompt and decorators
        reply = chat(prompt=prompt, decorators=decorators, history=history)

        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()

        # Print the response
        print(reply)

if __name__ == "__main__":
    main()
