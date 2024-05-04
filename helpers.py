# helpers.py
# Shared functions used by rbot.py and rbot-streamlit.py
# Author: Rajiv Pant

import os
import glob
import yaml
import pathlib
import openai
import anthropic
from litellm import completion
import tiktoken

from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Function to load configuration from YAML
def load_config(config_file):
    """Load configuration from YAML."""
    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)
    return config

# Function to load profiles from YAML
def load_profiles(profiles_file):
    """Load profiles from YAML."""
    with open(profiles_file, 'r') as stream:
        profiles = yaml.safe_load(stream)
    return profiles['profiles']

# Function to load files containing custom instructions
def load_custom_instruction_files(custom_instruction_path):

    """Load custom_instruction files."""
    custom_instructions = []
    custom_instruction_files = []  # to store file names of custom_instructions
    for path in custom_instruction_path:
        if os.path.isfile(path):
            with open(path, "r") as file:
                custom_instructions.append(file.read())
                custom_instruction_files.append(path)  # save file name
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "*")):
                if os.path.isfile(filepath):  # Check if the path is a file
                    with open(filepath, "r") as file:
                        custom_instructions.append(file.read())
                        custom_instruction_files.append(filepath)  # save file name

    return custom_instructions, custom_instruction_files

# Function to load files containing curated datasets
def load_curated_dataset_files(curated_dataset_path):

    """Load curated_dataset files."""
    curated_datasets = []
    curated_dataset_files = []  # to store file names of curated_datasets
    for path in curated_dataset_path:
        if os.path.isfile(path):
            with open(path, "r") as file:
                curated_datasets.append(file.read())
                curated_dataset_files.append(path)  # save file name
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "*")):
                if os.path.isfile(filepath):  # Check if the path is a file
                    with open(filepath, "r") as file:
                        curated_datasets.append(file.read())
                        curated_dataset_files.append(filepath)  # save file name
    return curated_datasets, curated_dataset_files

# Function to count tokens in a list of files
def count_tokens(file_paths):
    tokenizer = tiktoken.get_encoding('p50k_base')
    total_tokens = 0
    for file_path in file_paths:
        with open(file_path, 'r') as file:
            content = file.read()
            total_tokens += len(tokenizer.encode(content))
    return total_tokens

def count_custom_instructions_tokens(custom_instruction_path):
    _, custom_instruction_files = load_custom_instruction_files(custom_instruction_path)
    return count_tokens(custom_instruction_files)

def count_curated_datasets_tokens(curated_dataset_path):
    _, curated_dataset_files = load_curated_dataset_files(curated_dataset_path)
    return count_tokens(curated_dataset_files)


def print_saved_files(directory):
    sessions_directory = os.path.join(directory, "sessions")
    print("Currently saved JSON files:")
    for file in pathlib.Path(sessions_directory).glob("*.json"):
        print(f" - {file.name}")

def chat(
    prompt,
    curated_datasets,
    custom_instructions,
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
    Send a request to the OpenAI or Anthropic API with the provided prompt and curated_datasets.

    :param prompt: The user's input to generate a response for.
    :param curated_datasets: A list of curated_datasets to provide context for the model.
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
    added_curated_datasets = False

    messages = [
        {"role": "system", "content": ' '.join(custom_instructions)},
        {"role": "user", "content": ' '.join(curated_datasets) + prompt}, 
        
    ]
    # litellm allows you to use Google Palm, OpenAI, Azure, Anthropic, Replicate, Cohere LLM models
    # just pass model="gpt-3.5-turbo" (your model name)
    llm_response = completion(model=model, messages=messages,  max_tokens=max_tokens, temperature=temperature)
    return llm_response
    
#    match engine:
#
#        case "openai":
#
#            # Call the OpenAI API via LangChain
#            llm_invocation = ChatOpenAI(openai_api_key=openai.api_key, model_name=model, max_tokens=max_tokens, temperature=temperature)
#
#            llm_response =llm_invocation.invoke([SystemMessage(content=' '.join(custom_instructions)),HumanMessage(content=' '.join(curated_datasets) + prompt)])
#            response = llm_response.content
#
#
#        case "anthropic":
#            # Call the Anthropic API via LangChain
#            llm_invocation = ChatAnthropic(model=model, max_tokens_to_sample=max_tokens, temperature=temperature)
#
#            messages = [
#                HumanMessage(content=' '.join(custom_instructions)),
#                AIMessage(content=' '.join(curated_datasets)),
#                HumanMessage(content=prompt)
#            ]
#
#            llm_response = llm_invocation.invoke(messages)
#            response = llm_response.content
#
#        case "google":
#            # Call the Google API via LangChain
#            llm_invocation = ChatGoogleGenerativeAI(model=model, max_tokens=max_tokens, temperature=temperature)
#            
#            messages = [
#                HumanMessage(content=' '.join(custom_instructions)),
#                AIMessage(content=' '.join(curated_datasets)),
#                HumanMessage(content=prompt)
#            ]
#
#            llm_response = llm_invocation.invoke(messages)
#            response = llm_response.content
#
#    return response
