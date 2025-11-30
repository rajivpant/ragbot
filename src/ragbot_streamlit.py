#!/usr/bin/env python3
# ragbot_streamlit.py - https://github.com/rajivpant/ragbot

from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
import os
import openai
import anthropic
import litellm
import babel.numbers
from helpers import load_files, load_config, chat, count_tokens_from_text, load_profiles, load_workspaces_as_profiles, load_data_config, human_format

load_dotenv() # Load environment variables from .env file

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
temperature_settings = config.get('temperature_settings', {})
engine_choices = list(engines_config.keys())
model_choices = {engine: [model['name'] for model in engines_config[engine]['models']] for engine in engine_choices}
default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}

# Build hierarchical model structure by category
def get_categorized_models(engine):
    """Organize models by category (small, medium, large, reasoning)"""
    models = engines_config[engine]['models']
    categorized = {'small': [], 'medium': [], 'large': [], 'reasoning': []}
    for model in models:
        category = model.get('category', 'medium')  # Default to medium if not specified
        categorized[category].append(model['name'])
    return categorized

# Create friendly category labels
category_labels = {
    'small': 'Fast',
    'medium': 'Balanced',
    'large': 'Powerful',
    'reasoning': 'Reasoning'
}

# Map categories back to keys
category_keys = {v: k for k, v in category_labels.items()}

model_cost_map = litellm.model_cost


def get_model_display_name(model_name):
    """Extract a shorter display name from the full model name."""
    # Common patterns to simplify
    name = model_name.split('/')[-1]  # Remove provider prefix like "anthropic/"
    return name 

@st.cache_data
def get_model_limits(engine, model):
    """Get model token limits from config or litellm."""
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

    return max_input_tokens, model_data


