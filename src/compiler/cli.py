"""
CLI Wrapper for AI Knowledge Compiler (Instructions Only)

Thin wrapper that calls library functions. This is what `ragbot compile` invokes.
Knowledge concatenation is handled by CI/CD (GitHub Actions).
RAG indexing is handled by `ragbot index`.

Usage:
    ragbot compile --project my-project
    ragbot compile --project my-project --no-llm
    ragbot compile --project my-client --llm claude
"""

import argparse
import os
import sys
import time
from pathlib import Path

from . import compile_project
from .config import load_compile_config, validate_config, get_project_name
from .manifest import format_manifest_summary


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the compile command."""
    parser = argparse.ArgumentParser(
        prog='ragbot compile',
        description='Compile AI Knowledge instructions for LLM consumption. '
                    'Knowledge concatenation is handled by CI/CD. '
                    'RAG indexing is handled by `ragbot index`.'
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

    # Behavior options
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
        default=os.environ.get('RAGBOT_BASE_PATH', os.path.expanduser('~/ai-knowledge')),
        help='Base path containing ai-knowledge-* repositories (default: $RAGBOT_BASE_PATH or ~/ai-knowledge)'
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


def main(args=None):
    """Main entry point for the compile CLI."""
    parser = create_parser()
    args = parser.parse_args(args)

    # Determine what to compile
    if args.project:
        return compile_project_command(args, args.project)
    elif args.repo:
        return compile_repo_command(args, args.repo)
    else:
        # Default: compile current directory if it's a repo
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'compile-config.yaml')):
            return compile_repo_command(args, cwd)
        else:
            parser.print_help()
            return 1


def compile_project_command(args, project_name: str) -> int:
    """Compile instructions for a specific project by name."""
    try:
        repo_path = find_project_repo(project_name, args.base_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return compile_repo_command(args, repo_path)


def compile_repo_command(args, repo_path: str) -> int:
    """Compile instructions for a repository."""
    start_time = time.time()

    if not args.quiet:
        print(f"Compiling instructions: {repo_path}")

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

    # Map CLI llm option to platform names
    llm_map = {
        'claude': ['anthropic'],
        'chatgpt': ['openai'],
        'gemini': ['google'],
        'all': None  # All platforms
    }
    target_platforms = llm_map.get(args.llm)

    # Compile instructions only
    try:
        result = compile_project(
            config=config,
            platforms=target_platforms,
            personalized=args.personalized,
            force=args.force,
            use_llm=not args.no_llm,
            instructions_only=True,  # Always instructions-only
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


if __name__ == '__main__':
    sys.exit(main())
