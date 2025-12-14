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
from typing import Optional

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
    check_token_budget
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


def compile_project(config: dict,
                    platforms: list = None,
                    personalized: bool = False,
                    context: str = None,
                    force: bool = False,
                    use_llm: bool = True,
                    instructions_only: bool = False,
                    verbose: bool = False,
                    personal_repo_path: str = None) -> dict:
    """
    Compile an AI Knowledge project.

    This is the main compilation function. It:
    1. Assembles content from source directories
    2. Optionally merges inherited content (if personalized)
    3. Compiles instructions using each target LLM
    4. Generates knowledge files
    5. Optionally generates vector store chunks
    6. Creates a manifest

    Args:
        config: Loaded compile-config.yaml (from load_compile_config)
        platforms: List of platforms to compile for (None = all)
        personalized: Whether to include inherited content
        context: Optional context filter to apply
        force: Force recompilation, ignore cache
        use_llm: Whether to use LLMs for instruction compilation
        instructions_only: Only compile instructions, skip knowledge
        verbose: Print verbose output
        personal_repo_path: Path to personal repo (for inheritance config)

    Returns:
        Dictionary with:
        - manifest: Compilation manifest
        - output_dir: Path to compiled output
        - compiled_files: List of output file paths
        - errors: List of any errors encountered
    """
    start_time = time.time()

    project_name = get_project_name(config)
    repo_path = config.get('_repo_path', '.')
    output_dir = get_output_dir(config)
    source_path = get_source_path(config)

    result = {
        'manifest': {},
        'output_dir': output_dir,
        'compiled_files': [],
        'errors': []
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
    if verbose:
        print(f"Assembling content from {source_path}")

    include_patterns = get_include_patterns(config)
    exclude_patterns = get_exclude_patterns(config)
    assembled = assemble_content(source_path, include_patterns, exclude_patterns)

    if verbose:
        print(f"Found {len(assembled['files'])} files, {assembled['total_tokens']:,} tokens")

    # Handle personalized compilation (merge inherited content)
    if personalized and personal_repo_path:
        inheritance_config_path = find_inheritance_config(personal_repo_path)
        if inheritance_config_path:
            try:
                inheritance_config = load_inheritance_config(inheritance_config_path)
                # TODO: Implement full inheritance merging
                # For now, just note that it's enabled
                if verbose:
                    print("Personalized compilation enabled (inheritance merging)")
            except Exception as e:
                result['errors'].append(f"Inheritance config error: {e}")

    # Apply context filter if specified
    if context:
        # TODO: Load context definition and apply filter
        if verbose:
            print(f"Context filter: {context}")

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
            result = compile_project(config, **kwargs)
            results[project_name] = result
        except Exception as e:
            results[project_name] = {'error': str(e)}

    return results


# Version
__version__ = '0.1.0'
