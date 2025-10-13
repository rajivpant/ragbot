#!/usr/bin/env python3
# ragbot_streamlit.py - https://github.com/rajivpant/ragbot

from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
import os
import openai
import anthropic
import tiktoken
import litellm
import babel.numbers
from helpers import load_files, load_config, chat, count_custom_instructions_tokens, count_curated_datasets_tokens, load_profiles, human_format

load_dotenv() # Load environment variables from .env file

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
temperature_settings = config.get('temperature_settings', {})
engine_choices = list(engines_config.keys())
model_choices = {engine: [model['name'] for model in engines_config[engine]['models']] for engine in engine_choices}
default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}

model_cost_map = litellm.model_cost 

@st.cache_data

def get_token_counts(custom_instruction_path, curated_dataset_path, engine, model):
    custom_instructions_tokens = count_custom_instructions_tokens(custom_instruction_path)
    curated_datasets_tokens = count_curated_datasets_tokens(curated_dataset_path)

    # Find selected model and get context length
    selected_model = next((item for item in engines_config[engine]['models'] if item['name'] == model), None)

    if model in model_cost_map:
        model_data = model_cost_map[model]
    else:
        model_data = {}

    # Prefer max_input_tokens from config, fall back to model_cost_map, then to 128000
    if selected_model:
        max_input_tokens = selected_model.get("max_input_tokens") or model_data.get("max_input_tokens") or 128000
    else:
        max_input_tokens = model_data.get("max_input_tokens") or 128000

    return custom_instructions_tokens, curated_datasets_tokens, max_input_tokens


def find_closest_max_tokens(suggested_max_tokens, max_tokens_mapping):
    """Finds the closest max_tokens option that is less than or equal to the suggested value,
       or returns the lowest available option if the suggested value is too low."""

    closest_option = None
    closest_difference = float('inf')

    for option, value in max_tokens_mapping.items():
        difference = suggested_max_tokens - value
        if 0 <= difference < closest_difference:
            closest_option = option
            closest_difference = difference

    # If no suitable option found, return the lowest available option
    if closest_option is None:
        return min(max_tokens_mapping, key=max_tokens_mapping.get) 

    return closest_option


