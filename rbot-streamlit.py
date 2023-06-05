#!/usr/bin/env python3

# rbot.py - https://github.com/rajivpant/rbot
# Developed by Rajiv Pant (https://github.com/rajivpant)
# The first version was inspired by 
# - Jim Mortko (https://github.com/jskills)
# - Alexandria Redmon (https://github.com/alexdredmon)
#
# 🤖 rbot: Rajiv's AI augmented brain assistant chatbot
# utilizing OpenAI's GPT and Anthropic's Claude models 
# to offer engaging conversations
# with a personalized touch and advanced context understanding.
#
# 🚀 Rajiv's GPT-4 based chatbot processes user prompts and custom conversation decorators,
# enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.
#
# Custom decorators are a simpler way to achieve outcomes similar to those of
# Parameter-Efficient Fine-Tuning (PEFT) methods.
# 
# 🧠 Custom conversation decorators help the chatbot better understand the context,
# resulting in more accurate and relevant responses, surpassing the capabilities of
# out of the box GPT-4 implementations.


import streamlit as st
import glob
import os
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
        return resp['completion']



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
                with open(filepath, "r") as file:
                    decorators.append(file.read())
                    decorator_files.append(filepath)  # save file name
    return decorators, decorator_files


def main():
    st.title("rbot: Rajiv's AI augmented brain assistant chatbot")
    engine = st.selectbox("Choose an engine", options=engine_choices, index=engine_choices.index(config.get('default', 'openai')))
    model = st.text_input("Enter model name", value=engines_config[engine]['default_model'])
    decorator_path = st.text_input("Enter decorator path (either file or directory)")
    prompt = st.text_input("Enter your prompt here")
 
    decorators, decorator_files = load_decorator_files(decorator_path.split())
    history = []
    for decorator in decorators:
        history.append({"role": "system", "content": decorator,})

    if engine == 'openai':
        openai.api_key = st.secrets["OPENAI_API_KEY"]
    elif engine == 'anthropic':
        anthropic.api_key = st.secrets["ANTHROPIC_API_KEY"]

    st.write(f"Using AI engine {engine} with model {model}")

    if st.button("Get response"):
        history.append({"role": "user", "content": prompt})
        reply = chat(prompt=prompt, decorators=decorators, history=history, engine=engine, model=model)
        history.append({"role": "assistant", "content": reply})
        st.write(f"rbot: {reply}")


if __name__ == "__main__":
    main()

