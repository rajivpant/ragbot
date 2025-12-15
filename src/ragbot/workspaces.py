"""Workspace discovery and management for Ragbot.

This module handles discovering and loading workspaces from ai-knowledge repos.
"""

import os
from typing import Optional, List, Dict, Any
import yaml

from .exceptions import WorkspaceError, WorkspaceNotFoundError
from .models import WorkspaceInfo


# Default locations for ai-knowledge repos
DEFAULT_AI_KNOWLEDGE_PATHS = [
    '/app/ai-knowledge',  # Docker
    os.path.expanduser('~/projects/my-projects/ai-knowledge'),  # Local dev
]


def discover_ai_knowledge_repos(ai_knowledge_root: str) -> Dict[str, Dict[str, Any]]:
    """
    Auto-discover ai-knowledge repos by convention.

    Convention: Any directory matching 'ai-knowledge-*' is recognized as a workspace.

    Args:
        ai_knowledge_root: Root directory containing ai-knowledge-* folders

    Returns:
        Dictionary mapping workspace names to their content and metadata
    """
    discovered = {}

    if not os.path.isdir(ai_knowledge_root):
        return discovered

    for item in os.listdir(ai_knowledge_root):
        if not item.startswith('ai-knowledge-'):
            continue

        repo_path = os.path.join(ai_knowledge_root, item)
        if not os.path.isdir(repo_path):
            continue

        workspace_name = item.replace('ai-knowledge-', '')

        # Read compile-config.yaml for metadata
        config = {}
        compile_config_path = os.path.join(repo_path, 'compile-config.yaml')
        if os.path.isfile(compile_config_path):
            with open(compile_config_path, 'r') as f:
                config = yaml.safe_load(f) or {}

        # Check compiled content locations
        # New flat structure: compiled/{project}/instructions/ and compiled/{project}/knowledge/
        compiled_base = os.path.join(repo_path, 'compiled', workspace_name)
        instructions_dir = os.path.join(compiled_base, 'instructions')
        knowledge_dir = os.path.join(compiled_base, 'knowledge')

        # Check source directory
        source_dir = os.path.join(repo_path, 'source')
        has_source = os.path.isdir(source_dir)
        has_instructions = os.path.isdir(instructions_dir)
        has_knowledge = os.path.isdir(knowledge_dir)

        if has_instructions or has_knowledge or has_source or config:
            discovered[workspace_name] = {
                'instructions': instructions_dir if has_instructions else None,
                'datasets': knowledge_dir if has_knowledge else None,
                'repo_path': repo_path,
                'source_path': source_dir if has_source else None,
                'config': config,
                'has_instructions': has_instructions,
                'has_datasets': has_knowledge,
                'has_source': has_source,
            }

    return discovered


def find_ai_knowledge_root() -> Optional[str]:
    """Find the ai-knowledge root directory.

    Returns:
        Path to ai-knowledge root, or None if not found
    """
    for candidate in DEFAULT_AI_KNOWLEDGE_PATHS:
        if os.path.isdir(candidate):
            return candidate
    return None


