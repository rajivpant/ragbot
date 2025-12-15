"""
AI Knowledge Compiler

Library for compiling AI Knowledge repositories into optimized outputs
for various LLM platforms (Claude, ChatGPT, Gemini, etc.).

This is a library-first design: all functionality is available as importable
Python modules. The CLI (ragbot compile) is a thin wrapper.

Example usage:
    from ragbot.compiler import compile_project
    from ragbot.compiler.config import load_compile_config, resolve_model

    config = load_compile_config("/path/to/ai-knowledge-my-project")
    result = compile_project(config, platforms=['anthropic'], personalized=True)

Public API:
- compile_project() - Main compilation function
- compile_all_projects() - Compile all projects in a directory
- Config functions: load_compile_config, resolve_model, validate_config
- Assembler functions: assemble_content, count_tokens
- Instruction functions: compile_instructions, format_for_platform
- Cache functions: load_cache, save_cache, is_file_changed
- Manifest functions: generate_manifest, save_manifest
- Vector functions: chunk_content, generate_chunks_for_rag
"""

import os
import time
import fnmatch
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml

# Import library modules
from .config import (
    load_compile_config,
    load_engines_config,
    resolve_model,
    validate_config,
    get_project_name,
    get_output_dir,
    get_source_path,
    get_include_patterns,
    get_exclude_patterns,
    get_token_budget,
    get_targets,
    get_default_compiler,
    get_vector_store_config
)

from .assembler import (
    find_files,
    read_file,
    assemble_content,
    count_tokens,
    merge_content,
    apply_context_filter,
    format_knowledge_file,
    check_token_budget,
    merge_assembled_content
)

from .cache import (
    compute_hash,
    compute_file_hash,
    load_cache,
    save_cache,
    is_file_changed,
    is_compilation_valid,
    update_file_cache,
    update_compilation_cache,
    get_cache_path
)

from .inheritance import (
    load_inheritance_config,
    find_inheritance_config,
    get_inheritance_chain,
    resolve_dependencies,
    ensure_repos_available,
    get_repo_source_path
)

from .instructions import (
    compile_instructions,
    format_for_platform,
    get_platform_constraints,
    passthrough_instructions,
    assemble_instructions_content
)

from .manifest import (
    generate_manifest,
    add_target_to_manifest,
    save_manifest,
    load_manifest,
    format_manifest_summary
)

from .vectors import (
    chunk_content,
    generate_chunks_for_rag,
    save_chunks,
    load_chunks
)


def load_context_definition(context_name: str, source_path: str) -> Optional[Dict]:
    """
    Load a context definition YAML file.

    Args:
        context_name: Name of the context (e.g., 'writing-mode')
        source_path: Path to the source directory

    Returns:
        Parsed context definition or None if not found
    """
    # Look for context file in source/contexts/
    contexts_dir = os.path.join(source_path, 'contexts')

    # Try with and without .yaml extension
    possible_paths = [
        os.path.join(contexts_dir, f'{context_name}.yaml'),
        os.path.join(contexts_dir, f'{context_name}.yml'),
        os.path.join(contexts_dir, context_name),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return yaml.safe_load(f)

    return None


def apply_context_to_assembled(assembled: Dict, context_def: Dict, source_path: str) -> Dict:
    """
    Apply context filtering to assembled content.

    Args:
        assembled: Assembled content dict from assemble_content()
        context_def: Context definition from load_context_definition()
        source_path: Path to source directory (for resolving relative paths)

    Returns:
        Filtered assembled content dict
    """
    include_rules = context_def.get('include', {})
    exclude_rules = context_def.get('exclude', [])

    # Build include patterns by category
    include_patterns = {}
    for category, patterns in include_rules.items():
        if isinstance(patterns, list):
            include_patterns[category] = patterns
        elif isinstance(patterns, str):
            include_patterns[category] = [patterns]

    # Convert exclude rules to patterns
    exclude_patterns = []
    if isinstance(exclude_rules, list):
        exclude_patterns = exclude_rules
    elif isinstance(exclude_rules, str):
        exclude_patterns = [exclude_rules]

    result = {
        'files': [],
        'by_category': {},
        'total_tokens': 0
    }

    for file_info in assembled.get('files', []):
        category = file_info.get('category', 'other')
        rel_path = file_info.get('relative_path', '')

        # Check if file matches any exclude pattern
        excluded = False
        for pattern in exclude_patterns:
            # Normalize pattern - handle both with and without category prefix
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f'*/{pattern}'):
                excluded = True
                break
            # Also check if the category/path matches
            full_pattern = f'{category}/{pattern}' if not pattern.startswith(category) else pattern
            if fnmatch.fnmatch(rel_path, full_pattern):
                excluded = True
                break

        if excluded:
            continue

        # Check if file matches include patterns for its category
        category_patterns = include_patterns.get(category, [])
        if category_patterns:
            # If include patterns exist for this category, file must match one
            matched = False
            for pattern in category_patterns:
                # Handle glob patterns
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f'{category}/{pattern}'):
                    matched = True
                    break
                # Also check just the filename
                filename = os.path.basename(rel_path)
                if fnmatch.fnmatch(filename, pattern):
                    matched = True
                    break

            if not matched:
                continue

        # File passes all filters
        result['files'].append(file_info)
        result['by_category'].setdefault(category, []).append(file_info)
        result['total_tokens'] += file_info.get('tokens', 0)

    return result


