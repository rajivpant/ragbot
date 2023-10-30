import os
import streamlit as st
import openai
import anthropic
from chat_engine import ChatOpenAI, ChatAnthropic
from utils import load_config

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
temperature_settings = config.get('temperature_settings', {})
engine_choices = list(engines_config.keys())

model_choices = {engine: [model['name'] for model in engines_config[engine]['models']] for engine in engine_choices}

default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}


st.header("Ragbot.AI augmented brain & assistant")

engine = st.selectbox("Choose an engine", options=engine_choices, index=engine_choices.index(config.get('default', 'openai')))
model = st.selectbox("Choose a model", options=model_choices[engine], index=model_choices[engine].index(default_models[engine]))

if engine == 'openai':
    openai.api_key = os.getenv("OPENAI_API_KEY")
    chat_engine = ChatOpenAI(model=model, temperature=temperature_settings.get(engine, 0.5))
elif engine == 'anthropic':
    anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")
    chat_engine = ChatAnthropic(model=model, temperature=temperature_settings.get(engine, 0.5))

st.write(f"Using {engine} engine with {model} model")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        response = openai.Completion.create(
            engine=chat_engine.engine,
            prompt=prompt,
            max_tokens=1024,
            n=1,
            stop=None,
            temperature=chat_engine.temperature,
            frequency_penalty=0,
            presence_penalty=0,
        )["choices"][0]["text"]
        st.session_state.messages.append({"role": "bot", "content": response})
        st.markdown(response)

    with st.chat_message("assistant"):
        if chat_engine.engine == "openai":
            message_placeholder = st.empty()
            full_response = ""
            for response in openai.ChatCompletion.create(
                model=chat_engine.model,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            ):
                full_response += response.choices[0].text
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        elif chat_engine.engine == "anthropic":
            response = chat_engine.send_message(st.session_state.messages)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.markdown(response)