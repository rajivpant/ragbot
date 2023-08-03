#!/usr/bin/env python3
# rbot-streamlit.py - https://github.com/rajivpant/rbot

from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
import glob
import os
import re
import yaml
import json
import openai
import anthropic
from helpers import load_custom_instruction_files, load_curated_dataset_files, load_config, chat

from langchain.llms import OpenAI, OpenAIChat, Anthropic

load_dotenv() # Load environment variables from .env file


# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
temperature_settings = config.get('temperature_settings', {})
engine_choices = list(engines_config.keys())

model_choices = {engine: [model['name'] for model in engines_config[engine]['models']] for engine in engine_choices}

default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}



def main():
    st.header("Ragbot.AI augmented brain & assistant")

    engine = st.selectbox("Choose an engine", options=engine_choices, index=engine_choices.index(config.get('default', 'openai')))
    model = st.selectbox("Choose a model", options=model_choices[engine], index=model_choices[engine].index(default_models[engine]))

    # Find the selected model in the engines config and get default temperature and tokens
    selected_model = next((item for item in engines_config[engine]['models'] if item['name'] == model), None)
    if selected_model:
        default_temperature = selected_model['temperature']
        default_max_tokens = selected_model['max_tokens']
    else:
        default_temperature = default_temperature = temperature_creative
        default_max_tokens = 1024

    temperature_precise = temperature_settings.get('precise', 0.20)
    temperature_balanced = temperature_settings.get('balanced', 0.50)
    temperature_creative = temperature_settings.get('creative', 0.75)

    temperature_precise_label = "precise leaning " + "(" + str(temperature_precise) + ")"
    temperature_balanced_label = "balanced " + "(" + str(temperature_balanced) + ")"
    temperature_creative_label = "creative leaning " + "(" + str(temperature_creative) + ")"
    temperature_custom_label = "custom"

    temperature_option = st.selectbox("Choose desired creativity option (called temperature)", options=[temperature_creative_label, temperature_balanced_label, temperature_precise_label, temperature_custom_label])
    temperature_mapping = {temperature_creative_label: temperature_creative, temperature_balanced_label: temperature_balanced, temperature_precise_label: temperature_precise}

    if temperature_option == temperature_custom_label:
        temperature = st.number_input("Enter a custom temperature", min_value=0.0, max_value=1.0, value=default_temperature, step=0.01)
    else:
        temperature = temperature_mapping[temperature_option]

    max_tokens_mapping = {"256": 256, "512": 512, "1024": 1024, "2048": 2048, "4096": 4096, "8192": 8192}
    default_max_tokens_list = list(max_tokens_mapping.keys())
    default_max_tokens_list.append("custom")

    # Get the index of the default max_tokens in the options list
    default_max_tokens_index = default_max_tokens_list.index(str(default_max_tokens))

    st.caption("Max tokens is the maximum number of tokens to generate in the response. For English text, 100 tokens is on average about 75 words.")
    max_tokens_option = st.selectbox("Choose max_tokens", options=default_max_tokens_list, index=default_max_tokens_index)

    if max_tokens_option == "custom":
        max_tokens = st.number_input("Enter a custom value for max_tokens", min_value=1, max_value=65536, value=default_max_tokens, step=128)
    else: 
        max_tokens = max_tokens_mapping[max_tokens_option]

    # Get default curated_dataset paths from environment variable and populate the text area
    default_custom_instruction_paths = os.getenv("CUSTOM_INSTRUCTIONS", "").split("\n")
    # Remove any blank lines
    default_custom_instruction_paths = [path for path in default_custom_instruction_paths if path.strip() != '']
    custom_instruction_path = st.text_area("Enter files and folders for custom instructions to provide commands", "\n".join(default_custom_instruction_paths))

    # Get default curated_dataset paths from environment variable and populate the text area
    default_curated_dataset_paths = os.getenv("CURATED_DATASETS", "").split("\n")
    # Remove any blank lines
    default_curated_dataset_paths = [path for path in default_curated_dataset_paths if path.strip() != '']
    curated_dataset_path = st.text_area("Enter files and folders for curated datasets to provide context", "\n".join(default_curated_dataset_paths))

    prompt = st.text_area("Enter your prompt here")
    custom_instructions, custom_instruction_files = load_custom_instruction_files(custom_instruction_path=custom_instruction_path.split())   
    curated_datasets, curated_dataset_files = load_curated_dataset_files(curated_dataset_path=curated_dataset_path.split())
    history = []
    for curated_dataset in curated_datasets:
        history.append({"role": "system", "content": curated_dataset,})

    # Use dotenv to get the API keys
    if engine == 'openai':
        openai.api_key = os.getenv("OPENAI_API_KEY")
    elif engine == 'anthropic':
        anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")

    # Get the current date and time
    now = datetime.now()
    # Convert to a string in the format of "2021/January/01 01:01 AM (UTC)"
    date_and_time = now.strftime("%Y/%B/%d %I:%M %p %Z")

    st.write(f"Using AI engine {engine} with model {model}. Creativity temperature set to {temperature} and max_tokens set to {max_tokens}. The current date and time is {date_and_time}.")
    debug_mode = st.checkbox("Debug mode", value=False)

    if st.button("Get response"):

        if debug_mode:
            st.write(f"engine: {engine}")
            st.write(f"model: {model}")
            st.write(f"max_tokens: {max_tokens}")
            st.write(f"temperature: {temperature}")
            st.write(f"custom_instruction_files: {custom_instruction_files}")
            st.write(f"curated_dataset_files: {curated_dataset_files}")
            # st.write(f"custom_instructions: {custom_instructions}")
            # st.write(f"curated_datasets: {curated_datasets}")
            # st.write(f"history: {history}")
            st.write(f"prompt: {prompt}")
            
        history.append({"role": "user", "content": prompt})
        reply = chat(prompt=prompt, custom_instructions=custom_instructions, curated_datasets=curated_datasets, history=history, engine=engine, model=model, max_tokens=max_tokens, temperature=temperature)
        history.append({"role": "assistant", "content": reply})
        st.header(f"Ragbot.AI's response")
        st.divider()
        st.write(f"{reply}")


if __name__ == "__main__":
    main()