@st.cache_data
def load_and_count_files(file_paths_tuple, file_type):
    """Load files and count tokens in a single pass. Returns (content, files_list, token_count)."""
    # Convert tuple back to list (tuples are hashable for caching)
    file_paths = list(file_paths_tuple)
    content, files_list = load_files(file_paths=file_paths, file_type=file_type)
    token_count = count_tokens_from_text(content)
    return content, files_list, token_count


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
    st.set_page_config(
        page_title="Ragbot.AI",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'workspace' not in st.session_state:
        st.session_state.workspace = None

    # Load workspaces from ragbot-data directory
    data_root = os.getenv('RAGBOT_DATA_ROOT')
    if data_root is None:
        if os.path.isdir('/app/workspaces'):
            data_root = '/app'
        elif os.path.isdir('workspaces'):
            data_root = '.'
        elif os.path.isdir('../ragbot-data/workspaces'):
            data_root = '../ragbot-data'
        else:
            data_root = '.'

    profiles = load_workspaces_as_profiles(data_root)
    profile_choices = [profile['name'] for profile in profiles]

    # Load global config for default workspace
    data_config = load_data_config(data_root)
    default_workspace = data_config.get('default_workspace', '')

    # Find index of default workspace (match by directory name or display name)
    default_index = 0
    for i, profile in enumerate(profiles):
        # Check if this profile matches the default workspace
        if profile.get('name') == default_workspace or profile.get('dir_name') == default_workspace:
            default_index = i
            break

    # ===== SIDEBAR =====
    with st.sidebar:
        st.title("🤖 Ragbot.AI")

        # Workspace selection
        selected_profile = st.selectbox(
            "Workspace",
            options=profile_choices,
            index=default_index,
            help="Select a workspace with pre-configured instructions and datasets"
        )

        # Detect workspace change and clear history
        if st.session_state.workspace != selected_profile:
            if st.session_state.workspace is not None:
                st.session_state.history = []
            st.session_state.workspace = selected_profile

        # Get workspace paths
        selected_profile_data = next(profile for profile in profiles if profile['name'] == selected_profile)
        default_custom_instruction_paths = [p for p in selected_profile_data.get('instructions', []) if p.strip()]
        default_curated_dataset_paths = [p for p in selected_profile_data.get('datasets', []) if p.strip()]

        st.divider()

        # Model selection - compact layout
        st.subheader("Model")
        engine = st.selectbox(
            "Provider",
            options=engine_choices,
            index=engine_choices.index(config.get('default', 'openai')),
            label_visibility="collapsed"
        )

        categorized_models = get_categorized_models(engine)
        default_model = default_models[engine]

        # Find default category
        default_category = 'medium'
        for cat, models_in_cat in categorized_models.items():
            if default_model in models_in_cat:
                default_category = cat
                break

        available_categories = [cat for cat in ['small', 'medium', 'large', 'reasoning'] if categorized_models[cat]]

        # Two columns for category and model
        col1, col2 = st.columns(2)
        with col1:
            model_category = st.selectbox(
                "Size",
                options=available_categories,
                index=available_categories.index(default_category) if default_category in available_categories else 0,
                format_func=lambda x: category_labels[x]
            )
        with col2:
            models_in_category = categorized_models[model_category]
            default_idx = models_in_category.index(default_model) if default_model in models_in_category else 0
            model = st.selectbox(
                "Model",
                options=models_in_category,
                index=default_idx,
                format_func=get_model_display_name
            )

        # Get model config
        selected_model = next((item for item in engines_config[engine]['models'] if item['name'] == model), None)
        model_data = model_cost_map.get(model, {})

        if selected_model:
            default_temperature = selected_model.get("temperature", 0.75)
            default_max_tokens = selected_model.get("max_output_tokens") or model_data.get("max_output_tokens") or 4096
        else:
            default_temperature = 0.75
            default_max_tokens = 4096

        supports_system_role = selected_model.get('supports_system_role', True) if selected_model else True
        max_input_tokens, _ = get_model_limits(engine, model)

        st.divider()

        # Temperature - simplified
        # Check if model supports variable temperature
        max_temp = selected_model.get('max_temperature', 2) if selected_model else 2
        model_fixed_temp = selected_model.get('temperature', 0.75) if selected_model else 0.75

        if max_temp <= 1:
            # Model only supports fixed temperature (reasoning models)
            st.subheader("Creativity")
            st.caption("This model uses fixed temperature")
            temp_choice = "Fixed"
            temperature = model_fixed_temp
        else:
            st.subheader("Creativity")
            temperature_presets = {
                "Precise": temperature_settings.get('precise', 0.20),
                "Balanced": temperature_settings.get('balanced', 0.50),
                "Creative": temperature_settings.get('creative', 0.75)
            }
            temp_choice = st.select_slider(
                "Temperature",
                options=list(temperature_presets.keys()),
                value="Creative",
                label_visibility="collapsed"
            )
            temperature = temperature_presets[temp_choice]

        st.divider()

        # Conversation controls
        st.subheader("Conversation")
        history_count = len(st.session_state.history) // 2  # Count exchanges, not messages
        history_tokens = sum(count_tokens_from_text(msg['content']) for msg in st.session_state.history)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Turns", history_count)
        with col2:
            st.metric("Tokens", human_format(history_tokens))

        if st.button("🗑️ Clear Chat", use_container_width=True, disabled=history_count == 0):
            st.session_state.history = []
            st.rerun()

        st.divider()

        # Advanced settings in expander
        with st.expander("⚙️ Advanced Settings"):
            # Max tokens
            max_tokens_mapping = {str(2**i): 2**i for i in range(8, 17)}
            default_max_tokens_option = find_closest_max_tokens(default_max_tokens, {k: int(k) for k in max_tokens_mapping})
            max_tokens = st.select_slider(
                "Max response tokens",
                options=list(max_tokens_mapping.keys()),
                value=default_max_tokens_option
            )
            max_tokens = int(max_tokens)

            # Custom instructions path
            custom_instruction_path = st.text_area(
                "Custom instructions paths",
                "\n".join(default_custom_instruction_paths),
                height=68
            )

            # Curated datasets path
            curated_dataset_path = st.text_area(
                "Dataset paths",
                "\n".join(default_curated_dataset_paths),
                height=68
            )

        # Debug info
        with st.expander("🔍 Debug Info"):
            now = datetime.now()

            # Load files for debug info
            custom_instructions, custom_instructions_files, custom_instructions_tokens = load_and_count_files(
                tuple(custom_instruction_path.split()), "custom_instructions"
            )
            curated_datasets, curated_dataset_files, curated_datasets_tokens = load_and_count_files(
                tuple(curated_dataset_path.split()), "curated_datasets"
            )

            st.caption(f"**Provider:** {engine}")
            st.caption(f"**Model:** {model}")
            st.caption(f"**Context:** {human_format(max_input_tokens)} tokens")
            st.caption(f"**Max output:** {human_format(max_tokens)} tokens")
            st.caption(f"**Temperature:** {temperature}")
            st.caption(f"**Instructions:** {len(custom_instructions_files)} files ({human_format(custom_instructions_tokens)} tokens)")
            st.caption(f"**Datasets:** {len(curated_dataset_files)} files ({human_format(curated_datasets_tokens)} tokens)")
            st.caption(f"**Time:** {now.strftime('%Y-%m-%d %H:%M')}")

    # ===== MAIN CHAT AREA =====

    # Load files for chat (may already be cached)
    if 'custom_instruction_path' not in dir() or not custom_instruction_path:
        custom_instruction_path = "\n".join(default_custom_instruction_paths)
    if 'curated_dataset_path' not in dir() or not curated_dataset_path:
        curated_dataset_path = "\n".join(default_curated_dataset_paths)

    custom_instructions, custom_instructions_files, custom_instructions_tokens = load_and_count_files(
        tuple(custom_instruction_path.split()), "custom_instructions"
    )
    curated_datasets, curated_dataset_files, curated_datasets_tokens = load_and_count_files(
        tuple(curated_dataset_path.split()), "curated_datasets"
    )

    # Set API keys
    if engine == 'openai':
        openai.api_key = os.getenv("OPENAI_API_KEY")
    elif engine == 'anthropic':
        anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")

    # Header with current config
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(f"### 💬 {selected_profile}")
    with header_col2:
        st.caption(f"{get_model_display_name(model)} · {temp_choice}")

    # Chat container for messages
    chat_container = st.container()

    # Display conversation history
    with chat_container:
        if not st.session_state.history:
            # Welcome message
            st.markdown("""
            <div style="text-align: center; padding: 2rem; color: #666;">
                <p style="font-size: 1.2rem;">Welcome to Ragbot.AI</p>
                <p>Your augmented brain & assistant</p>
                <p style="font-size: 0.9rem; margin-top: 1rem;">Type a message below to start the conversation.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.history:
                with st.chat_message(msg['role'], avatar="🧑" if msg['role'] == 'user' else "🤖"):
                    st.markdown(msg['content'])

    # Chat input at the bottom
    if prompt := st.chat_input("Message Ragbot.AI..."):
        # Add user message to history
        st.session_state.history.append({"role": "user", "content": prompt})

        # Display user message immediately
        with chat_container:
            with st.chat_message("user", avatar="🧑"):
                st.markdown(prompt)

            # Generate and display assistant response
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Thinking..."):
                    reply = chat(
                        prompt=prompt,
                        custom_instructions=custom_instructions,
                        curated_datasets=curated_datasets,
                        history=st.session_state.history,
                        engine=engine,
                        model=model,
                        max_tokens=max_tokens,
                        max_input_tokens=max_input_tokens,
                        temperature=temperature,
                        supports_system_role=supports_system_role,
                        interactive=False
                    )
                st.markdown(reply)

        # Add assistant message to history
        st.session_state.history.append({"role": "assistant", "content": reply})

        # Rerun to update the UI properly
        st.rerun()

if __name__ == "__main__":
    main()

