#!/usr/bin/env python3
# ragbot.py - https://github.com/rajivpant/ragbot

import os
import sys
import argparse
import re
import json
import appdirs
import openai
import anthropic
import litellm
from helpers import load_files, load_config, print_saved_files, chat, load_workspaces_as_profiles
from ragbot.keystore import get_api_key

appname = "ragbot"
appauthor = "Rajiv Pant"

data_dir = appdirs.user_data_dir(appname, appauthor)
sessions_data_dir = os.path.join(data_dir, "sessions")

# Load configuration from engines.yaml
config = load_config('engines.yaml')
engines_config = {engine['name']: engine for engine in config['engines']}
engine_choices = list(engines_config.keys())
default_models = {engine: engines_config[engine]['default_model'] for engine in engine_choices}

model_cost_map = litellm.model_cost


def create_chat_parser(subparsers):
    """Create the chat subcommand parser."""
    chat_parser = subparsers.add_parser(
        'chat',
        help='Chat with an AI assistant (default command)',
        description='Chat with an AI assistant using various models and configurations.'
    )

    input_group = chat_parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "-ls", "--list-saved",
        action="store_true",
        help="List all the currently saved JSON files."
    )

    input_group2 = chat_parser.add_mutually_exclusive_group()
    input_group2.add_argument(
        "-p", "--prompt",
        help="The user's input to generate a response for."
    )
    input_group2.add_argument(
        "-f", "--prompt_file",
        help="The file containing the user's input to generate a response for."
    )
    input_group2.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enable interactive assistant chatbot mode."
    )
    input_group2.add_argument(
        "--stdin",
        action="store_true",
        help="Read the user's input from stdin."
    )

    chat_parser.add_argument(
        "-profile", "--profile",
        help="Name of the profile to use."
    )
    chat_parser.add_argument(
        "-c", "--custom_instructions",
        nargs='*', default=[],
        help="Path to the prompt custom instructions file or folder. Can accept multiple values."
    )
    chat_parser.add_argument(
        "-nc", "--nocustom_instructions",
        action="store_true",
        help="Ignore all prompt custom instructions even if they are specified."
    )
    chat_parser.add_argument(
        "-d", "--curated_dataset",
        nargs='*', default=[],
        help="Path to the prompt context curated dataset file or folder. Can accept multiple values."
    )
    chat_parser.add_argument(
        "-nd", "--nocurated_dataset",
        action="store_true",
        help="Ignore all prompt context curated dataset even if they are specified."
    )
    chat_parser.add_argument(
        "-e", "--engine",
        default=config.get('default', 'openai'),
        choices=engine_choices,
        help="The engine to use for the chat."
    )
    chat_parser.add_argument(
        "-m", "--model",
        help="The model to use for the chat. Defaults to engine's default model. Use 'flagship' to select the engine's most powerful model."
    )
    chat_parser.add_argument(
        "-t", "--temperature",
        type=float, default=None,
        help="The creativity of the response, with higher values being more creative."
    )
    chat_parser.add_argument(
        "-mt", "--max_tokens",
        type=int, default=None,
        help="The maximum number of tokens to generate in the response."
    )
    chat_parser.add_argument(
        "-l", "--load",
        help="Load a previous interactive session from a file."
    )

    chat_parser.set_defaults(func=run_chat)
    return chat_parser


