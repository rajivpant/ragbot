#!/usr/bin/env python3
# ragbot.py - https://github.com/synthesisengineering/ragbot

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
from ragbot.config import normalize_model_id
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

    # Reasoning / thinking effort. Reads from RAGBOT_THINKING_EFFORT env when
    # unset; per-call value wins. Models that don't advertise thinking
    # silently ignore the value.
    chat_parser.add_argument(
        "--thinking-effort",
        choices=["auto", "off", "minimal", "low", "medium", "high"],
        default=None,
        help="Reasoning effort for the LLM call. Defaults: flagship → medium, "
             "non-flagship → off, models without thinking metadata → ignored. "
             "Override via this flag or RAGBOT_THINKING_EFFORT env var."
    )

    # Cross-workspace search controls.
    chat_parser.add_argument(
        "--workspace", "-w",
        action="append",
        default=None,
        dest="extra_workspaces",
        help="Additional workspace to query alongside the primary one. "
             "Repeatable. When unset, the canonical 'skills' workspace is "
             "auto-included if it has indexed content."
    )
    chat_parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Disable auto-inclusion of the 'skills' workspace in retrieval."
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
        default=os.environ.get('RAGBOT_BASE_PATH'),
        help='Optional flat-parent path containing ai-knowledge-* repos. '
             'When unset, repos are discovered via ~/.synthesis/console.yaml '
             'and the workspace-rooted layout.'
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
        help='Workspace name to index (e.g., personal, example-client)'
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


def create_skills_parser(subparsers):
    """Create the `skills` subcommand parser.

    List, inspect, and index Agent Skills (directories with SKILL.md).
    """
    skills_parser = subparsers.add_parser(
        'skills',
        help='Discover, inspect, and index Agent Skills',
        description='Manage Agent Skills (directories with SKILL.md) for RAG '
                    'indexing and inspection. Skills are discovered from '
                    '~/.synthesis/skills, ~/.claude/skills, and plugin caches.'
    )
    skills_subparsers = skills_parser.add_subparsers(dest='skills_command', required=True)

    list_parser = skills_subparsers.add_parser('list', help='List discovered skills.')
    list_parser.add_argument('--verbose', '-v', action='store_true',
                             help='Include description and file counts.')
    list_parser.set_defaults(func=run_skills_list)

    info_parser = skills_subparsers.add_parser('info', help='Show details for one skill.')
    info_parser.add_argument('name', help='Skill name (directory or frontmatter name).')
    info_parser.set_defaults(func=run_skills_info)

    index_parser = skills_subparsers.add_parser(
        'index',
        help='Index discovered skills into a vector-store workspace (default: `skills`).',
    )
    index_parser.add_argument('--workspace', '-w', default='skills',
                              help='Target workspace name (default: skills).')
    index_parser.add_argument('--only', action='append', default=None,
                              help='Restrict to a specific skill name (repeatable).')
    index_parser.add_argument('--force', '-f', action='store_true',
                              help='Clear the target workspace before indexing.')
    index_parser.set_defaults(func=run_skills_index)

    return skills_parser


def create_db_parser(subparsers):
    """Create the db subcommand parser.

    Diagnostics and maintenance for the configured vector store backend.
    """
    db_parser = subparsers.add_parser(
        'db',
        help='Vector store backend diagnostics and maintenance',
        description='Inspect and maintain the configured vector store backend '
                    '(pgvector or qdrant). Use `ragbot db status` to verify '
                    'connectivity, list collections, and confirm migrations '
                    'are applied.'
    )

    db_subparsers = db_parser.add_subparsers(dest='db_command', required=True)

    status_parser = db_subparsers.add_parser(
        'status',
        help='Show backend health, configured connection, and indexed collections.'
    )
    status_parser.set_defaults(func=run_db_status)

    init_parser = db_subparsers.add_parser(
        'init',
        help='Apply schema migrations (no-op if already applied). Pgvector only.'
    )
    init_parser.set_defaults(func=run_db_init)

    return db_parser


