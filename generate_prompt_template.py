#!/usr/bin/env python3
# generate_prompt_template.py - https://github.com/rajivpant/ragbot

import os
import argparse

def concatenate_files(directories, output_file, recursive=False):
    content = ""
    for directory in directories:
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        with open(file_path, 'r') as infile:
                            content += f"# {file}\n\n"
                            content += infile.read()
                            content += "\n\n---\n\n"
        else:
            for file in os.listdir(directory):
                if file.endswith('.md'):
                    file_path = os.path.join(directory, file)
                    with open(file_path, 'r') as infile:
                        content += f"# {file}\n\n"
                        content += infile.read()
                        content += "\n\n---\n\n"
    return content.strip()

def generate_prompt_template(instructions_content, datasets_content, output_file):
    prompt_template = f"""
<prompt>
You are an AI assistant created to be helpful, harmless, and honest. Your role is to provide guidance, advice, and assistance to the user, drawing upon the custom instructions and curated datasets provided in the attached files.

When responding, please adhere to the following guidelines:
- Carefully review the custom instructions in the 'instructions.md' file and ensure your responses align with the specified guidelines, communication style, and preferences.
- Refer to the relevant information in the 'datasets.md' file to provide informed and personalized responses when applicable.
- If you are unsure about something or if the curated datasets don't cover the specific query, it's okay to say that you don't have enough information to provide a complete answer.
- Always prioritize being helpful, truthful, and aligned with the user's best interests.
- If there are any contradictions or inconsistencies between the query and the provided custom instructions or curated datasets, seek clarification before responding.

<documents>
<document index="1">
<source>instructions.md</source>
<document_content>
{instructions_content}
</document_content>
</document>

<document index="2">
<source>datasets.md</source>
<document_content>
{datasets_content}
</document_content>
</document>
</documents>

[User Query Here]

</prompt>
"""
    with open(output_file, 'w') as outfile:
        outfile.write(prompt_template)

def main():
    parser = argparse.ArgumentParser(description='Generate a prompt template with concatenated instructions and datasets')
    parser.add_argument('-i', '--instructions', help='Directories containing custom instructions', nargs='+', required=True)
    parser.add_argument('-d', '--datasets', help='Directories containing curated datasets', nargs='+', required=True)
    parser.add_argument('-o', '--output', help='Output file for the prompt template', required=True)
    parser.add_argument('-r', '--recursive', help='Search for .md files recursively in subdirectories', action='store_true', default=False)

    args = parser.parse_args()

    instructions_content = concatenate_files(args.instructions, "", args.recursive)
    datasets_content = concatenate_files(args.datasets, "", args.recursive)

    generate_prompt_template(instructions_content, datasets_content, args.output)

if __name__ == '__main__':
    main()