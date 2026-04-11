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
from ragbot.workspaces import get_llm_specific_instruction_path, ENGINE_TO_INSTRUCTION_FILE

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
        "--rag",
        action="store_true",
        default=True,
        help="Enable RAG (Retrieval-Augmented Generation) for knowledge retrieval. Default: enabled."
    )
    chat_parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG - use instructions only, no knowledge retrieval."
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
    """Create the compile subcommand parser.

    Compiles instructions for AI Knowledge repositories. Knowledge concatenation
    is handled by CI/CD (GitHub Actions), not this CLI. RAG indexing is handled
    by the 'index' subcommand.
    """
    compile_parser = subparsers.add_parser(
        'compile',
        help='Compile instructions for AI Knowledge repositories',
        description='Compile instructions from AI Knowledge repositories for various LLM platforms. '
                    'Knowledge concatenation is handled by CI/CD (GitHub Actions). '
                    'For RAG indexing, use "ragbot index".'
    )

    # Project selection - what to compile
    project_group = compile_parser.add_mutually_exclusive_group()
    project_group.add_argument(
        '--project', '-p',
        help='Project name to compile (e.g., company, client)'
    )
    project_group.add_argument(
        '--repo', '-r',
        help='Path to ai-knowledge-* repository to compile'
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

    # Behavior options
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
        default=os.environ.get('RAGBOT_BASE_PATH', os.path.expanduser('~/ai-knowledge')),
        help='Base path containing ai-knowledge-* repositories (default: $RAGBOT_BASE_PATH or ~/ai-knowledge)'
    )
    compile_parser.add_argument(
        '--personal-repo',
        help='Path to personal ai-knowledge repo (for inheritance config)'
    )

    compile_parser.set_defaults(func=run_compile)
    return compile_parser


def create_index_parser(subparsers):
    """Create the index subcommand parser.

    Indexes AI Knowledge content into a vector store (Qdrant) for RAG retrieval.
    Reads source files directly — no intermediate compiled files needed.
    """
    index_parser = subparsers.add_parser(
        'index',
        help='Index AI Knowledge content into vector store for RAG',
        description='Index AI Knowledge content into a vector store (Qdrant) for RAG retrieval. '
                    'Reads source files directly from ai-knowledge repositories.'
    )

    index_parser.add_argument(
        '--workspace', '-w',
        required=True,
        help='Workspace name to index (e.g., ragbot, rajiv, mcclatchy)'
    )
    index_parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Clear existing index and rebuild from scratch'
    )
    index_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    index_parser.set_defaults(func=run_index)
    return index_parser


def run_chat(args):
    """Run the chat command."""
    if args.list_saved:
        print_saved_files(data_dir)
        return

    new_session = True if not args.load else False

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

    workspace_name = None
    workspace_dir_name = None

    if args.profile:
        selected_profile_data = next((profile for profile in profiles if profile['name'] == args.profile or profile.get('dir_name') == args.profile), None)
        if not selected_profile_data:
            available_workspaces = [p['name'] for p in profiles if p['name'] != '(none - no workspace)']
            print(f"Error: Workspace '{args.profile}' not found.")
            print(f"Available workspaces: {', '.join(available_workspaces)}")
            sys.exit(1)
        workspace_name = args.profile
        workspace_dir_name = selected_profile_data.get('dir_name', args.profile)

    # Handle custom instructions
    # If user provides explicit -c paths, load them manually
    # Otherwise, let core.py auto-load LLM-specific instructions based on model
    custom_instructions = ""
    auto_load_instructions = True  # Let core.py handle it

    if not args.nocustom_instructions:
        if args.custom_instructions:
            # User provided explicit instruction paths - use them instead of auto-loading
            custom_instruction_paths = [p for p in args.custom_instructions if p.strip() != '']
            if custom_instruction_paths:
                custom_instructions, custom_instructions_files = load_files(
                    file_paths=custom_instruction_paths, file_type="custom_instructions"
                )
                auto_load_instructions = False  # Don't auto-load, user provided explicit instructions
                print("Custom instructions being used:")
                for file in custom_instructions_files:
                    print(f" - {file}")

    # Show what will be auto-loaded if no explicit instructions provided
    if auto_load_instructions and workspace_dir_name:
        llm_instruction_file = get_llm_specific_instruction_path(workspace_dir_name, args.engine)
        if llm_instruction_file:
            llm_name = ENGINE_TO_INSTRUCTION_FILE.get(args.engine, 'claude.md').replace('.md', '')
            print(f"LLM-specific instructions will be auto-loaded for {args.engine} engine")
            print(f" - {llm_instruction_file}")
        else:
            print("No custom instructions files available.")
    elif auto_load_instructions:
        print("No custom instructions files available.")

    # Determine RAG usage
    use_rag = args.rag and not args.no_rag
    if use_rag and workspace_dir_name:
        print(f"RAG enabled for workspace: {workspace_dir_name}")
    elif use_rag:
        print("RAG enabled (no workspace selected - RAG requires a workspace)")
        use_rag = False
    else:
        print("RAG disabled - using instructions only")

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

    # Convert engine/model to litellm format
    litellm_model = model
    if args.engine == 'anthropic':
        if not model.startswith('anthropic/'):
            litellm_model = f"anthropic/{model}"
    elif args.engine == 'openai':
        if not model.startswith('openai/') and not model.startswith('gpt') and not model.startswith('o1'):
            litellm_model = f"openai/{model}"
    elif args.engine == 'google':
        if not model.startswith('gemini/'):
            litellm_model = f"gemini/{model}"

    # Stream callback for interactive mode
    def print_chunk(chunk):
        print(chunk, end='', flush=True)

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
                model=litellm_model,
                max_tokens=max_tokens,
                max_input_tokens=max_input_tokens,
                temperature=temperature,
                history=history,
                supports_system_role=supports_system_role,
                stream=True,
                stream_callback=print_chunk,
                workspace_name=workspace_dir_name,
                use_rag=use_rag,
                auto_load_instructions=auto_load_instructions
            )
            print()  # Newline after streaming
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
            model=litellm_model,
            max_tokens=max_tokens,
            max_input_tokens=max_input_tokens,
            temperature=temperature,
            history=history,
            supports_system_role=supports_system_role,
            stream=False,
            workspace_name=workspace_dir_name,
            use_rag=use_rag,
            auto_load_instructions=auto_load_instructions
        )
        pattern = re.compile(r"OUTPUT ?= ?\"\"\"((\n|.)*?)\"\"\"", re.MULTILINE)
        is_structured = pattern.search(reply)
        if is_structured:
            reply = is_structured[1].strip()
        print(reply)


