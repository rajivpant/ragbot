"""
CLI Wrapper for AI Knowledge Compiler

Thin wrapper that calls library functions. This is what `ragbot compile` invokes.

Usage:
    ragbot compile --project my-project
    ragbot compile --project my-project --personalized
    ragbot compile --project my-client --llm claude
    ragbot compile --all
    ragbot compile --dry-run
"""

import argparse
import os
import sys
import time
from pathlib import Path

from . import compile_project, compile_all_projects
from .config import load_compile_config, validate_config, get_project_name
from .manifest import format_manifest_summary


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the compile command."""
    parser = argparse.ArgumentParser(
        prog='ragbot compile',
        description='Compile AI Knowledge repositories for LLM consumption'
    )

    # Project selection
    project_group = parser.add_mutually_exclusive_group()
    project_group.add_argument(
        '--project', '-p',
        help='Project name to compile (e.g., my-project, my-client)'
    )
    project_group.add_argument(
        '--repo', '-r',
        help='Path to ai-knowledge-* repository to compile'
    )
    project_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Compile all projects'
    )

    # Compilation options
    parser.add_argument(
        '--personalized',
        action='store_true',
        help='Include inherited content from parent repos'
    )
    parser.add_argument(
        '--llm',
        choices=['claude', 'chatgpt', 'gemini', 'all'],
        default='all',
        help='Target LLM platform (default: all)'
    )
    parser.add_argument(
        '--context',
        help='Context filter to apply (e.g., writing-mode, coding-mode)'
    )
    parser.add_argument(
        '--instructions-only',
        action='store_true',
        help='Only compile instructions, skip knowledge assembly'
    )

    # Behavior options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be compiled without writing files'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force recompilation, ignore cache'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Skip LLM compilation, just assemble content'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output with token counts'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output'
    )

    # Path options
    parser.add_argument(
        '--base-path',
        default=os.path.expanduser('~/projects/my-projects/ai-knowledge'),
        help='Base path containing ai-knowledge-* repositories'
    )
    parser.add_argument(
        '--personal-repo',
        help='Path to personal ai-knowledge repo (for inheritance config)'
    )

    return parser


def find_project_repo(project_name: str, base_path: str) -> str:
    """Find the repository path for a project name."""
    repo_name = f'ai-knowledge-{project_name}'
    repo_path = os.path.join(base_path, repo_name)

    if os.path.exists(repo_path):
        return repo_path

    raise FileNotFoundError(f"Repository not found: {repo_path}")


def list_projects(base_path: str) -> list:
    """List all ai-knowledge projects in the base path."""
    projects = []

    if not os.path.exists(base_path):
        return projects

    for name in os.listdir(base_path):
        if name.startswith('ai-knowledge-'):
            project_name = name.replace('ai-knowledge-', '')
            repo_path = os.path.join(base_path, name)
            config_path = os.path.join(repo_path, 'compile-config.yaml')

            if os.path.exists(config_path):
                projects.append({
                    'name': project_name,
                    'repo_path': repo_path
                })

    return projects


def main(args=None):
    """Main entry point for the compile CLI."""
    parser = create_parser()
    args = parser.parse_args(args)

    # Determine what to compile
    if args.all:
        return compile_all_command(args)
    elif args.project:
        return compile_project_command(args, args.project)
    elif args.repo:
        return compile_repo_command(args, args.repo)
    else:
        # Default: show help or compile current directory if it's a repo
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'compile-config.yaml')):
            return compile_repo_command(args, cwd)
        else:
            parser.print_help()
            return 1


def compile_project_command(args, project_name: str) -> int:
    """Compile a specific project by name."""
    try:
        repo_path = find_project_repo(project_name, args.base_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return compile_repo_command(args, repo_path)


def compile_repo_command(args, repo_path: str) -> int:
    """Compile a repository."""
    start_time = time.time()

    if not args.quiet:
        print(f"Compiling: {repo_path}")

    # Load and validate config
    try:
        config = load_compile_config(repo_path)
        errors = validate_config(config)
        if errors:
            print("Configuration errors:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    project_name = get_project_name(config)

    if args.dry_run:
        return dry_run(args, config)

    # Map CLI llm option to platform names
    llm_map = {
        'claude': ['anthropic'],
        'chatgpt': ['openai'],
        'gemini': ['google'],
        'all': None  # All platforms
    }
    target_platforms = llm_map.get(args.llm)

    # Compile
    try:
        result = compile_project(
            config=config,
            platforms=target_platforms,
            personalized=args.personalized,
            context=args.context,
            force=args.force,
            use_llm=not args.no_llm,
            instructions_only=args.instructions_only,
            verbose=args.verbose,
            personal_repo_path=args.personal_repo
        )
    except Exception as e:
        print(f"Compilation error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    elapsed = time.time() - start_time

    # Output results
    if args.quiet:
        print(f"Compiled {project_name} in {elapsed:.2f}s")
    else:
        print(format_manifest_summary(result.get('manifest', {})))
        print(f"\nCompleted in {elapsed:.2f}s")

    return 0


def compile_all_command(args) -> int:
    """Compile all projects."""
    projects = list_projects(args.base_path)

    if not projects:
        print(f"No projects found in {args.base_path}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Found {len(projects)} projects to compile")

    failed = []
    for project in projects:
        if not args.quiet:
            print(f"\n{'='*60}")
            print(f"Compiling: {project['name']}")
            print('='*60)

        result = compile_project_command(args, project['name'])
        if result != 0:
            failed.append(project['name'])

    if failed:
        print(f"\nFailed projects: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"\nAll {len(projects)} projects compiled successfully")
    return 0


def dry_run(args, config: dict) -> int:
    """Show what would be compiled without actually compiling."""
    from .config import get_source_path, get_include_patterns, get_exclude_patterns, get_targets
    from .assembler import assemble_content, check_token_budget

    print("=== DRY RUN ===\n")

    project_name = get_project_name(config)
    print(f"Project: {project_name}")

    source_path = get_source_path(config)
    print(f"Source path: {source_path}")

    if not os.path.exists(source_path):
        print(f"Warning: Source path does not exist", file=sys.stderr)
        return 1

    # Assemble content to show what would be included
    include = get_include_patterns(config)
    exclude = get_exclude_patterns(config)

    assembled = assemble_content(source_path, include, exclude)

    print(f"\nFiles to compile: {len(assembled['files'])}")
    print(f"Total tokens: {assembled['total_tokens']:,}")

    # Show by category
    print("\nBy category:")
    for cat, files in assembled['by_category'].items():
        if files:
            tokens = sum(f['tokens'] for f in files)
            print(f"  {cat}: {len(files)} files, {tokens:,} tokens")

    # Check budget
    from .config import get_token_budget
    budget = get_token_budget(config)
    budget_check = check_token_budget(assembled, budget)
    status = "✓" if budget_check['within_budget'] else "⚠ OVER"
    print(f"\nToken budget: {assembled['total_tokens']:,} / {budget:,} {status}")

    # Show targets
    targets = get_targets(config)
    print(f"\nTargets: {', '.join(t['name'] for t in targets)}")

    if args.verbose:
        print("\n=== Files ===")
        for f in assembled['files']:
            print(f"  {f['relative_path']} ({f['tokens']:,} tokens)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