def main():

    st.set_page_config(layout="wide")  # Set the page to wide mode to give more space for sidebar

    # Sidebar for initial options
    with st.sidebar:
        st.header("Configuration")
        engine = st.selectbox("Choose an engine", options=engine_choices, index=engine_choices.index(config.get('default', 'openai')))
        model = st.selectbox("Choose a model", options=model_choices[engine], index=model_choices[engine].index(default_models[engine]))

        # Find the selected model in the engines config and get default temperature and tokens
        selected_model = next((item for item in engines_config[engine]['models'] if item['name'] == model), None)

        if model in model_cost_map:
            model_data = model_cost_map[model]
        else:
            model_data = {}

        if selected_model:
            default_temperature = selected_model.get("temperature")
            # Prefer max_output_tokens from config, fall back to model_cost_map, then to 4096
            default_max_tokens = selected_model.get("max_output_tokens") or model_data.get("max_output_tokens") or 4096
        else:
            default_temperature = temperature_settings.get('creative', 0.75)
            default_max_tokens = 4096

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

        max_tokens_mapping = {str(2**i): 2**i for i in range(8, 17)}  # Powers of 2 from 256 to 65536ß
        default_max_tokens_list = list(max_tokens_mapping.keys())
        default_max_tokens_list.append("custom")

        # Get the index of the default max_tokens in the options list
        default_max_tokens_option = find_closest_max_tokens(default_max_tokens, {option: int(option) for option in default_max_tokens_list if option != 'custom'})
        default_max_tokens_index = default_max_tokens_list.index(default_max_tokens_option)

    supports_system_role = selected_model.get('supports_system_role', True)

    st.header("Ragbot.AI augmented brain & assistant")

    # Load profiles from profiles.yaml
    profiles = load_profiles('profiles.yaml')
    profile_choices = [profile['name'] for profile in profiles]

    # Select profile
    selected_profile = st.selectbox("Choose a profile", options=profile_choices)

    # Get custom instruction and curated dataset paths from selected profile
    selected_profile_data = next(profile for profile in profiles if profile['name'] == selected_profile)
    default_custom_instruction_paths = selected_profile_data.get('custom_instructions', [])
    default_curated_dataset_paths = selected_profile_data.get('curated_datasets', [])

    default_custom_instruction_paths = [path for path in default_custom_instruction_paths if path.strip() != '']
    custom_instruction_path = st.text_area("Enter files and folders for custom instructions to provide commands", "\n".join(default_custom_instruction_paths))

    default_curated_dataset_paths = [path for path in default_curated_dataset_paths if path.strip() != '']
    curated_dataset_path = st.text_area("Enter files and folders for curated datasets to provide context", "\n".join(default_curated_dataset_paths))

    prompt = st.text_area("Enter your prompt here")

    with st.sidebar:
        # Calculate prompt tokens
        tokenizer = tiktoken.get_encoding("cl100k_base")  # Choose appropriate encoding
        prompt_tokens = len(tokenizer.encode(prompt))

        # Display token counts
        custom_instructions_tokens, curated_datasets_tokens, max_input_tokens = get_token_counts(custom_instruction_path.split(), curated_dataset_path.split(), engine, model)
        total_tokens = custom_instructions_tokens + curated_datasets_tokens + prompt_tokens

        # Calculate suggested max_tokens with 15% safety margin to account for tokenization differences
        # between tiktoken estimates and actual API tokenization
        safety_margin = 0.85  # Use 85% of available tokens
        available_tokens = max_input_tokens - total_tokens
        suggested_max_tokens = int(available_tokens * safety_margin)

        # Cap at the model's actual max_output_tokens limit
        model_max_output = default_max_tokens
        suggested_max_tokens = min(suggested_max_tokens, model_max_output)

        # Find the closest rounded-down max_tokens option that is less than or equal to the model's max_tokens
        closest_max_tokens_option = find_closest_max_tokens(min(suggested_max_tokens, default_max_tokens), max_tokens_mapping)

        # Get the index of the closest max_tokens option in the list
        closest_max_tokens_index = default_max_tokens_list.index(closest_max_tokens_option)

        # Validate index and handle edge cases
        if closest_max_tokens_index >= len(default_max_tokens_list):
            closest_max_tokens_index = 0  # Default to the first option if the index is out of range

        # Display token information and suggestion
        total_tokens_humanized = human_format(total_tokens)
        custom_instructions_tokens_humanized = human_format(custom_instructions_tokens)
        curated_datasets_tokens_humanized = human_format(curated_datasets_tokens)
        prompt_tokens_humanized = human_format(prompt_tokens)
        suggested_max_tokens_humanized = human_format(suggested_max_tokens)

        input_cost_per_token = model_data.get("input_cost_per_token")
        input_cost = total_tokens * input_cost_per_token

        input_cost_formatted = babel.numbers.format_currency(input_cost, 'USD', locale="en_US")

        st.markdown(f"Input tokens used: {total_tokens_humanized} ({input_cost_formatted})"\
                    , help="A token is about 4 characters for English text. The maximum number of tokens allowed for the entire request, including the custom instructions, curated datasets, prompt, and the generated response is limited. Adjust the value based on the tokens used by the custom instructions, curated datasets, and prompt.")

        max_tokens_option = st.selectbox("Choose max tokens for the response (less than " + str(suggested_max_tokens_humanized) + ")", options=default_max_tokens_list, index=closest_max_tokens_index)

        if max_tokens_option == "custom":
            max_tokens = st.number_input("Enter a custom value for max_tokens for the response", min_value=1, max_value=65536, value=default_max_tokens, step=128)
        else: 
            max_tokens = max_tokens_mapping[max_tokens_option]


    custom_instructions, custom_instructions_files = load_files(file_paths=custom_instruction_path.split(), file_type="custom_instructions")
    curated_datasets, curated_dataset_files = load_files(file_paths=curated_dataset_path.split(), file_type="curated_datasets")

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
    # Convert to a string in the format of "2021/Jan/01"
    date = now.strftime("%Y/%b/%d")

    with st.sidebar:
        debug_expander = st.expander("Debug Information")

        with debug_expander:
            st.write(f"The current date and time is {date_and_time}.")
            st.write(f"engine: {engine}")
            st.write(f"model: {model}")
            st.write(f"max_input_tokens: {human_format(max_input_tokens)}")
            st.write(f"max_tokens: {human_format(max_tokens)}")
            st.write(f"default_max_tokens: {human_format(default_max_tokens)}")
            st.write(f"temperature: {temperature}")
            st.write(f"supports_system_role: {supports_system_role}")
            st.write(f"Input tokens used: {total_tokens_humanized} (Custom Instructions: {custom_instructions_tokens_humanized}, Curated Datasets: {curated_datasets_tokens_humanized}, Prompt: {prompt_tokens_humanized})")
            st.write(f"custom_instruction_files: {custom_instructions_files}")
            st.write(f"curated_dataset_files: {curated_dataset_files}")
            st.write(f"prompt: {prompt}")
            #st.write(f"custom_instructions: {custom_instructions}")
            #st.write(f"curated_datasets: {curated_datasets}")
            #st.write(f"history: {history}")

    if st.button("Get response"):
        history.append({"role": "user", "content": prompt})
        reply = chat(prompt=prompt, custom_instructions=custom_instructions, curated_datasets=curated_datasets, history=history, engine=engine, model=model, max_tokens=max_tokens, temperature=temperature, supports_system_role=supports_system_role)
        history.append({"role": "assistant", "content": reply})
        st.header(f"Ragbot.AI's response")
        st.write(f"Profile: {selected_profile}, AI: {engine}/{model}, Creativity: {temperature}, Date: {date}")
        st.divider()
        st.write(f"{reply}")

if __name__ == "__main__":
    main()