def create_compile_parser(subparsers):
    """Create the compile subcommand parser."""
    compile_parser = subparsers.add_parser(
        'compile',
        help='Compile AI Knowledge repositories for LLM consumption',
        description='Compile AI Knowledge repositories into optimized outputs for various LLM platforms.'
    )

    # Project selection - what to compile
    project_group = compile_parser.add_mutually_exclusive_group()
    project_group.add_argument(
        '--project', '-p',
        help='Project name to compile (e.g., company, client)'
    )
    project_group.add_argument(
        '--repo', '-r',
        help='Path to ai-knowledge-* repository to compile (baseline only)'
    )
    project_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Compile all projects (baseline only, no inheritance)'
    )
    project_group.add_argument(
        '--all-with-inheritance',
        action='store_true',
        help='Compile ALL projects with inheritance into your private repo. '
             'Output goes to ai-knowledge-{user}/compiled/{project}/ for each project.'
    )

    # Output destination - where to put compiled output
    compile_parser.add_argument(
        '--output-repo', '-o',
        help='Path to repo where compiled output should go. Required with --project when using --with-inheritance. '
             'Example: --project {client} --with-inheritance --output-repo ~/ai-knowledge-{person}'
    )

    # Compilation options
    compile_parser.add_argument(
        '--with-inheritance',
        action='store_true',
        help='Include inherited content from parent repos (per my-projects.yaml)'
    )
    compile_parser.add_argument(
        '--llm',
        choices=['claude', 'chatgpt', 'gemini', 'all'],
        default='all',
        help='Target LLM platform (default: all)'
    )
    compile_parser.add_argument(
        '--context',
        help='Context filter to apply (e.g., writing-mode, coding-mode)'
    )
    compile_parser.add_argument(
        '--instructions-only',
        action='store_true',
        help='Only compile instructions, skip knowledge assembly'
    )

    # Behavior options
    compile_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be compiled without writing files'
    )
    compile_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force recompilation, ignore cache'
    )
    compile_parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Skip LLM compilation, just assemble content'
    )
    compile_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output with token counts'
    )
    compile_parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output'
    )

    # Path options
    compile_parser.add_argument(
        '--base-path',
        default=os.path.expanduser('~/projects/my-projects/ai-knowledge'),
        help='Base path containing ai-knowledge-* repositories'
    )
    compile_parser.add_argument(
        '--personal-repo',
        help='Path to personal ai-knowledge repo (for inheritance config)'
    )

    compile_parser.set_defaults(func=run_compile)
    return compile_parser


