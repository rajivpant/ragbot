#!/usr/bin/env python3
# ragbot-streamlit-chat.py - https://github.com/rajivpant/rbot
# Description: Streamlit chat interface for Ragbot.AI

from dotenv import load_dotenv
import os
import streamlit as st
import openai
import anthropic
from langchain.chat_models import ChatOpenAI, ChatAnthropic, ChatGooglePalm
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from helpers import load_custom_instruction_files, load_curated_dataset_files, load_config, chat


load_dotenv() # Load environment variables from .env file

# engine = st.selectbox("Choose an engine", options=['openai', 'anthropic', 'google-palm'], index=0)
engine = "openai"

if engine == 'openai':
    openai.api_key = os.getenv("OPENAI_API_KEY")
elif engine == 'anthropic':
    anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")


st.header("Ragbot.AI augmented brain & assistant")


if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        for response in openai.ChatCompletion.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        ):
            full_response += response.choices[0].delta.get("content", "")
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})