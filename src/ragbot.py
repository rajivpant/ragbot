#!/usr/bin/env python3
# ragbot.py - https://github.com/rajivpant/ragbot

import os
import sys
from dotenv import load_dotenv
import argparse
import re
import json
import appdirs
import openai
import anthropic
import litellm
from helpers import load_files, load_config, print_saved_files, chat, load_profiles, load_workspaces_as_profiles

appname = "ragbot"
appauthor = "Rajiv Pant"

data_dir = appdirs.user_data_dir(appname, appauthor)
sessions_data_dir = os.path.join(data_dir, "sessions")

load_dotenv()  # Load environment variables from .env file

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
engine_choices = list(engines_config.keys())
default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}

model_cost_map = litellm.model_cost 

def main():
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
        "-profile",
        "--profile",
        help="Name of the profile to use.",
    )
    parser.add_argument(
        "-c", "--custom_instructions", nargs='*', default=[],
        help="Path to the prompt custom instructions file or folder. Can accept multiple values."
    )
    parser.add_argument(
        "-nc", "--nocustom_instructions",
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
        help="The model to use for the chat. Defaults to engine's default model. Use 'flagship' to select the engine's most powerful model.",
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

    # Load workspaces from ragbot-data directory
    # Priority: 1) RAGBOT_DATA_ROOT env var, 2) Docker /app, 3) local workspaces/, 4) sibling ragbot-data/
    data_root = os.getenv('RAGBOT_DATA_ROOT')

    if data_root is None:
        # Check common locations in order of priority
        if os.path.isdir('/app/workspaces'):
            # Docker deployment
            data_root = '/app'
        elif os.path.isdir('workspaces'):
            # Local workspaces directory (current working directory)
            data_root = '.'
        elif os.path.isdir('../ragbot-data/workspaces'):
            # Sibling ragbot-data directory (common development setup)
            data_root = '../ragbot-data'
        else:
            # Fallback - will result in empty workspaces list
            data_root = '.'

    profiles = load_workspaces_as_profiles(data_root)

    if args.profile:
        # Get instruction and dataset paths from selected workspace
        selected_profile_data = next((profile for profile in profiles if profile['name'] == args.profile), None)
        if not selected_profile_data:
            available_workspaces = [p['name'] for p in profiles]
            print(f"Error: Workspace '{args.profile}' not found.")
            print(f"Available workspaces: {', '.join(available_workspaces)}")
            sys.exit(1)
        custom_instruction_paths = selected_profile_data.get('instructions', [])
        curated_dataset_paths = selected_profile_data.get('datasets', [])
    else:
        custom_instruction_paths = []
        curated_dataset_paths = []


    if not args.custom_instructions:
        # Load default custom_instructions for profile
        default_custom_instructions_paths = custom_instruction_paths
        default_custom_instructions_paths = [path for path in default_custom_instructions_paths if path.strip() != '']
        custom_instructions, custom_instructions_files = load_files(file_paths=default_custom_instructions_paths + args.curated_dataset, file_type="custom_instructions")

    if custom_instructions_files:
        print("Custom instructions being used:")
        for file in custom_instructions_files:
            print(f" - {file}")
    else:
        print("No custom instructions files are being used.")

    if not args.nocurated_dataset:
        # Load default curated_datasets profile
        default_curated_dataset_paths = curated_dataset_paths
        default_curated_dataset_paths = [path for path in default_curated_dataset_paths if path.strip() != '']
        curated_datasets, curated_dataset_files = load_files(file_paths=default_curated_dataset_paths + args.curated_dataset, file_type="curated_datasets")

    if curated_dataset_files:
        print("Curated datasets being used:")
        for file in curated_dataset_files:
            print(f" - {file}")
    else:
        print("No curated_dataset files are being used.")

    history = []  # Will contain user/assistant messages from conversation

    if args.load:
        filename = args.load.strip()  # Remove leading and trailing spaces
        full_path = os.path.join(sessions_data_dir, filename)
        with open(full_path, 'r') as f:
            history = json.load(f)
        print(f"Continuing previously saved session from file: {filename}")

    model = args.model
    if model is None:
        model = default_models[args.engine]
    elif model == "flagship":
        # Find the flagship model for this engine
        flagship_model = next(
            (m for m in engines_config[args.engine]['models'] if m.get('is_flagship')),
            None
        )
        if flagship_model:
            model = flagship_model['name']
        else:
            print(f"Warning: No flagship model defined for engine '{args.engine}'. Using default.")
            model = default_models[args.engine]

    # Get the engine API key from environment variable
    api_key_name = engines_config[args.engine].get('api_key_name')
    if api_key_name:
        api_key = os.getenv(api_key_name)
        engines_config[args.engine]['api_key'] = api_key

        # Set API keys for specific providers
        if args.engine == 'openai':
            openai.api_key = api_key
        elif args.engine == 'anthropic':
            anthropic.api_key = api_key
        elif args.engine == 'google':
            # LiteLLM looks for GEMINI_API_KEY environment variable
            os.environ['GEMINI_API_KEY'] = api_key


    # Get the default max_tokens and temperature from the engines.yaml configuration
    selected_model = next((item for item in engines_config[args.engine]['models'] if item['name'] == model), None)

    if model in model_cost_map:
        model_data = model_cost_map[model]
    else:
        model_data = {}

    if selected_model:
        default_temperature = selected_model.get("temperature", 0.75)
        # Prefer max_output_tokens from config, fall back to model_cost_map, then to default_max_tokens, then to 4096
        max_output_tokens = selected_model.get("max_output_tokens") or model_data.get("max_output_tokens") or selected_model.get("default_max_tokens") or 4096
        default_max_tokens = selected_model.get("default_max_tokens", min(max_output_tokens, 4096))
        # Get max_input_tokens for history compaction
        max_input_tokens = selected_model.get("max_input_tokens") or model_data.get("max_input_tokens") or 128000
    else:
        default_temperature = 0.75
        max_output_tokens = 4096
        default_max_tokens = 4096
        max_input_tokens = 128000

    # Use the default values if not provided by the user
    max_tokens = args.max_tokens or default_max_tokens
    temperature = args.temperature or default_temperature

    # Validate max_tokens doesn't exceed model's maximum output limit
    if max_tokens > max_output_tokens:
        print(f"Warning: Requested max_tokens ({max_tokens}) exceeds model's maximum output limit ({max_output_tokens})")
        print(f"Setting max_tokens to {max_output_tokens}")
        max_tokens = max_output_tokens

    supports_system_role = selected_model.get('supports_system_role', True)

    print(f"Using AI engine {args.engine} with model {model}")
    print(f"Creativity temperature setting: {temperature}")
    print(f"Max tokens setting: {max_tokens} (model max output: {max_output_tokens})")

    if args.interactive:
        print("Entering interactive mode. Conversation history is maintained between turns.")
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
            print("Ragbot.AI: ", end='', flush=True)  # Print prefix before streaming starts
            reply = chat(
                prompt=prompt,
                custom_instructions=custom_instructions,
                curated_datasets=curated_datasets,
                history=history,
                engine=args.engine,
                model=model,
                max_tokens=max_tokens,
                max_input_tokens=max_input_tokens,
                temperature=temperature,
                interactive=args.interactive,
                new_session=new_session,
                supports_system_role=supports_system_role
            )
            history.append({"role": "assistant", "content": reply})

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
        reply = chat(
            prompt=prompt,
            custom_instructions=custom_instructions,
            curated_datasets=curated_datasets,
            history=history,
            engine=args.engine,
            model=model,
            max_tokens=max_tokens,
            max_input_tokens=max_input_tokens,
            temperature=temperature,
            interactive=args.interactive,
            new_session=new_session,
            supports_system_role=supports_system_role
        )
        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()
        print(reply)

if __name__ == "__main__":
    main()
