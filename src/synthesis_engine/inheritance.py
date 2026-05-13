"""Workspace Inheritance.

Substrate-level workspace-bootstrap module. Reads the centralised
``my-projects.yaml`` from an operator's personal AI Knowledge repo, resolves
the inheritance graph between workspaces, and manages cloning or pulling of
the parent repositories that each workspace depends on. This is the substrate
counterpart that runtimes (Ragbot, Ragenie, the compiler) import to discover
which repos a workspace inherits from and to ensure those repos are present
on disk before any further work happens.

Public API:
    load_inheritance_config(path) -> Dict[str, Any]
    find_inheritance_config(personal_repo_path) -> Optional[str]
    get_project_config(project_name, inheritance_config) -> Dict[str, Any]
    get_inheritance_chain(project_name, inheritance_config, visited=None)
        -> List[str]
    resolve_dependencies(project_name, inheritance_config)
        -> List[Dict[str, Any]]
    clone_or_pull_repo(repo_url, local_path, quiet=True) -> bool
    ensure_repos_available(dependencies, base_path, github_user=None)
        -> Dict[str, Any]
    get_repo_source_path(repo_path) -> str
    create_default_inheritance_config(personal_repo_path,
                                      ai_knowledge_base_path)
        -> Dict[str, Any]
"""

import os
import subprocess
from typing import Any, Dict, List, Optional, Set

import yaml


__all__ = [
    "load_inheritance_config",
    "find_inheritance_config",
    "get_project_config",
    "get_inheritance_chain",
    "resolve_dependencies",
    "clone_or_pull_repo",
    "ensure_repos_available",
    "get_repo_source_path",
    "create_default_inheritance_config",
]


def load_inheritance_config(config_path: str) -> Dict[str, Any]:
    """
    Load inheritance configuration from my-projects.yaml.

    Args:
        config_path: Path to my-projects.yaml

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Inheritance config not found at {config_path}")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def find_inheritance_config(personal_repo_path: str) -> Optional[str]:
    """
    Find the my-projects.yaml file in a personal repo.

    Args:
        personal_repo_path: Path to the personal ai-knowledge repo

    Returns:
        Path to my-projects.yaml if found, None otherwise
    """
    possible_paths = [
        os.path.join(personal_repo_path, 'my-projects.yaml'),
        os.path.join(personal_repo_path, 'source', 'my-projects.yaml'),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def get_project_config(project_name: str,
                       inheritance_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get configuration for a specific project from inheritance config.

    Args:
        project_name: Name of the project
        inheritance_config: Loaded inheritance configuration

    Returns:
        Project configuration dictionary
    """
    projects = inheritance_config.get('projects', {})
    return projects.get(project_name, {})


def get_inheritance_chain(project_name: str,
                          inheritance_config: Dict[str, Any],
                          visited: Optional[Set[str]] = None) -> List[str]:
    """
    Build the inheritance chain for a project (parent-first order).

    Args:
        project_name: Name of the project
        inheritance_config: Loaded inheritance configuration
        visited: Set of already visited projects (for cycle detection)

    Returns:
        List of project names in inheritance order (parents first)

    Raises:
        ValueError: If circular dependency detected
    """
    if visited is None:
        visited = set()

    if project_name in visited:
        raise ValueError(f"Circular dependency detected involving '{project_name}'")

    visited.add(project_name)

    project_config = get_project_config(project_name, inheritance_config)
    inherits_from = project_config.get('inherits_from', [])

    if isinstance(inherits_from, str):
        inherits_from = [inherits_from]

    chain: List[str] = []

    # Recursively resolve parent chains
    for parent in inherits_from:
        parent_chain = get_inheritance_chain(parent, inheritance_config, visited.copy())
        for p in parent_chain:
            if p not in chain:
                chain.append(p)

    # Add this project at the end
    chain.append(project_name)

    return chain