def run_chat(args):
    """Run the chat command."""
    if args.list_saved:
        print_saved_files(data_dir)
        return

    new_session = True if not args.load else False

    # Workspace discovery for the chat command:
    #   - Honour RAGBOT_DATA_ROOT (legacy flat-parent override) when set.
    #   - Honour RAGBOT_BASE_PATH (the canonical override used elsewhere).
    #   - Otherwise fall through to the full discovery chain
    #     (~/.synthesis/console.yaml, ~/workspaces/*/ai-knowledge-*, legacy fallbacks).
    data_root = os.getenv('RAGBOT_DATA_ROOT') or os.getenv('RAGBOT_BASE_PATH')
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

    # Resolve additional workspaces (cross-workspace retrieval).
    #   --workspace W (repeatable): explicit list (auto-include disabled).
    #   --no-skills:                  explicit opt-out of skills auto-include.
    #   neither:                      auto-include policy applies in get_relevant_context.
    extra_workspaces_arg = getattr(args, 'extra_workspaces', None)
    no_skills = getattr(args, 'no_skills', False)
    if extra_workspaces_arg is not None:
        # Explicit list given; respect --no-skills filter.
        additional_workspaces = [w for w in extra_workspaces_arg if w and (not no_skills or w != 'skills')]
    elif no_skills:
        # User opts out without specifying alternates.
        additional_workspaces = []
    else:
        additional_workspaces = None  # let get_relevant_context auto-include skills

    thinking_effort = getattr(args, 'thinking_effort', None)

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

    # Convert engine/model to litellm format via the shared normalizer.
    litellm_model = normalize_model_id(args.engine, model)

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
                auto_load_instructions=auto_load_instructions,
                thinking_effort=thinking_effort,
                additional_workspaces=additional_workspaces,
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


def run_skills_list(args):
    """Print discovered skills."""
    from ragbot.skills import discover_skills

    skills = discover_skills()
    if not skills:
        print("No skills discovered. Searched ~/.synthesis/skills and ~/.claude/skills.")
        return 0

    print(f"Discovered {len(skills)} skills:")
    for s in skills:
        if args.verbose:
            desc_short = (s.description or '').strip().replace('\n', ' ')[:80]
            extras = []
            if s.references:
                extras.append(f"{len(s.references)} refs")
            if s.scripts:
                extras.append(f"{len(s.scripts)} scripts")
            if s.other_files:
                extras.append(f"{len(s.other_files)} other")
            extras_str = f" ({', '.join(extras)})" if extras else ""
            version_str = f" v{s.version}" if s.version else ""
            print(f"  {s.name}{version_str}{extras_str}")
            if desc_short:
                print(f"    {desc_short}")
        else:
            print(f"  {s.name}")
    return 0


def run_skills_info(args):
    """Show full details for one skill."""
    from ragbot.skills import discover_skills

    target = args.name
    skills = discover_skills()
    skill = next((s for s in skills if s.name == target), None)
    if skill is None:
        print(f"Skill not found: {target}", file=sys.stderr)
        print(f"Run `ragbot skills list` to see all discovered skills.", file=sys.stderr)
        return 1

    print(f"Name:        {skill.name}")
    print(f"Path:        {skill.path}")
    print(f"Version:     {skill.version or '(unset)'}")
    print(f"Description: {skill.description or '(none)'}")
    print(f"Triggers:    {', '.join(skill.triggers) if skill.triggers else '(none)'}")
    print(f"Files:       {len(skill.files)}")
    print()
    for f in skill.files:
        chars = len(f.content) if f.is_text else 0
        print(f"  {f.kind.value:18s} {f.relative_path:50s} {chars} chars")
    return 0


def run_skills_index(args):
    """Index discovered skills into a vector-store workspace."""
    from rag import index_skills, get_index_status

    result = index_skills(
        workspace_name=args.workspace,
        only=args.only,
        force=args.force,
    )
    if 'error' in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    print(f"Backend:        {result.get('backend', '?')}")
    print(f"Workspace:      {result.get('workspace', '?')}")
    print(f"Skills indexed: {result.get('skills_indexed', 0)}")
    print(f"Chunks indexed: {result.get('chunks_indexed', 0)}")
    skipped = result.get('skipped') or []
    if skipped:
        print(f"Skipped (no indexable text): {', '.join(skipped)}")
    indexed_total, count = get_index_status(args.workspace)
    print(f"Workspace now contains {count} chunks (indexed={indexed_total}).")
    return 0


def run_db_status(args):
    """Print backend health and indexed collections.

    In demo mode the listing is filtered to only the bundled demo
    workspace, so screenshots taken with ``RAGBOT_DEMO=1`` cannot leak
    real workspace names that happen to exist on the same vector store.
    """
    from ragbot.vectorstore import get_vector_store
    from ragbot.demo import is_demo_mode, DEMO_WORKSPACE_NAME

    vs = get_vector_store()
    if vs is None:
        print("Vector backend: unavailable.")
        print("Check RAGBOT_VECTOR_BACKEND and RAGBOT_DATABASE_URL.")
        return 1

    health = vs.healthcheck()
    print(f"Backend: {vs.backend_name}")
    print(f"Healthy: {health.get('ok', False)}")
    for k, v in health.items():
        if k in ('backend', 'ok'):
            continue
        print(f"  {k}: {v}")

    collections = vs.list_collections()
    if is_demo_mode():
        # Show only demo-scoped collections. Hide everything else so
        # screenshots cannot leak real workspace names that happen to
        # exist on the same vector store.
        from ragbot.demo import DEMO_SKILLS_WORKSPACE_NAME
        allowed = {DEMO_WORKSPACE_NAME, DEMO_SKILLS_WORKSPACE_NAME}
        collections = [c for c in collections if c in allowed]
    print(f"\nIndexed collections ({len(collections)}):")
    if not collections:
        print("  (none)")
    for name in collections:
        info = vs.get_collection_info(name) or {}
        print(f"  {name:30s} chunks={info.get('count', 0)}")
    return 0


