# helpers.py
# Shared functions used by rbot.py and rbot-streamlit.py
# Author: Rajiv Pant

import os
import glob
import yaml
import pathlib
import tiktoken
from litellm import completion

def load_config(config_file):
    """Load configuration from YAML."""
    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)
    return config

def load_profiles(profiles_file):
    """Load profiles from YAML."""
    with open(profiles_file, 'r') as stream:
        profiles = yaml.safe_load(stream)
    return profiles['profiles']


def discover_workspaces(data_root):
    """
    Discover all workspaces by scanning the workspaces directory for workspace.yaml files.

    Args:
        data_root: Root directory containing the workspaces folder

    Returns:
        List of workspace dictionaries with 'name', 'path', and 'config' keys
    """
    workspaces_dir = os.path.join(data_root, 'workspaces')
    discovered = []

    if not os.path.isdir(workspaces_dir):
        return discovered

    for workspace_name in os.listdir(workspaces_dir):
        workspace_path = os.path.join(workspaces_dir, workspace_name)
        workspace_yaml = os.path.join(workspace_path, 'workspace.yaml')

        if os.path.isdir(workspace_path) and os.path.isfile(workspace_yaml):
            with open(workspace_yaml, 'r') as f:
                config = yaml.safe_load(f)

            discovered.append({
                'name': config.get('name', workspace_name),
                'path': workspace_path,
                'dir_name': workspace_name,
                'config': config
            })

    # Sort by name for consistent ordering
    discovered.sort(key=lambda x: x['name'])
    return discovered


def resolve_workspace_paths(workspace, data_root, all_workspaces=None, resolved_chain=None):
    """
    Resolve a workspace's content paths including inherited workspaces.

    Each workspace can have:
    - instructions/ folder: identity and instruction files
    - runbooks/ folder: how-to guides and procedures
    - datasets/ folder: reference data and context

    Workspaces inherit content from parent workspaces via 'inherits_from'.

    Args:
        workspace: Workspace dictionary from discover_workspaces()
        data_root: Root directory containing the workspaces folder
        all_workspaces: List of all discovered workspaces (for inheritance resolution)
        resolved_chain: Set of workspace names already resolved (to prevent circular inheritance)

    Returns:
        Dictionary with 'instructions' and 'datasets' as lists of absolute paths
    """
    if resolved_chain is None:
        resolved_chain = set()

    config = workspace['config']
    workspace_name = workspace['dir_name']
    workspace_path = workspace['path']

    # Prevent circular inheritance
    if workspace_name in resolved_chain:
        return {'instructions': [], 'datasets': []}
    resolved_chain.add(workspace_name)

    instructions = []
    datasets = []

    # First, resolve inherited workspaces (parent content comes first)
    inherits_from = config.get('inherits_from', [])
    if all_workspaces and inherits_from:
        for parent_name in inherits_from:
            parent_workspace = next(
                (w for w in all_workspaces if w['dir_name'] == parent_name),
                None
            )
            if parent_workspace:
                parent_paths = resolve_workspace_paths(
                    parent_workspace, data_root, all_workspaces, resolved_chain.copy()
                )
                instructions.extend(parent_paths['instructions'])
                datasets.extend(parent_paths['datasets'])

    # Add this workspace's own content folders
    # Instructions folder (identity, instructions)
    instructions_dir = os.path.join(workspace_path, 'instructions')
    if os.path.isdir(instructions_dir):
        instructions.append(instructions_dir)

    # Runbooks folder (how-to guides) - goes to instructions
    runbooks_dir = os.path.join(workspace_path, 'runbooks')
    if os.path.isdir(runbooks_dir):
        instructions.append(runbooks_dir)

    # Datasets folder (reference data, context)
    datasets_dir = os.path.join(workspace_path, 'datasets')
    if os.path.isdir(datasets_dir):
        datasets.append(datasets_dir)

    # Include any files directly in the workspace (excluding workspace.yaml)
    for item in os.listdir(workspace_path):
        item_path = os.path.join(workspace_path, item)
        if item != 'workspace.yaml' and os.path.isfile(item_path):
            datasets.append(item_path)

    return {'instructions': instructions, 'datasets': datasets}