def resolve_dependencies(project_name: str,
                         inheritance_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Resolve all repository dependencies for a project.

    Args:
        project_name: Name of the project
        inheritance_config: Loaded inheritance configuration

    Returns:
        List of dicts with 'name', 'repo', 'local_path', 'config' for each
        dependency
    """
    chain = get_inheritance_chain(project_name, inheritance_config)
    dependencies: List[Dict[str, Any]] = []

    for name in chain:
        project_config = get_project_config(name, inheritance_config)
        repo = project_config.get('repo', f'ai-knowledge-{name}')
        local_path = project_config.get('local_path')

        dependencies.append({
            'name': name,
            'repo': repo,
            'local_path': local_path,
            'config': project_config
        })

    return dependencies


def clone_or_pull_repo(repo_url: str, local_path: str, quiet: bool = True) -> bool:
    """
    Clone a repository if it doesn't exist, or pull if it does.

    Args:
        repo_url: Git repository URL
        local_path: Local path to clone to
        quiet: Suppress git output

    Returns:
        True if successful, False otherwise
    """
    quiet_flags = ['--quiet'] if quiet else []

    if os.path.exists(local_path):
        # Pull latest changes
        try:
            subprocess.run(
                ['git', 'pull'] + quiet_flags,
                cwd=local_path,
                check=True,
                capture_output=quiet
            )
            return True
        except subprocess.CalledProcessError:
            return False
    else:
        # Clone the repository
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            subprocess.run(
                ['git', 'clone'] + quiet_flags + [repo_url, local_path],
                check=True,
                capture_output=quiet
            )
            return True
        except subprocess.CalledProcessError:
            return False


def ensure_repos_available(dependencies: List[Dict[str, Any]],
                           base_path: str,
                           github_user: Optional[str] = None) -> Dict[str, Any]:
    """
    Ensure all dependency repos are available locally.

    Args:
        dependencies: List of dependency dicts from resolve_dependencies
        base_path: Base path where repos should be located
        github_user: GitHub username for constructing URLs

    Returns:
        Dict with 'success', 'available', 'missing', 'errors'
    """
    result: Dict[str, Any] = {
        'success': True,
        'available': [],
        'missing': [],
        'errors': []
    }

    for dep in dependencies:
        name = dep['name']
        local_path = dep.get('local_path')

        if not local_path:
            # Construct default local path
            local_path = os.path.join(base_path, f'ai-knowledge-{name}')

        if os.path.exists(local_path):
            result['available'].append({
                'name': name,
                'path': local_path
            })
        else:
            # Try to clone if we have a repo URL
            repo = dep.get('repo', '')
            if repo and github_user:
                if not repo.startswith('http') and not repo.startswith('git@'):
                    repo = f'https://github.com/{github_user}/{repo}.git'

                success = clone_or_pull_repo(repo, local_path)
                if success:
                    result['available'].append({
                        'name': name,
                        'path': local_path
                    })
                else:
                    result['missing'].append(name)
                    result['errors'].append(f"Failed to clone {repo}")
                    result['success'] = False
            else:
                result['missing'].append(name)
                result['errors'].append(f"Repo not found: {local_path}")
                result['success'] = False

    return result


def get_repo_source_path(repo_path: str) -> str:
    """
    Get the source directory path for a repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Path to the source directory
    """
    return os.path.join(repo_path, 'source')


def create_default_inheritance_config(personal_repo_path: str,
                                      ai_knowledge_base_path: str) -> Dict[str, Any]:
    """
    Create a default my-projects.yaml configuration by scanning existing repos.

    Args:
        personal_repo_path: Path to the personal ai-knowledge repo
        ai_knowledge_base_path: Path containing all ai-knowledge-* repos

    Returns:
        Default configuration dictionary
    """
    config: Dict[str, Any] = {
        'version': 1,
        'description': 'Inheritance configuration for AI Knowledge compilation',
        'projects': {}
    }

    # Scan for ai-knowledge-* directories
    if os.path.exists(ai_knowledge_base_path):
        for name in os.listdir(ai_knowledge_base_path):
            if name.startswith('ai-knowledge-'):
                project_name = name.replace('ai-knowledge-', '')
                local_path = os.path.join(ai_knowledge_base_path, name)

                config['projects'][project_name] = {
                    'local_path': local_path,
                    'inherits_from': []  # User needs to configure this
                }

    return config
