"""
Cache Manager for AI Knowledge Compiler

Manages compilation caching using content hashes to avoid recompiling
unchanged content.

Library API:
- compute_hash(content) -> str
- compute_file_hash(path) -> str
- load_cache(path) -> dict
- save_cache(cache, path)
- is_changed(file_path, cache) -> bool
- update_cache_entry(cache, file_path, hash) -> dict
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime


def compute_hash(content: str) -> str:
    """
    Compute SHA256 hash of content.

    Args:
        content: String content to hash

    Returns:
        Hex digest of the hash
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def compute_file_hash(path: str) -> str:
    """
    Compute SHA256 hash of a file's contents.

    Args:
        path: Path to the file

    Returns:
        Hex digest of the hash
    """
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_directory_hash(directory: str, include_patterns: list = None, exclude_patterns: list = None) -> str:
    """
    Compute a combined hash of all files in a directory.

    Args:
        directory: Path to the directory
        include_patterns: Glob patterns to include
        exclude_patterns: Glob patterns to exclude

    Returns:
        Combined hash of all matching files
    """
    from .assembler import find_files  # Import here to avoid circular import

    files = find_files(directory, include_patterns or ['**/*'], exclude_patterns or [])
    files.sort()  # Ensure consistent ordering

    combined = hashlib.sha256()
    for file_path in files:
        # Include both the path and content in the hash
        combined.update(file_path.encode('utf-8'))
        combined.update(compute_file_hash(file_path).encode('utf-8'))

    return combined.hexdigest()


def get_cache_path(repo_path: str) -> str:
    """
    Get the path to the cache file for a repository.

    Args:
        repo_path: Path to the ai-knowledge-* repository

    Returns:
        Path to .compile-cache.json
    """
    return os.path.join(repo_path, '.compile-cache.json')


def load_cache(cache_path: str) -> dict:
    """
    Load cache from disk.

    Args:
        cache_path: Path to the cache file

    Returns:
        Cache dictionary, or empty dict if cache doesn't exist
    """
    if not os.path.exists(cache_path):
        return {
            'version': 1,
            'created': datetime.now().isoformat(),
            'files': {},
            'compilations': {}
        }

    try:
        with open(cache_path, 'r') as f:
            cache = json.load(f)
            # Ensure required keys exist
            cache.setdefault('version', 1)
            cache.setdefault('files', {})
            cache.setdefault('compilations', {})
            return cache
    except (json.JSONDecodeError, IOError):
        return {
            'version': 1,
            'created': datetime.now().isoformat(),
            'files': {},
            'compilations': {}
        }


def save_cache(cache: dict, cache_path: str) -> None:
    """
    Save cache to disk.

    Args:
        cache: Cache dictionary
        cache_path: Path to save the cache
    """
    cache['last_updated'] = datetime.now().isoformat()
    with open(cache_path, 'w') as f:
        json.dump(cache, f, indent=2)


def is_file_changed(file_path: str, cache: dict) -> bool:
    """
    Check if a file has changed since last cached.

    Args:
        file_path: Path to the file
        cache: Cache dictionary

    Returns:
        True if file has changed or is not in cache
    """
    if not os.path.exists(file_path):
        return True

    files_cache = cache.get('files', {})
    cached_entry = files_cache.get(file_path)

    if not cached_entry:
        return True

    current_hash = compute_file_hash(file_path)
    return current_hash != cached_entry.get('hash')


def is_compilation_valid(target_name: str, source_hash: str, cache: dict) -> bool:
    """
    Check if a compilation is still valid (source hasn't changed).

    Args:
        target_name: Name of the compilation target
        source_hash: Current hash of source content
        cache: Cache dictionary

    Returns:
        True if cached compilation is still valid
    """
    compilations = cache.get('compilations', {})
    cached = compilations.get(target_name)

    if not cached:
        return False

    return cached.get('source_hash') == source_hash


def update_file_cache(cache: dict, file_path: str, file_hash: Optional[str] = None) -> dict:
    """
    Update cache entry for a file.

    Args:
        cache: Cache dictionary
        file_path: Path to the file
        file_hash: Hash of the file (computed if not provided)

    Returns:
        Updated cache dictionary
    """
    if file_hash is None:
        file_hash = compute_file_hash(file_path)

    cache.setdefault('files', {})
    cache['files'][file_path] = {
        'hash': file_hash,
        'cached_at': datetime.now().isoformat()
    }
    return cache


def update_compilation_cache(cache: dict, target_name: str, source_hash: str,
                             output_files: list, token_count: int = 0) -> dict:
    """
    Update cache entry for a compilation.

    Args:
        cache: Cache dictionary
        target_name: Name of the compilation target
        source_hash: Hash of the source content
        output_files: List of output file paths
        token_count: Token count of compiled output

    Returns:
        Updated cache dictionary
    """
    cache.setdefault('compilations', {})
    cache['compilations'][target_name] = {
        'source_hash': source_hash,
        'output_files': output_files,
        'token_count': token_count,
        'compiled_at': datetime.now().isoformat()
    }
    return cache


def clear_cache(cache_path: str) -> None:
    """
    Clear the cache file.

    Args:
        cache_path: Path to the cache file
    """
    if os.path.exists(cache_path):
        os.remove(cache_path)


def get_cache_stats(cache: dict) -> dict:
    """
    Get statistics about the cache.

    Args:
        cache: Cache dictionary

    Returns:
        Dictionary with cache statistics
    """
    files = cache.get('files', {})
    compilations = cache.get('compilations', {})

    return {
        'cached_files': len(files),
        'cached_compilations': len(compilations),
        'created': cache.get('created'),
        'last_updated': cache.get('last_updated')
    }
