#!/usr/bin/env python3
# generate_prompt_template.py - https://github.com/rajivpant/ragbot

import os
from helpers import load_files, load_profiles
import argparse

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
    """Parses arguments and generates the prompt template."""

    # Load profile names for choices
    profile_names = [profile['name'] for profile in load_profiles("profiles.yaml")]

    parser = argparse.ArgumentParser(description="Generates a prompt template for AI assistants.")
    parser.add_argument("--profile", required=True, choices=profile_names, help="Name of the profile to use.")
    parser.add_argument("--output", required=True, help="Output file name for the prompt template.")
    args = parser.parse_args()

    try:
        profile_data = next(profile for profile in load_profiles("profiles.yaml") if profile["name"] == args.profile)
        custom_instructions, _ = load_files(profile_data.get("custom_instructions", []), file_type="custom_instructions")
        curated_datasets, _ = load_files(profile_data.get("curated_datasets", []), file_type="curated_datasets")
        generate_prompt_template(custom_instructions, curated_datasets, args.output)
        print(f"Prompt template generated successfully: {args.output}")
    except Exception as e:
        print(f"Error generating prompt template: {e}")

if __name__ == '__main__':
    main()