"""
Content Assembler for AI Knowledge Compiler

Walks source directories, applies include/exclude patterns, merges content
from multiple sources, counts tokens, and enforces budgets.

Library API:
- find_files(directory, include, exclude) -> list[str]
- read_file(path) -> str
- assemble_content(sources, include, exclude) -> dict
- count_tokens(content, model) -> int
- apply_context_filter(content, context_config) -> dict
- merge_content(contents, order) -> str
"""

import os
import fnmatch
from pathlib import Path
from typing import Optional
import tiktoken


def find_files(directory: str, include_patterns: list = None, exclude_patterns: list = None) -> list:
    """
    Find all files matching include patterns and not matching exclude patterns.

    Args:
        directory: Root directory to search
        include_patterns: List of glob patterns to include (default: ['**/*'])
        exclude_patterns: List of glob patterns to exclude (default: [])

    Returns:
        List of absolute file paths
    """
    if include_patterns is None:
        include_patterns = ['**/*']
    if exclude_patterns is None:
        exclude_patterns = []

    directory = os.path.abspath(directory)
    matched_files = []

    for root, dirs, files in os.walk(directory):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in files:
            # Skip hidden files
            if filename.startswith('.'):
                continue

            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, directory)

            # Check if file matches any include pattern
            included = False
            for pattern in include_patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                    included = True
                    break

            if not included:
                continue

            # Check if file matches any exclude pattern
            excluded = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(filename, pattern):
                    excluded = True
                    break

            if not excluded:
                matched_files.append(file_path)

    return sorted(matched_files)


def read_file(path: str) -> str:
    """
    Read file contents as string.

    Args:
        path: Path to the file

    Returns:
        File contents as string
    """
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def count_tokens(content: str, model: str = 'cl100k_base') -> int:
    """
    Count tokens in content using tiktoken.

    Args:
        content: Text content to count
        model: Tokenizer model to use (default: cl100k_base for GPT-4/Claude)

    Returns:
        Token count
    """
    try:
        encoding = tiktoken.get_encoding(model)
    except KeyError:
        # Fallback to cl100k_base if model not found
        encoding = tiktoken.get_encoding('cl100k_base')

    return len(encoding.encode(content))


def get_file_category(file_path: str, source_dir: str) -> str:
    """
    Determine the category of a file based on its path.

    Args:
        file_path: Absolute path to the file
        source_dir: Source directory root

    Returns:
        Category string: 'instructions', 'runbooks', 'datasets', 'contexts', or 'other'
    """
    rel_path = os.path.relpath(file_path, source_dir)
    parts = Path(rel_path).parts

    if len(parts) > 0:
        first_dir = parts[0].lower()
        if first_dir in ('instructions', 'runbooks', 'datasets', 'contexts', 'project-plans'):
            return first_dir

    return 'other'


def assemble_content(source_dir: str, include_patterns: list = None,
                     exclude_patterns: list = None) -> dict:
    """
    Assemble content from a source directory.

    Args:
        source_dir: Path to the source directory
        include_patterns: Glob patterns to include
        exclude_patterns: Glob patterns to exclude

    Returns:
        Dictionary with:
        - files: list of {path, content, tokens, category}
        - by_category: dict of category -> list of file info
        - total_tokens: total token count
    """
    files = find_files(source_dir, include_patterns, exclude_patterns)

    result = {
        'files': [],
        'by_category': {
            'instructions': [],
            'runbooks': [],
            'datasets': [],
            'contexts': [],
            'project-plans': [],
            'other': []
        },
        'total_tokens': 0
    }

    for file_path in files:
        try:
            content = read_file(file_path)
            tokens = count_tokens(content)
            category = get_file_category(file_path, source_dir)

            file_info = {
                'path': file_path,
                'relative_path': os.path.relpath(file_path, source_dir),
                'content': content,
                'tokens': tokens,
                'category': category
            }

            result['files'].append(file_info)
            result['by_category'][category].append(file_info)
            result['total_tokens'] += tokens

        except (IOError, UnicodeDecodeError) as e:
            # Skip files that can't be read
            print(f"Warning: Could not read {file_path}: {e}")
            continue

    return result


