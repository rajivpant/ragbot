# rbot

Rajiv's chat bot.

The environment variable OPENAI_API_KEY needs to be set in your shell for this to work.

In rbot.py where it says:

```
# set your custom conversation decorator here
with open('../rajiv-llms/fine-tuning/example-client.md', 'r') as file:
```
replace the path to the prompt decorator file with the one you want to use. In a subsequent version, I will make it configurable outside rbot.py.
