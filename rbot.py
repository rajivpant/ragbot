#!/usr/bin/env python3
# rbot.py - https://github.com/rajivpant/rbot

import glob
import os
import sys
from dotenv import load_dotenv
import argparse
import re
import yaml
import json
import appdirs
import openai
import anthropic
from langchain.llms import OpenAI, OpenAIChat, Anthropic
# from langchain.chat_models.anthropic import ChatAnthropic
from helpers import load_curated_dataset_files, load_custom_instruction_files, load_config, print_saved_files, chat


appname = "rbot"
appauthor = "Rajiv Pant"

data_dir = appdirs.user_data_dir(appname, appauthor)
sessions_data_dir = os.path.join(data_dir, "sessions")



load_dotenv()  # Load environment variables from .env file


# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
engine_choices = list(engines_config.keys())

default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}

added_curated_datasets = False



def main():
    global added_curated_datasets

    parser = argparse.ArgumentParser(
        description="Ragbot.AI is an augmented brain and asistant. Learn more at https://ragbot.ai"
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "-ls",
        "--list-saved",
        action="store_true",
        help="List all the currently saved JSON files."
    )
    input_group2 = parser.add_mutually_exclusive_group()
    input_group2.add_argument(
        "-p", "--prompt", help="The user's input to generate a response for."
    )
    input_group2.add_argument(
        "-f",
        "--prompt_file",
        help="The file containing the user's input to generate a response for.",
    )
    input_group2.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enable interactive assistant chatbot mode.",
    )
    input_group2.add_argument(
        "--stdin",
        action="store_true",
        help="Read the user's input from stdin."
    )
    parser.add_argument(
        "-c", "--custom_instructions", nargs='*', default=[],
        help="Path to the prompt custom instructions file or folder. Can accept multiple values."
    )
    parser.add_argument(
        "-nc", "--nocusom_instructions",
        action="store_true",
        help="Ignore all prompt custom instructions even if they are specified."
    )
    parser.add_argument(
        "-d", "--curated_dataset", nargs='*', default=[],
        help="Path to the prompt context curated dataset file or folder. Can accept multiple values."
    )
    parser.add_argument(
        "-nd", "--nocurated_dataset",
        action="store_true",
        help="Ignore all prompt context curated dataset even if they are specified."
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
    parser.add_argument(
        "-t",
        "--temperature",
        type=float,
        default=None,
        help="The creativity of the response, with higher values being more creative.",
    )
    parser.add_argument(
    "-mt", "--max_tokens",
    type=int,
    default=None,
    help="The maximum number of tokens to generate in the response.",
    )
    parser.add_argument(
        "-l",
        "--load",
        help="Load a previous interactive session from a file.",
    )

    known_args = parser.parse_known_args()
    args = known_args[0]

    if args.list_saved:
        print_saved_files(data_dir)
        return

    new_session = False  # Variable to track if this is a new session

    if args.load:
        args.interactive = True  # Automatically enable interactive mode when loading a session
        args.nocurated_dataset = True  # Do not load curated_dataset files when loading a session
    else:
        new_session = True  # This is a new session

    curated_datasets = []
    curated_dataset_files = []  # to store file names of curated_datasets

    if not args.custom_instructions:
        # Load default custom_instructions from .env file
        default_custom_instructions_paths = os.getenv("CUSTOM_INSTRUCTIONS", "").split("\n")
        default_custom_instructions_paths = [path for path in default_custom_instructions_paths if path.strip() != '']
        custom_instructions, custom_instructions_files = load_custom_instruction_files(default_custom_instructions_paths + args.curated_dataset)

    if custom_instructions_files:
        print("Custom instructions being used:")
        for file in custom_instructions_files:
            print(f" - {file}")
    else:
        print("No custom instructions files are being used.")

    if not args.nocurated_dataset:
        # Load default curated_datasets from .env file
        default_curated_dataset_paths = os.getenv("CURATED_DATASETS", "").split("\n")
        default_curated_dataset_paths = [path for path in default_curated_dataset_paths if path.strip() != '']
        curated_datasets, curated_dataset_files = load_curated_dataset_files(default_curated_dataset_paths + args.curated_dataset)

    if curated_dataset_files:
        print("Curated datasets being used:")
        for file in curated_dataset_files:
            print(f" - {file}")
    else:
        print("No curated_dataset files are being used.")

    history = []
    for custom_instruction in custom_instructions:
        history.append(
            {
                "role": "system",
                "content": custom_instruction,
            }
        )

    for curated_dataset in curated_datasets:
        history.append(
            {
                "role": "system",
                "content": curated_dataset,
            }
        )

    if args.load:
        filename = args.load.strip()  # Remove leading and trailing spaces
        full_path = os.path.join(sessions_data_dir, filename)
        with open(full_path, 'r') as f:
            history = json.load(f)
        print(f"Continuing previously saved session from file: {filename}")

    model = args.model
    if model is None:
        model = default_models[args.engine]

    # Get the engine API key from environment variable
    api_key_name = engines_config[args.engine].get('api_key_name')
    if api_key_name:
        engines_config[args.engine]['api_key'] = os.getenv(api_key_name)

    if args.engine == 'openai':
        openai.api_key = engines_config[args.engine]['api_key']
    elif args.engine == 'anthropic':
        anthropic.api_key = engines_config[args.engine]['api_key']


    # Get the default max_tokens and temperature from the engines.yaml configuration
    selected_model = next((item for item in engines_config[args.engine]['models'] if item['name'] == model), None)
    if selected_model:
        default_temperature = selected_model['temperature']
        default_max_tokens = selected_model['max_tokens']
    else:
        default_temperature = 0.75
        default_max_tokens = 1024

    # Use the default values if not provided by the user
    max_tokens = args.max_tokens or default_max_tokens
    temperature = args.temperature or default_temperature

    print(f"Using AI engine {args.engine} with model {model}")
    print(f"Creativity temperature setting: {temperature}")
    print(f"Max tokens setting: {max_tokens}")

    if args.interactive:
        print("Entering interactive mode.")
        added_curated_datasets = False
        while True:
            prompt = input("\nEnter prompt below. /quit to exit or /save file_name.json to save conversation.\n> ")
            if prompt.lower() == "/quit":
                break
            elif prompt.lower().startswith("/save "):
                filename = prompt[6:].strip()  # Remove leading '/save ' and spaces
                full_path = os.path.join(sessions_data_dir, filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    json.dump(history, f)
                print(f"Conversation saved to {full_path}")
                continue
            history.append({"role": "user", "content": prompt})
            reply = chat(prompt=prompt, custom_instructions=custom_instructions, curated_datasets=curated_datasets, history=history, engine=args.engine, model=model, max_tokens=max_tokens, temperature=temperature, interactive=args.interactive, new_session=new_session)
            history.append({"role": "assistant", "content": reply})
            print(f"Ragbot.AI: {reply}")
            if new_session and args.engine == "anthropic":
                    added_curated_datasets = False  # Reset curated_datasets flag after each user prompt
            

    else:
        prompt = None
        if args.prompt:
            prompt = args.prompt
        elif args.prompt_file:
            with open(args.prompt_file, 'r') as f:
                prompt = f.read().strip()
        elif args.stdin:
            stdin = sys.stdin.readlines()
            if stdin:
                prompt = "".join(stdin).strip()

        if prompt is None:
            print("Error: No prompt provided. Please provide a prompt using -p, -f, or -i option.")
            sys.exit(1)

        history.append({"role": "user", "content": prompt})
        if args.engine == "anthropic":
            added_curated_datasets = False  # Reset curated_datasets flag before each user prompt

        reply = chat(prompt=prompt, custom_instructions=custom_instructions, curated_datasets=curated_datasets, history=history, engine=args.engine, model=model, max_tokens=max_tokens, temperature=temperature, interactive=args.interactive, new_session=new_session)
        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()
        print(reply)

if __name__ == "__main__":
    main()
