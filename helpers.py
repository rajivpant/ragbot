# helpers.py
# Shared functions used by rbot.py and rbot-streamlit.py
# Author: Rajiv Pant

import os
import glob
import yaml
import pathlib

# Function to load configuration from YAML
def load_config(config_file):
    """Load configuration from YAML."""
    with open(config_file, 'r') as stream:
        return yaml.safe_load(stream)


def load_decorator_files(decorator_path):
    """Load decorator files."""
    decorators = []
    decorator_files = []  # to store file names of decorators
    for path in decorator_path:
        if os.path.isfile(path):
            with open(path, "r") as file:
                decorators.append(file.read())
                decorator_files.append(path)  # save file name
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "*")):
                if os.path.isfile(filepath):  # Check if the path is a file
                    with open(filepath, "r") as file:
                        decorators.append(file.read())
                        decorator_files.append(filepath)  # save file name
    return decorators, decorator_files


def print_saved_files(directory):
    sessions_directory = os.path.join(directory, "sessions")
    print("Currently saved JSON files:")
    for file in pathlib.Path(sessions_directory).glob("*.json"):
        print(f" - {file.name}")
