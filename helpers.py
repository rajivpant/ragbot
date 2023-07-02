# helpers.py
# Shared functions used by rbot.py and rbot-streamlit.py
# Author: Rajiv Pant

import os
import glob
import yaml
import pathlib
import openai
import anthropic
from langchain.llms import OpenAI, OpenAIChat, Anthropic
from langchain.chat_models import ChatOpenAI, ChatAnthropic


# Function to load configuration from YAML
def load_config(config_file):
    """Load configuration from YAML."""
    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)
    return config

def load_decorator_files(decorator_path):
    """Load decorator files."""
    decorators = []
    decorator_files = []  # to store file names of decorators
    for path in decorator_path:
        if os.path.isfile(path):
            with open(path, "r") as file:
                decorators.append(file.read())
                decorator_files.append(path)  # save file name
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "*")):
                if os.path.isfile(filepath):  # Check if the path is a file
                    with open(filepath, "r") as file:
                        decorators.append(file.read())
                        decorator_files.append(filepath)  # save file name
    return decorators, decorator_files


def print_saved_files(directory):
    sessions_directory = os.path.join(directory, "sessions")
    print("Currently saved JSON files:")
    for file in pathlib.Path(sessions_directory).glob("*.json"):
        print(f" - {file.name}")

def chat(
    prompt,
    decorators,
    model,
    max_tokens,
    stream=True,
    request_timeout=15,
    temperature=0.75,
    history=None,
    engine="openai",
    interactive=False,
    new_session=False
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
    :param interactive: Whether the chat is in interactive mode (default is False).
    :param new_session: Whether this is a new session (default is False).
    :return: The generated response text from the model.
    """
    added_decorators = False
    
    match engine:

        case "openai":
            # If no history is provided, construct it from the decorators
            if not history:
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

            # Call the OpenAI API via LangChain
            model = OpenAIChat(openai_api_key=openai.api_key, model=model, temperature=temperature, max_tokens=max_tokens, prefix_messages=history)
            #model = ChatOpenAI(openai_api_key=openai.api_key, model=model, temperature=temperature, max_tokens=max_tokens, prefix_messages=history)
            
            response = model(prompt)

        case "anthropic":   
            if not added_decorators and decorators:
                decorated_prompt = f"{anthropic.HUMAN_PROMPT} {' '.join(decorators)} {prompt} {anthropic.AI_PROMPT}"
                added_decorators = True
            else:
                decorated_prompt = f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}"
            # Call the Anthropic API via LangChain
            model = Anthropic(anthropic_api_key=anthropic.api_key, model=model, temperature=temperature, max_tokens_to_sample=max_tokens)
            #model = ChatAnthropic(anthropic_api_key=anthropic.api_key, model=model, temperature=temperature, max_tokens_to_sample=max_tokens)

            response = model(decorated_prompt) 

            if interactive and new_session and engine == "anthropic":
                added_decorators = False  # Reset decorators flag after each user prompt

    return response

