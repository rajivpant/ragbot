#!/usr/bin/env python3

# rbot-streamlit.py - https://github.com/rajivpant/rbot
# Developed by Rajiv Pant (https://github.com/rajivpant)
#
# ❗️ This web app using streamlit is currently in development.
# ❗️ It does not yet have the features in the rbot command line app rbot.py
# 
# 🤖 rbot: Rajiv's AI augmented brain, assistant, and chatbot
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

from dotenv import load_dotenv
import streamlit as st
import glob
import os
import re
import yaml
import json
import openai
import anthropic
from helpers import load_decorator_files, load_config

load_dotenv() # Load environment variables from .env file


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
        decorated_prompt = f"{anthropic.HUMAN_PROMPT} {' '.join(decorators)} {prompt} {anthropic.AI_PROMPT}"
        resp = c.completion(
            prompt=decorated_prompt,
            stop_sequences=[anthropic.HUMAN_PROMPT],
            model=model,
            max_tokens_to_sample=max_tokens,
        )
        return resp['completion']


def main():
    st.title("rbot: AI augmented brain assistant")
    engine = st.selectbox("Choose an engine", options=engine_choices, index=engine_choices.index(config.get('default', 'openai')))
    model = st.selectbox("Choose a model", options=engines_config[engine]['models'], index=engines_config[engine]['models'].index(engines_config[engine]['default_model']))
    temperature = st.slider("Creativity temperature", min_value=0.0, max_value=1.0, value=0.75, step=0.01)

    # Get default decorator paths from environment variable and populate the text area
    default_decorator_paths = os.getenv("DECORATORS", "").split("\n")
    # Remove any blank lines
    default_decorator_paths = [path for path in default_decorator_paths if path.strip() != '']
    decorator_path = st.text_area("Enter decorator path (files and/or directories)", "\n".join(default_decorator_paths))

    prompt = st.text_area("Enter your prompt here")

    decorators, decorator_files = load_decorator_files(decorator_path.split())
    history = []
    for decorator in decorators:
        history.append({"role": "system", "content": decorator,})

    # Use dotenv to get the API keys
    if engine == 'openai':
        openai.api_key = os.getenv("OPENAI_API_KEY")
    elif engine == 'anthropic':
        anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")

    st.write(f"Using AI engine {engine} with model {model}")

    if st.button("Get response"):
        history.append({"role": "user", "content": prompt})
        reply = chat(prompt=prompt, decorators=decorators, history=history, engine=engine, model=model, temperature=temperature)
        history.append({"role": "assistant", "content": reply})
        st.write(f"rbot:\n{reply}")


if __name__ == "__main__":
    main()