def run_chat(args):
    """Run the chat command."""
    if args.list_saved:
        print_saved_files(data_dir)
        return

    new_session = False

    if args.load:
        args.interactive = True
        args.nocurated_dataset = True
    else:
        new_session = True

    curated_datasets = []
    curated_dataset_files = []

    # Load workspaces from ragbot-data directory
    data_root = os.getenv('RAGBOT_DATA_ROOT')

    if data_root is None:
        if os.path.isdir('/app/workspaces'):
            data_root = '/app'
        elif os.path.isdir('workspaces'):
            data_root = '.'
        elif os.path.isdir('../ragbot-data/workspaces'):
            data_root = '../ragbot-data'
        else:
            data_root = '.'

    profiles = load_workspaces_as_profiles(data_root)

    if args.profile:
        selected_profile_data = next((profile for profile in profiles if profile['name'] == args.profile), None)
        if not selected_profile_data:
            available_workspaces = [p['name'] for p in profiles]
            print(f"Error: Workspace '{args.profile}' not found.")
            print(f"Available workspaces: {', '.join(available_workspaces)}")
            sys.exit(1)
        custom_instruction_paths = selected_profile_data.get('instructions', [])
        curated_dataset_paths = selected_profile_data.get('datasets', [])
    else:
        custom_instruction_paths = []
        curated_dataset_paths = []

    if not args.custom_instructions:
        default_custom_instructions_paths = custom_instruction_paths
        default_custom_instructions_paths = [path for path in default_custom_instructions_paths if path.strip() != '']
        custom_instructions, custom_instructions_files = load_files(file_paths=default_custom_instructions_paths + args.curated_dataset, file_type="custom_instructions")

    if custom_instructions_files:
        print("Custom instructions being used:")
        for file in custom_instructions_files:
            print(f" - {file}")
    else:
        print("No custom instructions files are being used.")

    if not args.nocurated_dataset:
        default_curated_dataset_paths = curated_dataset_paths
        default_curated_dataset_paths = [path for path in default_curated_dataset_paths if path.strip() != '']
        curated_datasets, curated_dataset_files = load_files(file_paths=default_curated_dataset_paths + args.curated_dataset, file_type="curated_datasets")

    if curated_dataset_files:
        print("Curated datasets being used:")
        for file in curated_dataset_files:
            print(f" - {file}")
    else:
        print("No curated_dataset files are being used.")

    history = []

    if args.load:
        filename = args.load.strip()
        full_path = os.path.join(sessions_data_dir, filename)
        with open(full_path, 'r') as f:
            history = json.load(f)
        print(f"Continuing previously saved session from file: {filename}")

    model = args.model
    if model is None:
        model = default_models[args.engine]
    elif model == "flagship":
        flagship_model = next(
            (m for m in engines_config[args.engine]['models'] if m.get('is_flagship')),
            None
        )
        if flagship_model:
            model = flagship_model['name']
        else:
            print(f"Warning: No flagship model defined for engine '{args.engine}'. Using default.")
            model = default_models[args.engine]

    api_key = get_api_key(args.engine)
    if api_key:
        engines_config[args.engine]['api_key'] = api_key

        if args.engine == 'openai':
            openai.api_key = api_key
        elif args.engine == 'anthropic':
            anthropic.api_key = api_key
        elif args.engine == 'google':
            os.environ['GEMINI_API_KEY'] = api_key

    selected_model = next((item for item in engines_config[args.engine]['models'] if item['name'] == model), None)

    if model in model_cost_map:
        model_data = model_cost_map[model]
    else:
        model_data = {}

    if selected_model:
        default_temperature = selected_model.get("temperature", 0.75)
        max_output_tokens = selected_model.get("max_output_tokens") or model_data.get("max_output_tokens") or selected_model.get("default_max_tokens") or 4096
        default_max_tokens = selected_model.get("default_max_tokens", min(max_output_tokens, 4096))
        max_input_tokens = selected_model.get("max_input_tokens") or model_data.get("max_input_tokens") or 128000
    else:
        default_temperature = 0.75
        max_output_tokens = 4096
        default_max_tokens = 4096
        max_input_tokens = 128000

    max_tokens = args.max_tokens or default_max_tokens
    temperature = args.temperature or default_temperature

    if max_tokens > max_output_tokens:
        print(f"Warning: Requested max_tokens ({max_tokens}) exceeds model's maximum output limit ({max_output_tokens})")
        print(f"Setting max_tokens to {max_output_tokens}")
        max_tokens = max_output_tokens

    supports_system_role = selected_model.get('supports_system_role', True)

    print(f"Using AI engine {args.engine} with model {model}")
    print(f"Creativity temperature setting: {temperature}")
    print(f"Max tokens setting: {max_tokens} (model max output: {max_output_tokens})")

    if args.interactive:
        print("Entering interactive mode. Conversation history is maintained between turns.")
        while True:
            prompt = input("\nEnter prompt below. /quit to exit or /save file_name.json to save conversation.\n> ")
            if prompt.lower() == "/quit":
                break
            elif prompt.lower().startswith("/save "):
                filename = prompt[6:].strip()
                full_path = os.path.join(sessions_data_dir, filename)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    json.dump(history, f)
                print(f"Conversation saved to {full_path}")
                continue
            history.append({"role": "user", "content": prompt})
            print("Ragbot.AI: ", end='', flush=True)
            reply = chat(
                prompt=prompt,
                custom_instructions=custom_instructions,
                curated_datasets=curated_datasets,
                history=history,
                engine=args.engine,
                model=model,
                max_tokens=max_tokens,
                max_input_tokens=max_input_tokens,
                temperature=temperature,
                interactive=args.interactive,
                new_session=new_session,
                supports_system_role=supports_system_role
            )
            history.append({"role": "assistant", "content": reply})
    else:
        prompt = None
        if args.prompt:
            prompt = args.prompt
        elif args.prompt_file:
            with open(args.prompt_file, 'r') as f:
                prompt = f.read().strip()
        elif args.stdin:
            stdin = sys.stdin.readlines()
            if stdin:
                prompt = "".join(stdin).strip()

        if prompt is None:
            print("Error: No prompt provided. Please provide a prompt using -p, -f, or -i option.")
            sys.exit(1)

        history.append({"role": "user", "content": prompt})
        reply = chat(
            prompt=prompt,
            custom_instructions=custom_instructions,
            curated_datasets=curated_datasets,
            history=history,
            engine=args.engine,
            model=model,
            max_tokens=max_tokens,
            max_input_tokens=max_input_tokens,
            temperature=temperature,
            interactive=args.interactive,
            new_session=new_session,
            supports_system_role=supports_system_role
        )
        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()
        print(reply)