def run_compile(args):
    """Run the compile command (instructions only).

    Knowledge concatenation is handled by CI/CD (GitHub Actions).
    RAG indexing is handled by the 'index' subcommand.
    """
    import time
    from compiler.config import load_compile_config, validate_config, get_project_name
    from compiler import compile_project, compile_all_with_inheritance
    from compiler.manifest import format_manifest_summary

    def get_personal_repo_path_local(base_path):
        """Get the path to the user's personal ai-knowledge repo."""
        from compiler import get_personal_repo_path
        return get_personal_repo_path(base_path)

    def find_project_repo(project_name, base_path):
        """Find the repository path for a project name."""
        repo_name = f'ai-knowledge-{project_name}'
        repo_path = os.path.join(base_path, repo_name)
        if os.path.exists(repo_path):
            return repo_path
        raise FileNotFoundError(f"Repository not found: {repo_path}")

    def compile_repo(repo_path):
        """Compile instructions for a single repository."""
        start_time = time.time()

        if not args.quiet:
            print(f"Compiling instructions: {repo_path}")

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
            output_repo = get_personal_repo_path_local(args.base_path)

        try:
            result = compile_project(
                config=config,
                platforms=target_platforms,
                personalized=with_inheritance,
                force=args.force,
                use_llm=not args.no_llm,
                instructions_only=True,  # Always instructions-only
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

    # Determine what to compile
    if hasattr(args, 'all_with_inheritance') and args.all_with_inheritance:
        personal_repo = get_personal_repo_path_local(args.base_path)

        if not personal_repo or not os.path.exists(personal_repo):
            print(f"Error: Personal repo not found. Set default_workspace in ~/.config/ragbot/config.yaml", file=sys.stderr)
            return 1

        if not args.quiet:
            print("=" * 70)
            print("COMPILING ALL INSTRUCTIONS WITH INHERITANCE")
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
            instructions_only=True,  # Always instructions-only
        )

        if result['errors']:
            print("\nErrors:", file=sys.stderr)
            for error in result['errors']:
                print(f"  - {error}", file=sys.stderr)

        print(f"\n{'='*70}")
        print(f"COMPILATION COMPLETE")
        print(f"{'='*70}")
        print(f"Projects compiled: {result['total_compiled']}")
        print(f"Output location: {personal_repo}/compiled/")

        print("\nCompiled projects:")
        for name, proj_result in result['projects'].items():
            if 'error' in proj_result:
                print(f"  ✗ {name}: {proj_result['error']}")
            else:
                chain = proj_result.get('inheritance_chain', [])
                chain_str = ' → '.join(chain) if chain else 'baseline'
                print(f"  ✓ {name} ({chain_str})")

        return 1 if result['errors'] else 0

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
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, 'compile-config.yaml')):
            return compile_repo(cwd)
        else:
            print("Error: No project specified. Use --project, --repo, or --all-with-inheritance.")
            print("       Or run from an ai-knowledge-* directory with compile-config.yaml")
            return 1


def run_index(args):
    """Run the index command — index AI Knowledge content into vector store.

    Reads source files directly from ai-knowledge repositories and indexes
    them into Qdrant for RAG retrieval. No intermediate compiled files needed.
    """
    import time

    workspace_name = args.workspace

    if args.verbose:
        print(f"Indexing workspace: {workspace_name}")
        if args.force:
            print("Force mode: clearing existing index first")

    start_time = time.time()

    try:
        from rag import index_workspace_by_name
        indexed = index_workspace_by_name(workspace_name, force=args.force)
    except Exception as e:
        print(f"Indexing error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    elapsed = time.time() - start_time

    print(f"Indexed {indexed} documents for workspace '{workspace_name}' in {elapsed:.2f}s")
    return 0


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
    create_index_parser(subparsers)

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