def merge_content(contents: list, separator: str = '\n\n---\n\n') -> str:
    """
    Merge multiple content strings into one.

    Args:
        contents: List of content strings
        separator: Separator between content pieces

    Returns:
        Merged content string
    """
    return separator.join(c for c in contents if c.strip())


def merge_assembled_content(assembled_list: list, order: list = None) -> dict:
    """
    Merge multiple assembled content results.

    Args:
        assembled_list: List of assembled content dicts (from assemble_content)
        order: Order of categories to include (default: all)

    Returns:
        Merged assembled content dict
    """
    if order is None:
        order = ['instructions', 'runbooks', 'datasets', 'contexts', 'project-plans', 'other']

    result = {
        'files': [],
        'by_category': {cat: [] for cat in order},
        'total_tokens': 0
    }

    for assembled in assembled_list:
        for file_info in assembled.get('files', []):
            result['files'].append(file_info)
            category = file_info.get('category', 'other')
            if category in result['by_category']:
                result['by_category'][category].append(file_info)
            result['total_tokens'] += file_info.get('tokens', 0)

    return result


def apply_context_filter(assembled: dict, context_config: dict) -> dict:
    """
    Filter assembled content based on a context configuration.

    Args:
        assembled: Assembled content dict
        context_config: Context configuration with include/exclude rules

    Returns:
        Filtered assembled content dict
    """
    include_categories = context_config.get('include_categories', [])
    exclude_categories = context_config.get('exclude_categories', [])
    include_patterns = context_config.get('include_patterns', [])
    exclude_patterns = context_config.get('exclude_patterns', [])

    result = {
        'files': [],
        'by_category': {},
        'total_tokens': 0
    }

    for file_info in assembled.get('files', []):
        category = file_info.get('category', 'other')
        rel_path = file_info.get('relative_path', '')

        # Check category filters
        if include_categories and category not in include_categories:
            continue
        if category in exclude_categories:
            continue

        # Check pattern filters
        if include_patterns:
            matched = any(fnmatch.fnmatch(rel_path, p) for p in include_patterns)
            if not matched:
                continue

        if exclude_patterns:
            matched = any(fnmatch.fnmatch(rel_path, p) for p in exclude_patterns)
            if matched:
                continue

        # File passes all filters
        result['files'].append(file_info)
        result['by_category'].setdefault(category, []).append(file_info)
        result['total_tokens'] += file_info.get('tokens', 0)

    return result


def format_knowledge_file(assembled: dict, categories: list = None,
                          include_headers: bool = True) -> str:
    """
    Format assembled content into a single knowledge file.

    Args:
        assembled: Assembled content dict
        categories: Categories to include (default: runbooks, datasets)
        include_headers: Whether to include category headers

    Returns:
        Formatted content string
    """
    if categories is None:
        categories = ['runbooks', 'datasets']

    sections = []

    for category in categories:
        files = assembled.get('by_category', {}).get(category, [])
        if not files:
            continue

        if include_headers:
            header = f"# {category.title()}\n\n"
        else:
            header = ""

        content_parts = []
        for file_info in files:
            rel_path = file_info.get('relative_path', '')
            content = file_info.get('content', '')

            # Add file path as a comment/header
            file_header = f"## {rel_path}\n\n"
            content_parts.append(file_header + content)

        sections.append(header + '\n\n'.join(content_parts))

    return '\n\n---\n\n'.join(sections)


def check_token_budget(assembled: dict, budget: int) -> dict:
    """
    Check if assembled content is within token budget.

    Args:
        assembled: Assembled content dict
        budget: Token budget

    Returns:
        Dict with 'within_budget', 'total_tokens', 'budget', 'overage'
    """
    total = assembled.get('total_tokens', 0)
    return {
        'within_budget': total <= budget,
        'total_tokens': total,
        'budget': budget,
        'overage': max(0, total - budget)
    }
