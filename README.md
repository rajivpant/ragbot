# rbot

🤖 rbot is a chatbot powered by OpenAI's GPT-4 model, developed by Rajiv Pant ([rajivpant](https://github.com/rajivpant)) and inspired by prior work done by Jim Mortko ([jskills](https://github.com/jskills)) and Alexandria Redmon ([alexdredmon](https://github.com/alexdredmon)).

It offers engaging conversations with a personalized touch and advanced context understanding. rbot processes user prompts and custom conversation decorators, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.

🚀 Rajiv's GPT-4 based chatbot that processes user prompts and custom conversation decorators, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.

🧠 Custom conversation decorators help the chatbot better understand the context, resulting in more accurate and relevant responses, surpassing the capabilities of standard GPT-4 implementations.

A Django web app for rbot is currently under development. Stay tuned for updates on this project!

## Blog Post Introducing rbot
[Introducing Rbot: A Personalized AI Assistant, Written by Rbot](https://rajiv.com/blog/2023/05/08/introducing-rbot-a-personalized-ai-assistant-written-by-rbot/)

## Installation

1. Ensure you have Python 3.6 or higher installed.
2. Clone this repository.
3. Install the required dependencies using pip:
```
pip install -r requirements.txt
```
4. Set your OpenAI API key as an environment variable:
```
export OPENAI_API_KEY=your_api_key_here
```

## Usage

To use rbot, you can provide a prompt and a conversation decorator file or a folder containing multiple decorator files.

Example 1:
```
./rbot.py -p "Write a short note in Rajiv's voice about some of Rajiv's coworkers, family members, and travel and food preferences." -d ../rajiv-llms/fine-tuning
```

Example 2:
```
./rbot.py -p "What are some good practices for software development?" -d decorators/software_development.txt
```


Example 3:
```
./rbot.py -p "Tell me a story about a brave knight and a wise wizard." -d decorators/story_characters
```


In the first example, rbot generates a short note in Rajiv's voice using the decorator files in the `../rajiv-llms/fine-tuning` folder. In the second example, rbot provides information on good practices for software development using the `decorators/software_development.txt` decorator file. In the third example, rbot tells a story about a brave knight and a wise wizard using the decorator files in the `decorators/story_characters` folder.


