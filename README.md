# rbot

🤖 rbot is a chatbot powered by OpenAI's GPT-4 model, developed by Rajiv Pant ([rajivpant](https://github.com/rajivpant)) and inspired by prior work done by Jim Mortko ([jskills](https://github.com/jskills)) and Alexandria Redmon ([alexdredmon](https://github.com/alexdredmon)).

It offers engaging conversations with a personalized touch and advanced context understanding. rbot processes user prompts and custom conversation decorators, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.

🚀 Rajiv's GPT-4 based chatbot that processes user prompts and custom conversation decorators, enabling more context-aware responses than out-of-the-box ChatGPT Plus with GPT-4.

🧠 Custom conversation decorators help the chatbot better understand the context, resulting in more accurate and relevant responses, surpassing the capabilities of standard GPT-4 implementations.

A Django web app for rbot is currently under development. Stay tuned for updates on this project!

## Blog Post Introducing rbot
[Introducing Rbot: A Personalized AI Assistant, Written by Rbot](https://rajiv.com/blog/2023/05/08/introducing-rbot-a-personalized-ai-assistant-written-by-rbot/)

Excerpt from the blog post:
### Rbot: Offering Personalized Assistance Beyond ChatGPT Plus, Bing Chat, and Google Bard Currently Offer

As an AI assistant, I provide a unique level of personalization and adaptability that sets me apart from current implementations of ChatGPT Plus, Bing Chat, and Google Bard. By using folders containing customized decorator files, I can cater to multiple use cases, such as personal life, work, education, and specific projects. This customization enables me to understand and support you in a way that is tailored to your unique needs.

#### Serving as Your Personal Life Assistant

You can create a folder with decorator files that include personal information, family details, travel and food preferences, and more. By using this information, I can function as your personal life assistant, offering AI-powered recommendations and support tailored to your specific context.

#### Assisting You in Your Professional Life

Similarly, you can develop another folder containing decorator files related to your work life. These files might include details about your job, industry, colleagues, projects, and other work-related information. With this context, I can help you with various tasks, such as drafting emails, scheduling meetings, conducting research, and more, enhancing your efficiency and organization.

#### Supporting Your Educational Goals

You can also customize me for educational purposes by creating a folder with decorator files containing information about your academic background, subjects of interest, courses, and other educational details. In this role, I can provide personalized educational support, from helping with homework to explaining complex concepts or recommending learning resources.

#### Providing Project-Specific Help

In addition to the use cases mentioned above, I can be tailored to support you on specific projects. By creating a folder with decorator files containing project-related information, such as objectives, team members, deadlines, and relevant resources, I can assist you throughout the project lifecycle, offering valuable insights and support tailored to each unique project.

My ability to create distinct profiles for different needs using customized decorator files sets me apart from ChatGPT Plus, Bing Chat, and Google Bard. This versatility enables me to offer personalized assistance across multiple aspects of your life, ensuring that I can understand and cater to your specific requirements.


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

### Using decorator files
To use rbot, you can provide a prompt and a conversation decorator file or a folder containing multiple decorator files. You can view an example of a decorator file at
https://github.com/rajivpant/rbot/blob/main/fine-tuning/biography.md

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


### Examples of using with Linux/Unix pipes via the command line

Asking it to guess what some of the decorator files I use are for
```
rajiv@RP-2023-MacBook-Air rbot % ls ../rajiv-llms/fine-tuning | ./rbot.py -p "What do you guess these files are for?" -d ../rajiv-llms/fine-tuning 
These files likely contain various sections of information related to Rajiv Pant. The file names suggest the following content:

1. `about.md`: A general overview or introduction about Rajiv Pant.
2. `biography.md`: A detailed biography of Rajiv Pant, including his professional background, experience, and achievements.
3. `contact-info.md`: Contact information for Rajiv Pant, including email addresses, phone numbers, and other relevant communication details.
4. `example-client.md`: Information related to Rajiv Pant's role and responsibilities at Example-Client Magazines, including his direct reports, teams, and peers within the company.
5. `personal-family.md`: Personal and family information about Rajiv Pant, including details about his family members, relationships, and other relevant personal details.
6. `travel-food.md`: Rajiv Pant's preferences, requirements, and other relevant information related to travel and food. This may include information about his preferred airlines, seating preferences, food choices, and other travel-related details.
rajiv@RP-2023-MacBook-Air rbot % 
```


Asking technical questions about a project
```
alex.redmon@a-workstation ~/s/scribe (master)> cat docker-compose.yml | rbot -p "which services will be exposed on which ports by running all services in the following docker-compose.yml file?"
In the given docker-compose.yml file, the following services are exposed on their respective ports:

1. `scribe` service:
   - Exposed on port 80
   - Exposed on port 9009 (mapped to internal port 9009)

2. `scribe-feature` service:
   - Exposed on port 80

3. `scribe-redis` service:
   - Exposed on port 6379 (mapped to internal port 6379)
```

Just for fun
```
> cat names.csv
name,nickname
rajiv,
jim,
dennis,
alexandria,

> cat names.csv | rbot -p 'generate a creative nickname for each of the following people'
name,nickname
rajiv,Rajiv Razzle-Dazzle
jim,Jolly JimJam
dennis,Daring Denmaster
alexandria,All-Star Alexi
```