def run_compile(args):
    """Run the compile command."""
    import time
    from compiler.config import load_compile_config, validate_config, get_project_name
    from compiler import compile_project, compile_all_with_inheritance
    from compiler.manifest import format_manifest_summary
    from ragbot.keystore import get_user_config

    def get_personal_repo_path(base_path):
        """Get the path to the user's personal ai-knowledge repo."""
        user_workspace = get_user_config('user_workspace', 'rajiv')
        return os.path.join(base_path, f'ai-knowledge-{user_workspace}')

    def find_project_repo(project_name, base_path):
        """Find the repository path for a project name."""
        repo_name = f'ai-knowledge-{project_name}'
        repo_path = os.path.join(base_path, repo_name)
        if os.path.exists(repo_path):
            return repo_path
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    def list_projects(base_path):
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
                    projects.append({'name': project_name, 'repo_path': repo_path})
        return projects

    def compile_repo(repo_path):
        """Compile a single repository."""
        start_time = time.time()

        if not args.quiet:
            print(f"Compiling: {repo_path}")

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
            return dry_run(config)

        llm_map = {
            'claude': ['anthropic'],
            'chatgpt': ['openai'],
            'gemini': ['google'],
            'all': None
        }
        target_platforms = llm_map.get(args.llm)

        # Determine output repo path
        output_repo = None
        with_inheritance = getattr(args, 'with_inheritance', False)
        if hasattr(args, 'output_repo') and args.output_repo:
            output_repo = os.path.expanduser(args.output_repo)
        elif with_inheritance:
            # Inheritance compilations MUST go to user's private repo
            output_repo = get_personal_repo_path(args.base_path)

        try:
            result = compile_project(
                config=config,
                platforms=target_platforms,
                personalized=with_inheritance,  # Internal param still called personalized
                context=args.context,
                force=args.force,
                use_llm=not args.no_llm,
                instructions_only=args.instructions_only,
                verbose=args.verbose,
                personal_repo_path=args.personal_repo,
                base_path=args.base_path,
                output_repo_path=output_repo
            )
        except Exception as e:
            print(f"Compilation error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

        elapsed = time.time() - start_time

        if args.quiet:
            print(f"Compiled {project_name} in {elapsed:.2f}s")
        else:
            print(format_manifest_summary(result.get('manifest', {})))
            print(f"\nCompleted in {elapsed:.2f}s")

        return 0

    def dry_run(config):
        """Show what would be compiled without actually compiling."""
        from compiler.config import get_source_path, get_include_patterns, get_exclude_patterns, get_targets, get_token_budget
        from compiler.assembler import assemble_content, check_token_budget

        print("=== DRY RUN ===\n")

        project_name = get_project_name(config)
        print(f"Project: {project_name}")

        source_path = get_source_path(config)
        print(f"Source path: {source_path}")

        if not os.path.exists(source_path):
            print(f"Warning: Source path does not exist", file=sys.stderr)
            return 1

        include = get_include_patterns(config)
        exclude = get_exclude_patterns(config)

        assembled = assemble_content(source_path, include, exclude)

        print(f"\nFiles to compile: {len(assembled['files'])}")
        print(f"Total tokens: {assembled['total_tokens']:,}")

        print("\nBy category:")
        for cat, files in assembled['by_category'].items():
            if files:
                tokens = sum(f['tokens'] for f in files)
                print(f"  {cat}: {len(files)} files, {tokens:,} tokens")

        budget = get_token_budget(config)
        budget_check = check_token_budget(assembled, budget)
        status = "✓" if budget_check['within_budget'] else "⚠ OVER"
        print(f"\nToken budget: {assembled['total_tokens']:,} / {budget:,} {status}")

        targets = get_targets(config)
        print(f"\nTargets: {', '.join(t['name'] for t in targets)}")

        if args.verbose:
            print("\n=== Files ===")
            for f in assembled['files']:
                print(f"  {f['relative_path']} ({f['tokens']:,} tokens)")

        return 0

    # Determine what to compile
    if hasattr(args, 'all_with_inheritance') and args.all_with_inheritance:
        # ==================================================================
        # --all-with-inheritance: Compile ALL projects with inheritance
        # into the personal repo. This is the SAFE and RECOMMENDED way
        # to compile everything for personal use.
        #
        # See: projects/active/ai-knowledge-architecture/architecture.md
        # ==================================================================
        personal_repo = get_personal_repo_path(args.base_path)

        if not os.path.exists(personal_repo):
            print(f"Error: Personal repo not found: {personal_repo}", file=sys.stderr)
            return 1

        if not args.quiet:
            print("=" * 70)
            print("COMPILING ALL PROJECTS WITH INHERITANCE")
            print("=" * 70)
            print(f"Output repo: {personal_repo}")
            print(f"All output will go to: {personal_repo}/compiled/")
            print("=" * 70)

        llm_map = {
            'claude': ['anthropic'],
            'chatgpt': ['openai'],
            'gemini': ['google'],
            'all': None
        }
        target_platforms = llm_map.get(args.llm)

        result = compile_all_with_inheritance(
            output_repo_path=personal_repo,
            base_path=args.base_path,
            verbose=args.verbose,
            platforms=target_platforms,
            force=args.force,
            use_llm=not args.no_llm,
            instructions_only=args.instructions_only,
            context=args.context
        )

        # Report results
        if result['errors']:
            print("\nErrors:", file=sys.stderr)
            for error in result['errors']:
                print(f"  - {error}", file=sys.stderr)

        print(f"\n{'='*70}")
        print(f"COMPILATION COMPLETE")
        print(f"{'='*70}")
        print(f"Projects compiled: {result['total_compiled']}")
        print(f"Output location: {personal_repo}/compiled/")

        # List compiled projects
        print("\nCompiled projects:")
        for name, proj_result in result['projects'].items():
            if 'error' in proj_result:
                print(f"  ✗ {name}: {proj_result['error']}")
            else:
                chain = proj_result.get('inheritance_chain', [])
                chain_str = ' → '.join(chain) if chain else 'baseline'
                print(f"  ✓ {name} ({chain_str})")

        return 1 if result['errors'] else 0

    elif args.all:
        # ==================================================================
        # --all: Compile all projects with BASELINE only (no inheritance)
        # Each repo gets its own compiled/ folder with only its own content.
        # ==================================================================
        projects = list_projects(args.base_path)
        if not projects:
            print(f"No projects found in {args.base_path}", file=sys.stderr)
            return 1

        if not args.quiet:
            print(f"Found {len(projects)} projects to compile (baseline only)")

        failed = []
        for project in projects:
            if not args.quiet:
                print(f"\n{'='*60}")
                print(f"Compiling: {project['name']} (baseline)")
                print('='*60)

            result = compile_repo(project['repo_path'])
            if result != 0:
                failed.append(project['name'])

        if failed:
            print(f"\nFailed projects: {', '.join(failed)}", file=sys.stderr)
            return 1

        print(f"\nAll {len(projects)} projects compiled successfully (baseline only)")
        return 0

    elif args.project:
        try:
            repo_path = find_project_repo(args.project, args.base_path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return compile_repo(repo_path)

    elif args.repo:
        return compile_repo(args.repo)

    else:
        # Default: compile current directory if it's a repo
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'compile-config.yaml')):
            return compile_repo(cwd)
        else:
            print("Error: No project specified. Use --project, --repo, or --all.")
            print("       Or run from an ai-knowledge-* directory with compile-config.yaml")
            return 1


def main():
    parser = argparse.ArgumentParser(
        prog='ragbot',
        description="Ragbot.AI - An augmented brain and AI assistant. Learn more at https://ragbot.ai"
    )

    subparsers = parser.add_subparsers(
        title='commands',
        description='Available commands',
        dest='command'
    )

    # Create subcommand parsers
    create_chat_parser(subparsers)
    create_compile_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, default to chat behavior for backward compatibility
    if args.command is None:
        # Re-parse with 'chat' as the default command
        # This maintains backward compatibility with existing usage like:
        #   ragbot -p "prompt"
        #   ragbot -i
        sys.argv.insert(1, 'chat')
        args = parser.parse_args()

    # Run the appropriate command
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