def run_db_init(args):
    """Apply schema migrations explicitly (idempotent)."""
    from ragbot.vectorstore import get_vector_store

    vs = get_vector_store()
    if vs is None:
        print("Vector backend: unavailable.")
        return 1

    if vs.backend_name != 'pgvector':
        print(f"`db init` is a no-op for {vs.backend_name}; nothing to do.")
        return 0

    # Pgvector backend runs migrations on construction; explicit re-trigger
    # by calling init_collection(workspace='_init_') is harmless and confirms
    # the schema is applied.
    ok = vs.init_collection('_init_check_', vector_size=384)
    print("Schema migrations applied." if ok else "Migration failed (see logs).")
    return 0 if ok else 1


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
        from ragbot.workspaces import resolve_repo_index
        repo_path = resolve_repo_index(base_path).get(project_name)
        if repo_path and os.path.exists(repo_path):
            return repo_path
        raise FileNotFoundError(
            f"Repository not found for project '{project_name}'. "
            f"Check ~/.synthesis/console.yaml or pass --base-path."
        )

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
            print(f"Error: Personal repo not found. Set default_workspace in ~/.synthesis/ragbot.yaml", file=sys.stderr)
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

    # Top-level --demo flag: equivalent to setting RAGBOT_DEMO=1 for the
    # rest of the process. Activates the bundled demo workspace and skill,
    # hard-isolating from any real workspaces or skills on the host.
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run in demo mode using the bundled sample workspace and skill.'
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
    create_skills_parser(subparsers)
    create_db_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # If --demo was passed at the top level (or on a subcommand), set the
    # env var early so every later import that reads RAGBOT_DEMO sees it.
    if getattr(args, 'demo', False):
        os.environ['RAGBOT_DEMO'] = '1'

    # If no command specified, default to chat behavior for backward compatibility
    if args.command is None:
        # Re-parse with 'chat' as the default command
        # This maintains backward compatibility with existing usage like:
        #   ragbot -p "prompt"
        #   ragbot -i
        sys.argv.insert(1, 'chat')
        args = parser.parse_args()
        if getattr(args, 'demo', False):
            os.environ['RAGBOT_DEMO'] = '1'

    # Demo mode: ensure the bundled workspace is indexed before any
    # subcommand runs. First-run setup; idempotent on subsequent runs.
    if os.environ.get('RAGBOT_DEMO', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        _ensure_demo_indexed()

    # Run the appropriate command
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


def _ensure_demo_indexed() -> None:
    """First-run auto-indexing for demo mode.

    Indexes the bundled demo workspace and demo skill into the configured
    vector backend (typically pgvector) under the canonical 'demo'
    workspace name. Idempotent: if the workspace already has chunks,
    this is a no-op.
    """
    try:
        from ragbot.demo import DEMO_WORKSPACE_NAME, demo_workspace_path
        from rag import (
            get_index_status,
            index_content,
            index_skills,
            init_collection,
        )
    except Exception:
        # Imports might fail in narrow contexts (e.g., db status). Skip
        # silently — discovery still hard-isolates either way.
        return

    workspace_path = demo_workspace_path()
    if workspace_path is None:
        return

    # Skip if already indexed.
    indexed, count = get_index_status(DEMO_WORKSPACE_NAME)
    if indexed and count > 0:
        return

    init_collection(DEMO_WORKSPACE_NAME)
    source_dir = workspace_path / 'source'
    for category in ('datasets', 'runbooks', 'instructions'):
        category_dir = source_dir / category
        if category_dir.is_dir():
            try:
                index_content(DEMO_WORKSPACE_NAME, [str(category_dir)], content_type=category)
            except Exception as exc:  # noqa: BLE001
                print(f"Demo: skipped {category} indexing ({exc})", file=sys.stderr)

    # Index the bundled demo skill into a demo-scoped workspace so the
    # demo's cross-workspace fan-out can NOT retrieve real skill content
    # that happens to share the host vector store.
    try:
        from ragbot.demo import DEMO_SKILLS_WORKSPACE_NAME
        index_skills(workspace_name=DEMO_SKILLS_WORKSPACE_NAME, force=False)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main() or 0)
