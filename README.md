# rbot

Rajiv's chat bot.

The environment variable OPENAI_API_KEY needs to be set in your shell for this to work. The instructions for doing that can be found at [OpenAI's Support Page for Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)

In rbot.py where it says:

```
# set your custom conversation decorator here
with open('../rajiv-llms/fine-tuning/hearst.md', 'r') as file:
```
replace the path to the prompt decorator file with the one you want to use. In a subsequent version, I will make it configurable outside rbot.py.