def assemble_inherited_content(
    project_name: str,
    inheritance_config: Dict,
    base_path: str,
    include_patterns: List[str] = None,
    exclude_patterns: List[str] = None,
    verbose: bool = False
) -> Dict:
    """
    Assemble content from a project and all its inherited parents.

    Args:
        project_name: Name of the project to assemble
        inheritance_config: Loaded my-projects.yaml
        base_path: Base path where ai-knowledge-* repos are located
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        verbose: Print verbose output

    Returns:
        Merged assembled content dict with content from all inherited repos
    """
    # Get inheritance chain (parents first, project last)
    chain = get_inheritance_chain(project_name, inheritance_config)

    if verbose:
        print(f"Inheritance chain for {project_name}: {' → '.join(chain)}")

    assembled_list = []

    for proj_name in chain:
        # Get project config from inheritance config
        proj_config = inheritance_config.get('projects', {}).get(proj_name, {})
        local_path = proj_config.get('local_path', '')

        # Expand ~ in path
        if local_path.startswith('~'):
            local_path = os.path.expanduser(local_path)

        # Fallback to convention-based path
        if not local_path or not os.path.exists(local_path):
            local_path = os.path.join(base_path, f'ai-knowledge-{proj_name}')

        if not os.path.exists(local_path):
            if verbose:
                print(f"  Warning: Repo not found for {proj_name}: {local_path}")
            continue

        source_path = os.path.join(local_path, 'source')
        if not os.path.exists(source_path):
            if verbose:
                print(f"  Warning: Source path not found: {source_path}")
            continue

        if verbose:
            print(f"  Assembling from {proj_name}: {source_path}")

        # Assemble content from this repo
        assembled = assemble_content(
            source_path,
            include_patterns or ['**/*'],
            exclude_patterns or []
        )

        # Tag each file with its source repo
        for file_info in assembled.get('files', []):
            file_info['source_repo'] = proj_name
            file_info['source_repo_path'] = local_path

        assembled_list.append(assembled)

        if verbose:
            print(f"    Found {len(assembled['files'])} files, {assembled['total_tokens']:,} tokens")

    # Merge all assembled content (earlier repos have lower priority)
    return merge_assembled_content(assembled_list)