def workspace_to_profile(workspace, data_root, all_workspaces=None):
    """
    Convert a workspace to the profile format expected by existing Ragbot code.

    Args:
        workspace: Workspace dictionary from discover_workspaces()
        data_root: Root directory containing workspaces, instructions, datasets folders
        all_workspaces: List of all discovered workspaces (for inheritance resolution)

    Returns:
        Dictionary in profile format: {'name': ..., 'instructions': [...], 'datasets': [...]}
    """
    resolved = resolve_workspace_paths(workspace, data_root, all_workspaces)

    return {
        'name': workspace['name'],
        'instructions': resolved['instructions'],
        'datasets': resolved['datasets']
    }


def load_workspaces_as_profiles(data_root):
    """
    Discover workspaces and convert them to profiles format for compatibility.

    This is the main entry point for workspace-based profile loading.

    Args:
        data_root: Root directory containing workspaces folder

    Returns:
        List of profiles in the format: [{'name': ..., 'instructions': [...], 'datasets': [...]}, ...]
    """
    workspaces = discover_workspaces(data_root)
    profiles = []

    for workspace in workspaces:
        profile = workspace_to_profile(workspace, data_root, workspaces)
        profiles.append(profile)

    # Add a "none" option
    profiles.append({
        'name': '(none - no workspace)',
        'instructions': [],
        'datasets': []
    })

    return profiles

def process_file(filepath, file_type, index):
    """
    Helper function to read and format the content of a file using standard document block format.

    This uses a format similar to Anthropic Claude's document format, which is more standard
    and widely recognized by LLMs than custom XML-like tags.

    Args:
        filepath: Path to the file to process
        file_type: Type of file (e.g., 'custom_instructions', 'curated_datasets')
        index: Numeric index for the document

    Returns:
        Tuple of (formatted_content, filepath)
    """
    with open(filepath, "r") as file:
        file_content = file.read()

    # Use standard document block format similar to Anthropic Claude
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
    files_list = []  # to store file names
    document_index = 1  # Start indexing from 1

    for path in file_paths:
        if os.path.isfile(path):
            content, filename = process_file(path, file_type, document_index)
            files_content.append(content)
            files_list.append(filename)  # save file name
            document_index += 1
        elif os.path.isdir(path):
            for filepath in glob.glob(os.path.join(path, "**/*"), recursive=True):
                if os.path.isfile(filepath):
                    content, filename = process_file(filepath, file_type, document_index)
                    files_content.append(content)
                    files_list.append(filename)  # save file name
                    document_index += 1

    # Wrap all documents in a documents container for better structure
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

# Use cl100k_base encoding - compatible with GPT-4, Claude, and most modern LLMs
# This is a reasonable approximation for token counting across providers
_tokenizer = None