def discover_workspaces(ai_knowledge_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discover all workspaces from ai-knowledge repos.

    Args:
        ai_knowledge_root: Optional root directory for ai-knowledge repos

    Returns:
        List of workspace dictionaries
    """
    if ai_knowledge_root is None:
        ai_knowledge_root = find_ai_knowledge_root()

    ai_knowledge_repos = {}
    if ai_knowledge_root:
        ai_knowledge_repos = discover_ai_knowledge_repos(ai_knowledge_root)

    discovered = []

    for workspace_name, content_info in ai_knowledge_repos.items():
        compile_config = content_info.get('config', {})
        project_config = compile_config.get('project', {})

        display_name = project_config.get('name', workspace_name)
        if display_name == workspace_name:
            display_name = workspace_name.replace('-', ' ').title()

        description = project_config.get('description', f'AI Knowledge workspace: {workspace_name}')

        discovered.append({
            'name': display_name,
            'path': None,
            'dir_name': workspace_name,
            'config': {
                'name': display_name,
                'description': description,
                'status': 'active',
                'type': project_config.get('type', 'project'),
                'inherits_from': compile_config.get('inherits_from', []),
            },
            'ai_knowledge': content_info
        })

    discovered.sort(key=lambda x: x['name'])
    return discovered


def resolve_workspace_paths(
    workspace: Dict[str, Any],
    all_workspaces: Optional[List[Dict[str, Any]]] = None,
    resolved_chain: Optional[set] = None
) -> Dict[str, List[str]]:
    """
    Resolve a workspace's content paths including inherited workspaces.

    Args:
        workspace: Workspace dictionary
        all_workspaces: List of all discovered workspaces (for inheritance)
        resolved_chain: Set of already resolved workspace names (prevents cycles)

    Returns:
        Dictionary with 'instructions' and 'datasets' as lists of paths
    """
    if resolved_chain is None:
        resolved_chain = set()

    config = workspace.get('config', {})
    workspace_name = workspace['dir_name']

    if workspace_name in resolved_chain:
        return {'instructions': [], 'datasets': []}
    resolved_chain.add(workspace_name)

    instructions = []
    datasets = []

    # Resolve inherited workspaces first
    inherits_from = config.get('inherits_from', [])
    if all_workspaces and inherits_from:
        for parent_name in inherits_from:
            parent_workspace = next(
                (w for w in all_workspaces if w['dir_name'] == parent_name),
                None
            )
            if parent_workspace:
                parent_paths = resolve_workspace_paths(
                    parent_workspace, all_workspaces, resolved_chain.copy()
                )
                instructions.extend(parent_paths['instructions'])
                datasets.extend(parent_paths['datasets'])

    # Add ai-knowledge compiled content
    ai_knowledge = workspace.get('ai_knowledge', {})
    if ai_knowledge:
        ai_instructions = ai_knowledge.get('instructions')
        ai_datasets = ai_knowledge.get('datasets')

        if ai_instructions and os.path.isdir(ai_instructions):
            instructions.append(ai_instructions)
        if ai_datasets and os.path.isdir(ai_datasets):
            datasets.append(ai_datasets)

        # Fallback to source content
        source_path = ai_knowledge.get('source_path')
        if source_path and os.path.isdir(source_path):
            if not ai_instructions or not os.path.isdir(ai_instructions):
                source_instructions = os.path.join(source_path, 'instructions')
                if os.path.isdir(source_instructions):
                    instructions.append(source_instructions)
                source_runbooks = os.path.join(source_path, 'runbooks')
                if os.path.isdir(source_runbooks):
                    instructions.append(source_runbooks)

            if not ai_datasets or not os.path.isdir(ai_datasets):
                source_datasets = os.path.join(source_path, 'datasets')
                if os.path.isdir(source_datasets):
                    datasets.append(source_datasets)

    return {'instructions': instructions, 'datasets': datasets}


def workspace_to_profile(
    workspace: Dict[str, Any],
    all_workspaces: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Convert a workspace to profile format.

    Args:
        workspace: Workspace dictionary
        all_workspaces: List of all workspaces for inheritance resolution

    Returns:
        Profile dictionary
    """
    resolved = resolve_workspace_paths(workspace, all_workspaces)

    return {
        'name': workspace['name'],
        'dir_name': workspace['dir_name'],
        'instructions': resolved['instructions'],
        'datasets': resolved['datasets'],
        'ai_knowledge': workspace.get('ai_knowledge', {})
    }


def load_workspaces_as_profiles(ai_knowledge_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discover workspaces and convert them to profiles format.

    This is the main entry point for workspace-based profile loading.

    Args:
        ai_knowledge_root: Optional root directory for ai-knowledge repos

    Returns:
        List of profiles
    """
    workspaces = discover_workspaces(ai_knowledge_root)
    profiles = []

    for workspace in workspaces:
        profile = workspace_to_profile(workspace, workspaces)
        profiles.append(profile)

    # Add "none" option
    profiles.append({
        'name': '(none - no workspace)',
        'dir_name': '',
        'instructions': [],
        'datasets': []
    })

    return profiles


def get_workspace(name: str, ai_knowledge_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a specific workspace by name or dir_name.

    Args:
        name: Workspace name or dir_name
        ai_knowledge_root: Optional root directory

    Returns:
        Workspace dictionary

    Raises:
        WorkspaceNotFoundError: If workspace not found
    """
    workspaces = discover_workspaces(ai_knowledge_root)

    for ws in workspaces:
        if ws['name'] == name or ws['dir_name'] == name:
            return workspace_to_profile(ws, workspaces)

    raise WorkspaceNotFoundError(f"Workspace not found: {name}")


def get_workspace_info(workspace: Dict[str, Any]) -> WorkspaceInfo:
    """
    Convert workspace dict to WorkspaceInfo Pydantic model.

    Args:
        workspace: Workspace dictionary

    Returns:
        WorkspaceInfo model
    """
    config = workspace.get('config', {})
    ai_knowledge = workspace.get('ai_knowledge', {})

    return WorkspaceInfo(
        name=workspace['name'],
        dir_name=workspace['dir_name'],
        description=config.get('description'),
        status=config.get('status', 'active'),
        type=config.get('type', 'project'),
        inherits_from=config.get('inherits_from', []),
        has_instructions=ai_knowledge.get('has_instructions', False),
        has_datasets=ai_knowledge.get('has_datasets', False),
        has_source=ai_knowledge.get('has_source', False),
        repo_path=ai_knowledge.get('repo_path'),
    )


def list_workspace_info(ai_knowledge_root: Optional[str] = None) -> List[WorkspaceInfo]:
    """
    Get list of all workspaces as WorkspaceInfo models.

    Args:
        ai_knowledge_root: Optional root directory

    Returns:
        List of WorkspaceInfo models
    """
    workspaces = discover_workspaces(ai_knowledge_root)
    return [get_workspace_info(ws) for ws in workspaces]


# Mapping from engine name to instruction file
ENGINE_TO_INSTRUCTION_FILE = {
    'anthropic': 'claude.md',
    'openai': 'chatgpt.md',
    'google': 'gemini.md',
}

# Fallback order if preferred file doesn't exist
INSTRUCTION_FALLBACK_ORDER = ['claude.md', 'chatgpt.md', 'gemini.md']


def get_llm_specific_instruction_path(
    workspace_name: str,
    engine: str = 'anthropic',
    ai_knowledge_root: Optional[str] = None
) -> Optional[str]:
    """
    Get the path to the LLM-specific compiled instruction file for a workspace.

    The compiler generates separate instruction files for each LLM platform:
    - claude.md for Anthropic models
    - chatgpt.md for OpenAI models
    - gemini.md for Google Gemini models

    Args:
        workspace_name: Name of the workspace (e.g., 'personal', 'flatiron')
        engine: LLM engine name ('anthropic', 'openai', 'google')
        ai_knowledge_root: Optional root directory for ai-knowledge repos

    Returns:
        Path to the instruction file, or None if not found
    """
    if ai_knowledge_root is None:
        ai_knowledge_root = find_ai_knowledge_root()

    if not ai_knowledge_root:
        return None

    # Build path to compiled instructions
    repo_path = os.path.join(ai_knowledge_root, f'ai-knowledge-{workspace_name}')
    instructions_dir = os.path.join(repo_path, 'compiled', workspace_name, 'instructions')

    if not os.path.isdir(instructions_dir):
        return None

    # Get preferred instruction file for this engine
    preferred_file = ENGINE_TO_INSTRUCTION_FILE.get(engine, 'claude.md')
    preferred_path = os.path.join(instructions_dir, preferred_file)

    if os.path.isfile(preferred_path):
        return preferred_path

    # Try fallbacks
    for fallback in INSTRUCTION_FALLBACK_ORDER:
        fallback_path = os.path.join(instructions_dir, fallback)
        if os.path.isfile(fallback_path):
            return fallback_path

    return None