def write_knowledge_full(assembled: Dict, output_dir: str, verbose: bool = False) -> List[str]:
    """
    Write individual knowledge files to knowledge/full/ directory.

    This creates individual files suitable for GitHub sync to Claude Projects.

    Args:
        assembled: Assembled content dict
        output_dir: Base output directory (compiled/)
        verbose: Print verbose output

    Returns:
        List of written file paths
    """
    full_dir = os.path.join(output_dir, 'knowledge', 'full')
    os.makedirs(full_dir, exist_ok=True)

    written_files = []

    # Write runbooks and datasets as individual files
    for category in ['runbooks', 'datasets']:
        files = assembled.get('by_category', {}).get(category, [])

        for file_info in files:
            rel_path = file_info.get('relative_path', '')
            content = file_info.get('content', '')

            if not content.strip():
                continue

            # Create output path preserving directory structure
            # Remove the category prefix from path for cleaner structure
            path_parts = Path(rel_path).parts
            if path_parts and path_parts[0] == category:
                clean_path = os.path.join(*path_parts[1:]) if len(path_parts) > 1 else path_parts[0]
            else:
                clean_path = rel_path

            output_path = os.path.join(full_dir, category, clean_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w') as f:
                f.write(content)

            written_files.append(output_path)

            if verbose:
                print(f"    Wrote: {output_path}")

    return written_files


def write_knowledge_by_context(
    assembled: Dict,
    output_dir: str,
    source_path: str,
    verbose: bool = False
) -> Dict[str, List[str]]:
    """
    Write context-filtered knowledge files to knowledge/by-context/ directory.

    Args:
        assembled: Assembled content dict
        output_dir: Base output directory (compiled/)
        source_path: Path to source directory (to find context definitions)
        verbose: Print verbose output

    Returns:
        Dict mapping context name to list of written file paths
    """
    contexts_dir = os.path.join(source_path, 'contexts')
    if not os.path.exists(contexts_dir):
        if verbose:
            print("  No contexts directory found, skipping context compilation")
        return {}

    written_by_context = {}

    # Find all context definition files
    for filename in os.listdir(contexts_dir):
        if not filename.endswith(('.yaml', '.yml')):
            continue

        context_name = filename.rsplit('.', 1)[0]
        context_path = os.path.join(contexts_dir, filename)

        try:
            with open(context_path, 'r') as f:
                context_def = yaml.safe_load(f)
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not load context {context_name}: {e}")
            continue

        if not context_def:
            continue

        if verbose:
            print(f"  Compiling context: {context_name}")

        # Apply context filter
        filtered = apply_context_to_assembled(assembled, context_def, source_path)

        if verbose:
            print(f"    Filtered to {len(filtered['files'])} files, {filtered['total_tokens']:,} tokens")

        # Create context output directory
        context_output_dir = os.path.join(output_dir, 'knowledge', 'by-context', context_name)
        os.makedirs(context_output_dir, exist_ok=True)

        written_files = []

        # Write consolidated knowledge file for this context
        knowledge_content = format_knowledge_file(
            filtered,
            categories=['instructions', 'runbooks', 'datasets'],
            include_headers=True
        )

        if knowledge_content.strip():
            # Use context display name if available
            display_name = context_def.get('name', context_name)
            safe_name = context_name.replace(' ', '-').lower()
            knowledge_path = os.path.join(context_output_dir, f'{safe_name}-knowledge.md')

            with open(knowledge_path, 'w') as f:
                f.write(f"# {display_name}\n\n")
                f.write(f"{context_def.get('description', '')}\n\n")
                f.write("---\n\n")
                f.write(knowledge_content)

            written_files.append(knowledge_path)

            if verbose:
                print(f"    Wrote: {knowledge_path}")

        written_by_context[context_name] = written_files

    return written_by_context


def compile_project(config: dict,
                    platforms: list = None,
                    personalized: bool = False,
                    context: str = None,
                    force: bool = False,
                    use_llm: bool = True,
                    instructions_only: bool = False,
                    verbose: bool = False,
                    personal_repo_path: str = None,
                    base_path: str = None) -> dict:
    """
    Compile an AI Knowledge project.

    This is the main compilation function. It:
    1. Assembles content from source directories
    2. Optionally merges inherited content (if personalized)
    3. Applies context filtering (if specified)
    4. Compiles instructions using each target LLM
    5. Generates knowledge files (full and by-context)
    6. Optionally generates vector store chunks
    7. Creates a manifest

    Args:
        config: Loaded compile-config.yaml (from load_compile_config)
        platforms: List of platforms to compile for (None = all)
        personalized: Whether to include inherited content
        context: Optional context filter to apply (single context)
        force: Force recompilation, ignore cache
        use_llm: Whether to use LLMs for instruction compilation
        instructions_only: Only compile instructions, skip knowledge
        verbose: Print verbose output
        personal_repo_path: Path to personal repo (for inheritance config)
        base_path: Base path where ai-knowledge-* repos are located

    Returns:
        Dictionary with:
        - manifest: Compilation manifest
        - output_dir: Path to compiled output
        - compiled_files: List of output file paths
        - errors: List of any errors encountered
        - inheritance_chain: List of repos in inheritance order (if personalized)
        - contexts_compiled: Dict of context names to file lists
    """
    start_time = time.time()

    project_name = get_project_name(config)
    repo_path = config.get('_repo_path', '.')
    source_path = get_source_path(config)

    # Determine base_path for ai-knowledge repos
    if not base_path:
        base_path = os.path.expanduser('~/projects/my-projects/ai-knowledge')

    # Determine output directory based on compilation mode
    if personalized and personal_repo_path:
        # Personalized compilation outputs to personal repo's compiled/projects/{project}/
        output_dir = os.path.join(personal_repo_path, 'compiled', 'projects', project_name)
    else:
        # Shared baseline compilation outputs to the repo's own compiled/
        output_dir = get_output_dir(config)

    result = {
        'manifest': {},
        'output_dir': output_dir,
        'compiled_files': [],
        'errors': [],
        'inheritance_chain': [],
        'contexts_compiled': {}
    }

    # Load engines config for model resolution
    try:
        engines_config = load_engines_config()
    except FileNotFoundError:
        engines_config = {'engines': []}
        result['errors'].append("Warning: engines.yaml not found, using defaults")

    # Load cache
    cache_path = get_cache_path(repo_path)
    cache = load_cache(cache_path) if not force else {'files': {}, 'compilations': {}}

    # Assemble source content
    include_patterns = get_include_patterns(config)
    exclude_patterns = get_exclude_patterns(config)

    # Handle personalized compilation (merge inherited content)
    inheritance_config = None
    if personalized:
        # Find personal repo path if not provided
        # NOTE: The actual personal repo name is configured in ~/.config/ragbot/config.yaml
        # This is a fallback that should be replaced with proper config lookup
        if not personal_repo_path:
            # Try to get user_workspace from config, fallback to convention
            from ..ragbot.keystore import get_user_config
            user_workspace = get_user_config('user_workspace', 'personal')
            personal_repo_path = os.path.join(base_path, f'ai-knowledge-{user_workspace}')

        inheritance_config_path = find_inheritance_config(personal_repo_path)
        if inheritance_config_path:
            try:
                inheritance_config = load_inheritance_config(inheritance_config_path)

                if verbose:
                    print(f"Loading inheritance config from {inheritance_config_path}")

                # Assemble content from all inherited repos
                assembled = assemble_inherited_content(
                    project_name,
                    inheritance_config,
                    base_path,
                    include_patterns,
                    exclude_patterns,
                    verbose
                )

                # Record inheritance chain
                result['inheritance_chain'] = get_inheritance_chain(project_name, inheritance_config)

            except Exception as e:
                result['errors'].append(f"Inheritance config error: {e}")
                if verbose:
                    print(f"Inheritance error: {e}, falling back to local-only")
                assembled = assemble_content(source_path, include_patterns, exclude_patterns)
        else:
            if verbose:
                print("No my-projects.yaml found, using local content only")
            assembled = assemble_content(source_path, include_patterns, exclude_patterns)
    else:
        if verbose:
            print(f"Assembling content from {source_path}")
        assembled = assemble_content(source_path, include_patterns, exclude_patterns)

    if verbose:
        print(f"Total: {len(assembled['files'])} files, {assembled['total_tokens']:,} tokens")

    # Apply single context filter if specified
    if context:
        context_def = load_context_definition(context, source_path)
        if context_def:
            if verbose:
                print(f"Applying context filter: {context}")
            assembled = apply_context_to_assembled(assembled, context_def, source_path)
            if verbose:
                print(f"After filter: {len(assembled['files'])} files, {assembled['total_tokens']:,} tokens")
        else:
            result['errors'].append(f"Context definition not found: {context}")

    # Check token budget
    budget = get_token_budget(config)
    budget_check = check_token_budget(assembled, budget)
    if not budget_check['within_budget']:
        result['errors'].append(
            f"Token budget exceeded: {assembled['total_tokens']:,} > {budget:,}"
        )

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)

    compiled_files = []
    targets = get_targets(config)

    # Filter targets by platform if specified
    if platforms:
        targets = [t for t in targets if t.get('platform') in platforms]

    # Compile instructions for each target
    instructions_files = assembled['by_category'].get('instructions', [])

    for target in targets:
        target_name = target.get('name', 'unknown')
        platform = target.get('platform', 'anthropic')
        model_category = target.get('model_category', 'flagship')

        if verbose:
            print(f"Compiling for target: {target_name} ({platform})")

        # Resolve model
        try:
            model = resolve_model(engines_config, platform, model_category)
        except ValueError:
            model = None
            result['errors'].append(f"Could not resolve model for {platform}")

        # Create target output directory
        target_output = os.path.join(output_dir, target_name)
        os.makedirs(target_output, exist_ok=True)

        # Compile instructions
        if instructions_files:
            instructions_content = assemble_instructions_content(instructions_files)

            if use_llm and model:
                try:
                    compiled = compile_instructions(
                        instructions_content, platform, model
                    )
                except Exception as e:
                    result['errors'].append(f"LLM compilation failed for {target_name}: {e}")
                    compiled = passthrough_instructions(instructions_content, platform)
            else:
                compiled = passthrough_instructions(instructions_content, platform)

            # Save compiled instructions
            instructions_dir = os.path.join(target_output, 'instructions')
            os.makedirs(instructions_dir, exist_ok=True)
            instructions_path = os.path.join(instructions_dir, f'{project_name}.md')

            with open(instructions_path, 'w') as f:
                f.write(compiled)

            compiled_files.append(instructions_path)

            if verbose:
                print(f"  Wrote instructions: {instructions_path}")

        # Compile knowledge (if not instructions-only)
        if not instructions_only:
            # Write consolidated knowledge file for this target
            knowledge_content = format_knowledge_file(
                assembled,
                categories=['runbooks', 'datasets']
            )

            if knowledge_content.strip():
                knowledge_dir = os.path.join(target_output, 'knowledge')
                os.makedirs(knowledge_dir, exist_ok=True)
                knowledge_path = os.path.join(knowledge_dir, 'knowledge.md')

                with open(knowledge_path, 'w') as f:
                    f.write(knowledge_content)

                compiled_files.append(knowledge_path)

                if verbose:
                    print(f"  Wrote knowledge: {knowledge_path}")

    # Write knowledge/full/ for GitHub sync (if not instructions-only)
    if not instructions_only:
        if verbose:
            print("Writing knowledge/full/ for GitHub sync")
        full_files = write_knowledge_full(assembled, output_dir, verbose)
        compiled_files.extend(full_files)

    # Write knowledge/by-context/ for each context (if not instructions-only)
    if not instructions_only:
        if verbose:
            print("Writing knowledge/by-context/")
        # Use the source path from the main repo (or personal repo for personalized)
        context_source = source_path
        if personalized and personal_repo_path:
            context_source = os.path.join(personal_repo_path, 'source')

        contexts_result = write_knowledge_by_context(assembled, output_dir, context_source, verbose)
        result['contexts_compiled'] = contexts_result
        for context_files in contexts_result.values():
            compiled_files.extend(context_files)

    # Generate vector store chunks (if enabled and not instructions-only)
    vector_config = get_vector_store_config(config)
    if vector_config.get('enabled') and not instructions_only:
        if verbose:
            print("Generating vector store chunks")

        chunks = generate_chunks_for_rag(assembled, vector_config)
        vector_output = os.path.join(output_dir, 'vectors')

        chunk_result = save_chunks(chunks, vector_output)
        compiled_files.append(chunk_result['jsonl_path'])

        if verbose:
            print(f"  Generated {chunk_result['total_chunks']} chunks")

    # Generate manifest
    compilation_time = time.time() - start_time
    manifest = generate_manifest(
        project_name=project_name,
        source_files=assembled['files'],
        compiled_files=compiled_files,
        config=config,
        compilation_time=compilation_time
    )

    # Add inheritance info to manifest
    if result['inheritance_chain']:
        manifest['inheritance'] = {
            'chain': result['inheritance_chain'],
            'personalized': True
        }

    # Add context info to manifest
    if result['contexts_compiled']:
        manifest['contexts'] = list(result['contexts_compiled'].keys())

    # Add target info to manifest
    for target in targets:
        target_name = target.get('name', 'unknown')
        platform = target.get('platform', 'anthropic')
        target_files = [f for f in compiled_files if target_name in f]

        add_target_to_manifest(
            manifest, target_name, platform,
            target_files, assembled['total_tokens'],
            compiled_with_llm=use_llm
        )

    # Save manifest
    manifest_path = save_manifest(manifest, output_dir)
    compiled_files.append(manifest_path)

    # Update cache
    for file_info in assembled['files']:
        update_file_cache(cache, file_info['path'])
    save_cache(cache, cache_path)

    result['manifest'] = manifest
    result['compiled_files'] = compiled_files

    return result


def compile_all_projects(base_path: str, **kwargs) -> dict:
    """
    Compile all AI Knowledge projects in a directory.

    Args:
        base_path: Path containing ai-knowledge-* repositories
        **kwargs: Arguments passed to compile_project

    Returns:
        Dictionary with results for each project
    """
    results = {}

    if not os.path.exists(base_path):
        return {'error': f"Base path does not exist: {base_path}"}

    for name in os.listdir(base_path):
        if not name.startswith('ai-knowledge-'):
            continue

        repo_path = os.path.join(base_path, name)
        config_path = os.path.join(repo_path, 'compile-config.yaml')

        if not os.path.exists(config_path):
            continue

        project_name = name.replace('ai-knowledge-', '')

        try:
            config = load_compile_config(repo_path)
            result = compile_project(config, base_path=base_path, **kwargs)
            results[project_name] = result
        except Exception as e:
            results[project_name] = {'error': str(e)}

    return results


# Version
__version__ = '0.2.0'