def get_tokenizer():
    """Get or create a cached tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding('cl100k_base')
    return _tokenizer

def count_tokens_from_text(text):
    """Count tokens in a text string using cl100k_base encoding.

    This provides a reasonable approximation for most modern LLMs including
    GPT-4, Claude, and Gemini models.
    """
    if not text:
        return 0
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def count_tokens(file_paths):
    """Count tokens in a list of files (legacy function for backwards compatibility)."""
    tokenizer = get_tokenizer()
    total_tokens = 0
    for file_path in file_paths:
        with open(file_path, 'r') as file:
            content = file.read()
            total_tokens += len(tokenizer.encode(content))
    return total_tokens

def count_custom_instructions_tokens(custom_instruction_path):
    """Count tokens in custom instructions files (legacy function)."""
    _, custom_instruction_files = load_files(file_paths=custom_instruction_path, file_type="custom_instructions")
    return count_tokens(custom_instruction_files)

def count_curated_datasets_tokens(curated_dataset_path):
    """Count tokens in curated datasets files (legacy function)."""
    _, curated_dataset_files = load_files(file_paths=curated_dataset_path, file_type="curated_datasets")
    return count_tokens(curated_dataset_files)


def print_saved_files(directory):
    """Print the list of saved JSON files in the sessions directory."""
    sessions_directory = os.path.join(directory, "sessions")
    print("Currently saved JSON files:")
    for file in pathlib.Path(sessions_directory).glob("*.json"):
        print(f" - {file.name}")


def compact_history(history, max_tokens, system_tokens=0, current_prompt_tokens=0, reserve_for_response=4096):
    """
    Compact conversation history to fit within token limits.

    Uses a sliding window approach: keeps the most recent messages while ensuring
    the total fits within the context window. Older messages are summarized or dropped.

    Args:
        history: List of message dicts with 'role' and 'content'
        max_tokens: Maximum context window size
        system_tokens: Tokens used by system message (instructions + datasets)
        current_prompt_tokens: Tokens in the current user prompt
        reserve_for_response: Tokens to reserve for the model's response

    Returns:
        Compacted history list
    """
    if not history:
        return []

    # Calculate available tokens for history
    available_for_history = max_tokens - system_tokens - current_prompt_tokens - reserve_for_response

    if available_for_history <= 0:
        # No room for history, return empty
        return []

    # Count tokens in each message and build from most recent
    tokenizer = get_tokenizer()
    compacted = []
    total_tokens = 0

    # Process history from newest to oldest (reverse order)
    for msg in reversed(history):
        msg_tokens = len(tokenizer.encode(msg['content']))
        # Add ~4 tokens overhead per message for role and formatting
        msg_tokens += 4

        if total_tokens + msg_tokens <= available_for_history:
            compacted.insert(0, msg)  # Insert at beginning to maintain order
            total_tokens += msg_tokens
        else:
            # Can't fit more messages
            break

    return compacted


def chat(
    prompt,
    curated_datasets,
    custom_instructions,
    model,
    max_tokens,
    max_input_tokens=128000,
    stream=True,
    request_timeout=15,
    temperature=0.75,
    history=None,
    engine="openai",
    interactive=False,
    new_session=False,
    supports_system_role=True,
    stream_callback=None
):
    """
    Send a request to the LLM API with the provided prompt and conversation history.

    :param prompt: The user's input to generate a response for.
    :param curated_datasets: Context documents as a string.
    :param custom_instructions: Custom instructions as a string.
    :param model: The name of the model to use.
    :param max_tokens: The maximum number of tokens to generate in the response.
    :param max_input_tokens: The model's context window size (for history compaction).
    :param stream: Whether to stream the response from the API (default is True).
    :param request_timeout: The request timeout in seconds (default is 15).
    :param temperature: The creativity of the response (default is 0.75).
    :param history: The conversation history as a list of message dicts.
    :param engine: The engine to use for the chat (default is 'openai').
    :param interactive: Whether the chat is in interactive mode (default is False).
    :param new_session: Whether this is a new session (default is False).
    :param supports_system_role: Whether the model supports the "system" role (default is True).
    :param stream_callback: Optional callback function for streaming output. Called with each chunk.
    :return: The generated response text from the model.
    """
    # Build system content from instructions and datasets
    system_content = ""
    if custom_instructions:
        system_content = custom_instructions
    if curated_datasets:
        system_content = system_content + "\n" + curated_datasets if system_content else curated_datasets

    # Calculate token usage for system content and current prompt
    system_tokens = count_tokens_from_text(system_content) if system_content else 0
    prompt_tokens = count_tokens_from_text(prompt)

    # Compact history to fit within context window
    compacted_history = []
    if history and len(history) > 0:
        # Don't include the current prompt in history (it's passed separately)
        # History should contain previous turns only
        past_history = [msg for msg in history if msg.get('content') != prompt]
        compacted_history = compact_history(
            past_history,
            max_tokens=max_input_tokens,
            system_tokens=system_tokens,
            current_prompt_tokens=prompt_tokens,
            reserve_for_response=max_tokens
        )

    # Build messages list
    if supports_system_role:
        messages = []

        # Add system message if there's content
        if system_content.strip():
            messages.append({"role": "system", "content": system_content})

        # Add compacted conversation history
        messages.extend(compacted_history)

        # Add current user prompt
        messages.append({"role": "user", "content": prompt})
    else:
        # For models that don't support system role (like some Google models)
        messages = []
        if custom_instructions:
            messages.append({"role": "user", "content": custom_instructions})
            messages.append({"role": "assistant", "content": "I understand. I'll follow these instructions."})
        if curated_datasets:
            messages.append({"role": "user", "content": curated_datasets})
            messages.append({"role": "assistant", "content": "I've reviewed the context information provided."})

        # Add compacted conversation history
        messages.extend(compacted_history)

        # Add current user prompt
        messages.append({"role": "user", "content": prompt})

    # Make the API call
    if stream and interactive:
        # Streaming mode for interactive sessions
        response_chunks = []
        llm_response = completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )

        for chunk in llm_response:
            if chunk and chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    response_chunks.append(delta.content)
                    if stream_callback:
                        stream_callback(delta.content)
                    elif interactive:
                        # Print directly for CLI interactive mode
                        print(delta.content, end='', flush=True)

        if interactive and not stream_callback:
            print()  # Newline after streaming completes

        response = ''.join(response_chunks)
    else:
        # Non-streaming mode
        llm_response = completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        response = llm_response.get('choices', [{}])[0].get('message', {}).get('content')

    return response
