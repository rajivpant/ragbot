rbot
====

🤖 [rbot](https://github.com/rajivpant/rbot): Rajiv's open source AI augmented brain assistant chatbot currently utilizing OpenAI's GPT and Anthropic's Claude models to offer engaging conversations with a personalized touch and advanced context understanding.

🚀 rbot processes user prompts and custom curated datasets, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.

Curated datasets are a simpler way to achieve outcomes similar to those of Parameter-Efficient Fine-Tuning (PEFT) methods.

Powered by large language models (LLMs), rbot uses a method called [Retrieval Augmented Generation](https://ai.meta.com/blog/retrieval-augmented-generation-streamlining-the-creation-of-intelligent-natural-language-processing-models/) (RAG) which is a technique that combines the power of pre-trained dense retrieval and sequence-to-sequence models to generate more factual and informative text.

🧠 Curated datasets help the AI assistant better understand the context, resulting in more accurate and relevant responses, surpassing the capabilities of out of the box GPT-4 implementations.

Developed by [Rajiv Pant](https://github.com/rajivpant)

Contributors and Advisors
- [Vik Pant, PhD](https://www.linkedin.com/in/vikpant/)
- [Alexandria Redmon](https://github.com/alexdredmon)
- [Trace Wax](https://github.com/tracedwax)
- [Jim Mortko](https://github.com/jskills)

Blog Post Introducing rbot
--------------------------

[Introducing Rbot: A Personalized AI Assistant, Written by Rbot](https://rajiv.com/blog/2023/05/08/introducing-rbot-a-personalized-ai-assistant-written-by-rbot/)

Excerpt from the blog post:

### Rbot: Offering Personalized Assistance Beyond ChatGPT Plus, Bing Chat, and Google Bard Currently Offer

As an AI assistant, I provide a unique level of personalization and adaptability that sets me apart from current implementations of ChatGPT Plus, Bing Chat, and Google Bard. By using folders containing customized curated dataset files, I can cater to multiple use cases, such as personal life, work, education, and specific projects. This customization enables me to understand and support you in a way that is tailored to your unique needs.

#### Serving as Your Personal Life Assistant

You can create a folder with curated dataset files that include personal information, family details, travel and food preferences, and more. By using this information, I can function as your personal life assistant, offering AI-powered recommendations and support tailored to your specific context.

#### Assisting You in Your Professional Life

Similarly, you can develop another folder containing curated dataset files related to your work life. These files might include details about your job, industry, colleagues, projects, and other work-related information. With this context, I can help you with various tasks, such as drafting emails, scheduling meetings, conducting research, and more, enhancing your efficiency and organization.

#### Supporting Your Educational Goals

You can also customize me for educational purposes by creating a folder with curated dataset files containing information about your academic background, subjects of interest, courses, and other educational details. In this role, I can provide personalized educational support, from helping with homework to explaining complex concepts or recommending learning resources.

#### Providing Project-Specific Help

In addition to the use cases mentioned above, I can be tailored to support you on specific projects. By creating a folder with curated dataset files containing project-related information, such as objectives, team members, deadlines, and relevant resources, I can assist you throughout the project lifecycle, offering valuable insights and support tailored to each unique project.

My ability to create distinct profiles for different needs using customized curated dataset files sets me apart from ChatGPT Plus, Bing Chat, and Google Bard. This versatility enables me to offer personalized assistance across multiple aspects of your life, ensuring that I can understand and cater to your specific requirements.

Installation, Configuration, and Personalization
------------------------------------------------
Read the [installation guide](INSTALL.md) and the [configuration and personaliation guide](CONFIGURE.md).

Using the Web version
---------------------
![](screenshots/Screenshot%202023-06-16%20at%2010.53.12%20PM.png)
![](screenshots/Screenshot%202023-06-16%20at%2011.32.51%20PM.png)

Using the command line interface
--------------------------------

### Command line usage: Getting help

```console
rajiv@RP-2023-MacBook-Air rbot % ./rbot --help
usage: rbot.py [-h] [-ls] [-p PROMPT | -f PROMPT_FILE | -i | --stdin]
               [-d [CURATED_DATASET ...]] [-nd] [-e {openai,anthropic,google}]
               [-m MODEL] [-t TEMPERATURE] [-mt MAX_TOKENS] [-l LOAD]

A GPT-4 or Anthropic Claude based chatbot that generates responses based on
user prompts.

options:
  -h, --help            show this help message and exit
  -ls, --list-saved     List all the currently saved JSON files.
  -p PROMPT, --prompt PROMPT
                        The user's input to generate a response for.
  -f PROMPT_FILE, --prompt_file PROMPT_FILE
                        The file containing the user's input to generate a
                        response for.
  -i, --interactive     Enable interactive assistant chatbot mode.
  --stdin               Read the user's input from stdin.
  -d [CURATED_DATASET ...], --curated_dataset [CURATED_DATASET ...]
                        Path to the prompt context curated_dataset file or
                        folder. Can accept multiple values.
  -nd, --nocurated_dataset
                        Ignore all prompt context curated_datasets even if
                        they are specified.
  -e {openai,anthropic,google}, --engine {openai,anthropic,google}
                        The engine to use for the chat.
  -m MODEL, --model MODEL
                        The model to use for the chat. Defaults to engine's
                        default model.
  -t TEMPERATURE, --temperature TEMPERATURE
                        The creativity of the response, with higher values
                        being more creative.
  -mt MAX_TOKENS, --max_tokens MAX_TOKENS
                        The maximum number of tokens to generate in the
                        response.
  -l LOAD, --load LOAD  Load a previous interactive session from a file.
rajiv@RP-2023-MacBook-Air rbot % 
```

### Using curated dataset files

To use rbot, you can provide curated dataset files and/or folders containing multiple curated dataset files. You can view examples of curated dataset files at <https://github.com/rajivpant/rbot/tree/main/example-curated-datasets>

Example 1:

```console
rajivpant@RP-2021-MacBook-Pro rbot % ./rbot.py -d custom-instructions/ curated-datasets/public/ ../rbot-private/curated-datasets/personal/ ../rbot-private/curated-datasets/hearst -p "Write a short note in Rajiv's voice about Rajiv's job, coworkers, family members, and travel and food preferences for the person temporarily backfilling for his EA." 
curated datasets being used:
 - custom-instructions/
 - curated-datasets/public/travel-food.md
 - curated-datasets/public/employment-history.md
 - curated-datasets/public/about.md
 - curated-datasets/public/biography.md
 - ../rbot-private/curated-datasets/personal/accounts.md
 - ../rbot-private/curated-datasets/personal/contact-info.md
 - ../rbot-private/curated-datasets/personal/personal-family.md
 - ../rbot-private/curated-datasets/hearst/hearst.md
Using AI engine openai with model gpt-4
[redacted in this example]
```

Example 2:

```console
rajivpant@RP-2021-MacBook-Pro rbot % ./rbot.py -d custom-instructions/ curated-datasets/public/ -p "Write a short resume of Rajiv" 
curated datasets being used:
 - custom-instructions/
 - curated-datasets/public/travel-food.md
 - curated-datasets/public/employment-history.md
 - curated-datasets/public/about.md
 - curated-datasets/public/biography.md
Using AI engine openai with model gpt-4
[truncated in this example]
```

Example 3:

```console
./rbot.py -p "Tell me a story about a brave knight and a wise wizard." -d curated datasets/story_characters
```

### Interactive mode

To use rbot in interactive mode, use the `-i` or `--interactive` flag without providing a prompt via command line or input file. In this mode, you can enter follow-up prompts after each response.

Example:

```console
./rbot.py -i -d curated-datasets/story_characters
```

In the first example, rbot generates a short note in Rajiv's voice using the curated dataset files in the `../rbot-private/curated-datasets` folder. In the second example, rbot provides information on good practices for software development using the `curated-datasets/software_development.txt` curated dataset file. In the third example, rbot tells a story about a brave knight and a wise wizard using the curated dataset files in the `curated-datasets/story_characters` folder.

### Using rbot to suggest changes to its own code!

```console
rajivpant@RP-2021-MacBook-Pro rbot % ./rbot.py -d rbot.py -p "if no curated dataset files are being used, then I want the code to show that."
curated datasets being used:
 - rbot.py
Using AI engine openai with model gpt-4
To modify the code to show a message when no curated dataset files are being used, you can add an else statement after checking for the curated dataset files. Update the code in the `main()` function as follows:

\```python
if curated_dataset_files:
    print("curated datasets being used:")
    for file in curated_dataset_files:
        print(f" - {file}")
else:
    print("No curated dataset files are being used.")
\```

This will print "No curated dataset files are being used." when there are no curated dataset files detected.
rajivpant@RP-2021-MacBook-Pro rbot % 

```

### Examples of using with Linux/Unix pipes via the command line

Asking it to guess what some of the curated dataset files I use are for

```console
rajivpant@RP-2021-MacBook-Pro rbot % find curated-datasets ../rbot-private/curated-datasets -print | ./rbot.py -d custom-instructions/ curated-datasets/public/ ../rbot-private/curated-datasets/personal/ ../rbot-private/curated-datasets/hearst/ -p "What do you guess these files are for?" 
curated datasets being used:
 - custom-instructions/
 - curated-datasets/public/travel-food.md
 - curated-datasets/public/employment-history.md
 - curated-datasets/public/about.md
 - curated-datasets/public/biography.md
 - ../rbot-private/curated-datasets/personal/accounts.md
 - ../rbot-private/curated-datasets/personal/contact-info.md
 - ../rbot-private/curated-datasets/personal/personal-family.md
 - ../rbot-private/curated-datasets/hearst/hearst.md
Using AI engine openai with model gpt-4
These files appear to be related to the curated-datasets of an AI system, likely for generating text or providing assistance based on the provided information. The files seem to be divided into two categories: public and private.

Public files:
- curated-datasets/public/travel-food.md: Rajiv's travel and food preferences
- curated-datasets/public/employment-history.md: Rajiv's employment history
- curated-datasets/public/about.md: General information about Rajiv
- curated-datasets/public/biography.md: Biography of Rajiv

Private files (stored in a separate private folder):
- curated-datasets/personal/accounts.md: Semi-private personal account information, such as frequent flyer numbers or loyalty programs. Does not contain any confidential or sensitive information.
- curated-datasets/personal/contact-info.md: Personal contact information, such as phone numbers and email addresses. Does not contain any confidential or sensitive information.
- curated-datasets/personal/personal-family.md: Personal and family information, such as family members and relationships. Does not contain any confidential or sensitive information.

Hearst-specific files:
- curated-datasets/hearst/hearst.md: Non-confidential, publicly available information related to the Hearst corporation, including Rajiv's role there

Overall, these files seem to contain various information about a person, their preferences, and professional background, likely used to tailor the AI system's responses and assistance.
rajivpant@RP-2021-MacBook-Pro rbot % 
```

Asking technical questions about a project

> ❗️ In the current version of rbot, the --stdin and --prompt options are mutually exclusive, so the following example no longer works as is. In a future update to this README file, I will give an alternate example to obtain the similar results.
```console
alexredmon@ar-macbook ~/s/scribe > cat docker-compose.yml | rbot --stdin -p "which services will be exposed on which ports by running all services in the following docker-compose.yml file?" 
In the given docker-compose.yml file, the following services are exposed on their respective ports:
1. "scribe" service: - Exposed on port 80 - Exposed on port 9009 (mapped to internal port 9009)
2. "scribe-feature" service: - Exposed on port 80
3. "scribe-redis" service: - Exposed on port 6379 (mapped to internal port 6379)
alexredmon@ar-macbook ~/s/scribe >
```

### Just for fun

Using the Anthropic engine with the Claude Instant model

```console
rajivpant@RP-2021-MacBook-Pro rbot % ./rbot.py -e anthropic -m "claude-instant-v1" -p "Tell me 5 fun things to do in NYC."
No curated dataset files are being used.
Using AI engine anthropic with model claude-instant-v1
 Here are 5 fun things to do in NYC:

1. Visit Central Park. Walk the paths, rent a paddle boat, visit the zoo, catch a Shakespeare in the Park performance.

2. Catch a Broadway show. New York is the center of the theater world with some of the greatest plays and musicals on Broadway and off Broadway. 

3. Go to the top of the Empire State Building. Take in the panoramic views of all of NYC from one of its most famous landmarks. 

4. Shop and dine in SoHo and the West Village. Explore trendy boutique shops and dig into meals at charming sidewalk cafes.  

5. Take a free walking tour. There are numerous companies that offer guided walking tours of various NYC neighborhoods, covering history, culture, architecture and more.
rajivpant@RP-2021-MacBook-Pro rbot % 
```


Random Creativity

> ❗️ In the current version of rbot, the --stdin and --prompt options are mutually exclusive, so the following example no longer works as is. In a future update to this README file, I will give an alternate example to obtain the similar results.
```console
alexredmon@ar-macbook ~ > cat names.csv 
rajiv,
jim,
dennis,
alexandria
alexredmon@ar-macbook ~ > catnames.csv | rbot.py --stdin -p "Generate a creative nickname for each of the following people" 
rajiv, Rajiv Razzle-Dazzle
jim, Jolly JimJam
dennis, Daring Denmaster
alexandria, All-Star Alexi
alexredmon@ar-macbook ~ >
```
