#!/usr/bin/env python3

# rbot.py - https://github.com/rajivpant/rbot
# Developed by Rajiv Pant (https://github.com/rajivpant)
# The first version was inspired by 
# - Jim Mortko (https://github.com/jskills)
# - Alexandria Redmon (https://github.com/alexdredmon)
#
# 🤖 rbot: Rajiv's chatbot utilizing OpenAI's GPT and Anthropic's Claude models 
# to offer engaging conversations
# with a personalized touch and advanced context understanding.
#
# 🚀 Rajiv's GPT-4 based chatbot processes user prompts and custom conversation decorators,
# enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.
#
# 🧠 Custom conversation decorators help the chatbot better understand the context,
# resulting in more accurate and relevant responses, surpassing the capabilities of
# out of the box GPT-4 implementations.


import glob
import os
import sys
import argparse
import re
import yaml
import json
import openai
import anthropic


# Function to load configuration from YAML
def load_config(config_file):
    with open(config_file, 'r') as stream:
        return yaml.safe_load(stream)

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
engine_choices = list(engines_config.keys())


def chat(
    prompt,
    decorators,
    model,
    max_tokens=1000,
    stream=True,
    request_timeout=15,
    temperature=0.75,
    history=None,
    engine="openai",
):
    """
    Send a request to the OpenAI or Anthropic API with the provided prompt and decorators.

    :param prompt: The user's input to generate a response for.
    :param decorators: A list of decorators to provide context for the model.
    :param model: The name of the GPT model to use.
    :param max_tokens: The maximum number of tokens to generate in the response (default is 1000).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response, with higher values being more creative (default is 0.75).
    :param history: The conversation history, if available (default is None).
    :param engine: The engine to use for the chat, 'openai' or 'anthropic' (default is 'openai').
    :return: The generated response text from the model.
    """
    if engine == "openai":
        # Configure the arguments for the OpenAI API
        args = {
            "max_tokens": max_tokens,
            "model": model,
            "request_timeout": request_timeout,
            "stream": stream,
            "temperature": temperature,
        }
        # If conversation history is provided, pass it to the API
        if history:
            args["messages"] = history
        else:
            # If no history is provided, construct it from the decorators
            history = []
            for decorator in decorators:
                history.append(
                    {
                        "role": "system",
                        "content": decorator,
                    }
                )
            # Add the user's prompt to the history
            history.append({"role": "user", "content": prompt})
            args["messages"] = history

        # Call the OpenAI API and build the response
        completion_method = openai.ChatCompletion.create
        response = ""
        for token in completion_method(**args):
            text = token["choices"][0]["delta"].get("content")
            if text:
                response += text
        return response
    elif engine == "anthropic":
        # Call the Anthropic API
        c = anthropic.Client(anthropic.api_key)
        resp = c.completion(
            prompt=f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}",
            stop_sequences=[anthropic.HUMAN_PROMPT],
            model=model,
            max_tokens_to_sample=max_tokens,
        )
        return resp

def main():
    parser = argparse.ArgumentParser(
        description="A GPT-4 or Anthropic Claude based chatbot that generates responses based on user prompts."
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
        help="Enable interactive assistant chatbot mode.",
    )
    parser.add_argument(
        "-d", "--decorator", nargs='*', default=[],
        help="Path to the conversation decorator file or folder. Can accept multiple values."
    )
    parser.add_argument(
    "-l",
    "--load",
    help="Load a previous session from a file.",
    )
    parser.add_argument(
        "-e",
        "--engine",
        default=config.get('default', 'openai'),
        choices=engine_choices,
        help="The engine to use for the chat.",
    )
    parser.add_argument(
        "-m",
        "--model",
        help="The model to use for the chat. Defaults to engine's default model.",
    )
    known_args = parser.parse_known_args()
    args = known_args[0]

    decorators = []
    decorator_files = []  # to store file names of decorators
    for decorator_path in args.decorator:
        if os.path.isfile(decorator_path):
            with open(decorator_path, "r") as file:
                decorators.append(file.read())
                decorator_files.append(decorator_path)  # save file name
        elif os.path.isdir(decorator_path):
            for filepath in glob.glob(os.path.join(decorator_path, "*")):
                with open(filepath, "r") as file:
                    decorators.append(file.read())
                    decorator_files.append(filepath)  # save file name

    print("Decorators being used:")
    for file in decorator_files:
        print(f" - {file}")

    history = []
    for decorator in decorators:
        history.append(
            {
                "role": "system",
                "content": decorator,
            }
        )
    if args.load:
        with open(args.load, 'r') as f:
            history = json.load(f)
    model = args.model
    if model is None:
        model = engines_config[args.engine]['default_model']

    # Get the engine API key from environment variable
    api_key_name = engines_config[args.engine].get('api_key_name')
    if api_key_name:
        engines_config[args.engine]['api_key'] = os.getenv(api_key_name)

    if args.engine == 'openai':
        openai.api_key = engines_config[args.engine]['api_key']
    elif args.engine == 'anthropic':
        anthropic.api_key = engines_config[args.engine]['api_key']

    print(f"Using AI engine {args.engine} with model: {model}")


    if args.interactive:
        print("Entering interactive mode.")
        while True:
            prompt = input("Enter prompt below. /quit to exit or /save file_name.json to save conversation.\n> ")
            if prompt.lower() == "/quit":
                break
            elif prompt.lower().startswith("/save "):
                filename = prompt[5:]
                with open(filename, 'w') as f:
                    json.dump(history, f)
                print(f"Conversation saved to {filename}")
                continue
            history.append({"role": "user", "content": prompt})
            reply = chat(prompt=prompt, decorators=decorators, history=history, engine=args.engine, model=model)
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
        reply = chat(prompt=prompt, decorators=decorators, history=history, engine=args.engine, model=model)
        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()
        print(reply)

if __name__ == "__main__":
    main()
