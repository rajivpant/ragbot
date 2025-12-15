# helpers.py
# Shared functions used by ragbot.py and ragbot_streamlit.py
# Author: Rajiv Pant
#
# This module provides a compatibility layer that re-exports from the ragbot library.
# For new code, prefer importing directly from 'ragbot'.

import os
import sys

# Add src directory to path to enable ragbot package imports
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Re-export everything from ragbot package
from ragbot import (
    # Config
    load_yaml_config,
    load_data_config,
    get_all_models,
    get_model_info,
    get_default_model,
    get_available_models,
    check_api_keys,
    # Core
    chat,
    chat_stream,
    count_tokens,
    compact_history,
    # Workspaces
    discover_ai_knowledge_repos,
    discover_workspaces,
    find_ai_knowledge_root,
    resolve_workspace_paths,
    workspace_to_profile,
    load_workspaces_as_profiles,
    get_workspace,
    get_workspace_info,
    list_workspace_info,
    # Exceptions
    RagbotError,
    ConfigurationError,
    WorkspaceError,
    WorkspaceNotFoundError,
    ChatError,
    RAGError,
    IndexingError,
)
from ragbot.core import get_tokenizer

# Alias for compatibility
count_tokens_from_text = count_tokens

# Additional utility imports
import glob
import yaml
import pathlib
import tiktoken


def load_config(config_file):
    """Load configuration from YAML."""
    return load_yaml_config(config_file)


def process_file(filepath, file_type, index):
    """
    Helper function to read and format the content of a file using standard document block format.

    Args:
        filepath: Path to the file to process
        file_type: Type of file (e.g., 'custom_instructions', 'curated_datasets')
        index: Numeric index for the document

    Returns:
        Tuple of (formatted_content, filepath)
    """
    with open(filepath, "r") as file:
        file_content = file.read()

    full_content = f"""<document index="{index}">
<source>{filepath}</source>
<document_type>{file_type}</document_type>
<document_content>
{file_content}
</document_content>
</document>
"""
    return full_content, filepath


def load_files(file_paths, file_type):
    """
    Load files containing custom instructions or curated datasets.

    Returns files formatted using standard document block format with sequential indexing.
    """
    files_content = []
    files_list = []
    document_index = 1

    for path in file_paths:
        if os.path.isfile(path):
            content, filename = process_file(path, file_type, document_index)
            files_content.append(content)
            files_list.append(filename)
            document_index += 1
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "**/*"), recursive=True):
                if os.path.isfile(filepath):
                    content, filename = process_file(filepath, file_type, document_index)
                    files_content.append(content)
                    files_list.append(filename)
                    document_index += 1

    if files_content:
        files_content_str = "<documents>\n" + "\n".join(files_content) + "</documents>"
    else:
        files_content_str = ""

    return files_content_str, files_list


def human_format(num):
    """Convert a number to a human-readable format."""
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'k', 'M', 'B', 'T'][magnitude])


def count_tokens_for_files(file_paths):
    """Count tokens in a list of files."""
    tokenizer = get_tokenizer()
    total_tokens = 0
    for file_path in file_paths:
        with open(file_path, 'r') as file:
            content = file.read()
            total_tokens += len(tokenizer.encode(content))
    return total_tokens


def count_custom_instructions_tokens(custom_instruction_path):
    """Count tokens in custom instructions files."""
    _, custom_instruction_files = load_files(file_paths=custom_instruction_path, file_type="custom_instructions")
    return count_tokens_for_files(custom_instruction_files)


def count_curated_datasets_tokens(curated_dataset_path):
    """Count tokens in curated datasets files."""
    _, curated_dataset_files = load_files(file_paths=curated_dataset_path, file_type="curated_datasets")
    return count_tokens_for_files(curated_dataset_files)


def print_saved_files(directory):
    """Print the list of saved JSON files in the sessions directory."""
    sessions_directory = os.path.join(directory, "sessions")
    print("Currently saved JSON files:")
    for file in pathlib.Path(sessions_directory).glob("*.json"):
        print(f" - {file.name}")
