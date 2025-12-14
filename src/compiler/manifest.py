"""
Manifest Generator for AI Knowledge Compiler

Generates manifest.yaml files documenting what was compiled,
token counts, and metadata.

Library API:
- generate_manifest(compiled_output, config) -> dict
- save_manifest(manifest, output_path)
- load_manifest(manifest_path) -> dict
"""

import os
import yaml
from datetime import datetime
from typing import Optional


def generate_manifest(project_name: str, source_files: list, compiled_files: list,
                      config: dict, compilation_time: float = 0) -> dict:
    """
    Generate a manifest documenting the compilation.

    Args:
        project_name: Name of the project
        source_files: List of source file info dicts
        compiled_files: List of compiled output file paths
        config: Compilation configuration
        compilation_time: Time taken to compile (seconds)

    Returns:
        Manifest dictionary
    """
    # Calculate totals
    total_source_tokens = sum(f.get('tokens', 0) for f in source_files)

    # Group source files by category
    by_category = {}
    for f in source_files:
        cat = f.get('category', 'other')
        if cat not in by_category:
            by_category[cat] = {'files': [], 'tokens': 0}
        by_category[cat]['files'].append(f.get('relative_path', ''))
        by_category[cat]['tokens'] += f.get('tokens', 0)

    manifest = {
        'version': 1,
        'generated_at': datetime.now().isoformat(),
        'compilation_time_seconds': round(compilation_time, 2),

        'project': {
            'name': project_name,
            'description': config.get('project', {}).get('description', '')
        },

        'source': {
            'total_files': len(source_files),
            'total_tokens': total_source_tokens,
            'by_category': by_category
        },

        'compiled': {
            'files': compiled_files,
            'targets': []
        },

        'configuration': {
            'token_budget': config.get('compilation', {}).get('default_token_budget', 100000),
            'targets': [t.get('name') for t in config.get('compilation', {}).get('targets', [])]
        }
    }

    return manifest


def add_target_to_manifest(manifest: dict, target_name: str, platform: str,
                           output_files: list, token_count: int,
                           compiled_with_llm: bool = True) -> dict:
    """
    Add a compilation target's info to the manifest.

    Args:
        manifest: Manifest dictionary
        target_name: Name of the target
        platform: Platform name
        output_files: List of output file paths
        token_count: Token count of compiled output
        compiled_with_llm: Whether LLM was used for compilation

    Returns:
        Updated manifest
    """
    target_info = {
        'name': target_name,
        'platform': platform,
        'output_files': output_files,
        'token_count': token_count,
        'llm_compiled': compiled_with_llm
    }

    manifest['compiled']['targets'].append(target_info)
    manifest['compiled']['files'].extend(output_files)

    return manifest


def save_manifest(manifest: dict, output_path: str) -> str:
    """
    Save manifest to a YAML file.

    Args:
        manifest: Manifest dictionary
        output_path: Directory to save manifest in

    Returns:
        Path to saved manifest file
    """
    os.makedirs(output_path, exist_ok=True)
    manifest_path = os.path.join(output_path, 'manifest.yaml')

    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    return manifest_path


def load_manifest(manifest_path: str) -> dict:
    """
    Load a manifest from disk.

    Args:
        manifest_path: Path to manifest.yaml

    Returns:
        Manifest dictionary
    """
    if not os.path.exists(manifest_path):
        return {}

    with open(manifest_path, 'r') as f:
        return yaml.safe_load(f) or {}


def format_manifest_summary(manifest: dict) -> str:
    """
    Format a human-readable summary of the manifest.

    Args:
        manifest: Manifest dictionary

    Returns:
        Formatted summary string
    """
    lines = [
        f"Compilation Summary for {manifest.get('project', {}).get('name', 'Unknown')}",
        f"Generated: {manifest.get('generated_at', 'Unknown')}",
        f"Compilation time: {manifest.get('compilation_time_seconds', 0):.2f}s",
        "",
        "Source:",
        f"  Total files: {manifest.get('source', {}).get('total_files', 0)}",
        f"  Total tokens: {manifest.get('source', {}).get('total_tokens', 0):,}",
        ""
    ]

    # Add category breakdown
    by_category = manifest.get('source', {}).get('by_category', {})
    if by_category:
        lines.append("  By category:")
        for cat, info in by_category.items():
            lines.append(f"    {cat}: {len(info.get('files', []))} files, {info.get('tokens', 0):,} tokens")
        lines.append("")

    # Add targets
    targets = manifest.get('compiled', {}).get('targets', [])
    if targets:
        lines.append("Compiled targets:")
        for target in targets:
            llm_status = "LLM-compiled" if target.get('llm_compiled') else "assembled"
            lines.append(f"  {target.get('name')}: {target.get('token_count', 0):,} tokens ({llm_status})")
        lines.append("")

    # Budget check
    budget = manifest.get('configuration', {}).get('token_budget', 0)
    total = manifest.get('source', {}).get('total_tokens', 0)
    if budget:
        status = "✓ within budget" if total <= budget else "⚠ over budget"
        lines.append(f"Token budget: {total:,} / {budget:,} ({status})")

    return '\n'.join(lines)


def compare_manifests(old_manifest: dict, new_manifest: dict) -> dict:
    """
    Compare two manifests to show what changed.

    Args:
        old_manifest: Previous manifest
        new_manifest: Current manifest

    Returns:
        Dictionary with changes
    """
    old_source = old_manifest.get('source', {})
    new_source = new_manifest.get('source', {})

    old_files = set()
    new_files = set()

    for cat_info in old_source.get('by_category', {}).values():
        old_files.update(cat_info.get('files', []))

    for cat_info in new_source.get('by_category', {}).values():
        new_files.update(cat_info.get('files', []))

    return {
        'added_files': list(new_files - old_files),
        'removed_files': list(old_files - new_files),
        'token_change': new_source.get('total_tokens', 0) - old_source.get('total_tokens', 0),
        'file_count_change': new_source.get('total_files', 0) - old_source.get('total_files', 0)
    }
