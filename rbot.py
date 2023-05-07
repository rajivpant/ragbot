#!/usr/local/bin/python

# rbot.py
# Original version by Jim Mortko, based on a similar program by Alexandira Redmon
# Current version by Rajiv Pant

import os
from sys import argv
import openai

# set your custom conversation decorator here
with open('../rajiv-llms/fine-tuning/hearst.md', 'r') as file:
    # Read the contents of the file into a string variable
    CONVERSATION_DECORATOR = file.read()

# Load your API key from an environment variable or secret management service
openai.api_key = os.getenv("OPENAI_API_KEY")

def chat(
        prompt,
        history = [],
        conversation_decorator = CONVERSATION_DECORATOR,
        model = 'gpt-4',
        max_tokens = 1000,
        stream = True,
        request_timeout = 15,
        temperature = .75
    ):

    if history == [] and conversation_decorator != '':
        history.append({
            'role': 'system',
            'content': conversation_decorator,
        })
    history = history + [{
        'role': 'user',
        'content': prompt
    }]

    args = {
        'max_tokens': max_tokens,
        'model': model,
        'request_timeout': request_timeout,
        'stream': stream,
        'temperature': temperature,
        'messages': history
    }

    completion_method = openai.ChatCompletion.create

    response = ''

    for token in completion_method(
        **args
    ):
        text = None
        if 'content' in token['choices'][0]['delta']:
            text = token['choices'][0]['delta']['content']
            response = response + text

    return response

#####


prompt = None

if argv[1:]:
    prompt = argv[1]
else:
    print("Usage: python chat-gpt.py [prompt]")
    exit()

reply = chat(prompt=prompt)

print(reply)


