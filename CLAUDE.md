# Claude Code Context: ragbot

## Repository: ragbot (PUBLIC)

This is a **PUBLIC** open source repository. Be careful not to include confidential information.

## Repository Ecosystem

| Repository | Type | Purpose | Location |
|------------|------|---------|----------|
| **ragbot** | Public | AI assistant CLI and Streamlit UI | `~/projects/my-projects/ragbot/` |
| **ragenie** | Public | Next-gen RAG platform | `~/projects/my-projects/ragenie/` |
| **ragbot-data** | Private | Shared data for both products | `~/ragbot-data/` |

Note: Home directory varies by machine (`/Users/rajiv` vs `/Users/rajivpant`), so use `~` for paths.

## VS Code Workspace

All three repositories are in the same VS Code workspace for unified development.

## Product Relationship

- **Ragbot**: Actively maintained and upgraded. Production-ready CLI and Streamlit UI.
- **RaGenie**: Successor product with advanced RAG capabilities. Under development.
- Both products share `ragbot-data` as their data layer.
- Both products will continue to be actively developed.

## Architecture

```text
ragbot/
├── src/
│   ├── ragbot.py              # CLI entry point
│   ├── ragbot_streamlit.py    # Streamlit web UI
│   ├── helpers.py             # Shared utilities
│   └── rag/                   # RAG module (planned)
├── docker-compose.yml
├── requirements.txt
├── engines.yaml               # LLM engine configurations
└── profiles.yaml              # User profiles
```

## Data Location

Ragbot reads data from `~/ragbot-data/workspaces/`:

- **instructions/** - WHO: Identity/persona files
- **runbooks/** - HOW: Procedure guides
- **datasets/** - WHAT: Reference knowledge

## Privacy Guidelines for This Public Repo

### NEVER include in docs or code

- Client/employer company names (use "example-company" instead)
- Workspace names that reveal client relationships
- Any content from ragbot-data that could identify clients

### Safe to use

- "rajiv" workspace name (owner's personal workspace)
- Open source project workspace names (e.g., "ragenie")
- Generic example names: "example-company", "acme-corp", "test-workspace"

### Example transformations

When writing documentation or examples:

- Use "example-company" or "client-workspace" instead of actual client names
- Use generic business scenarios instead of actual client project details

## Key Concepts

### Workspace System

- `user_workspace` config points to the user's identity workspace (e.g., "rajiv")
- Workspace folder names are usernames - do NOT rename to generic names
- Workspaces inherit from the user workspace

### Multi-User Design

- System supports multiple users with separate identity workspaces
- Different workspaces may come from different git repos
- User workspaces are private; some workspaces may be shared team repos

## Development Notes

- Python CLI with Streamlit UI
- Uses LiteLLM for multi-provider LLM support
- Engines configured in `engines.yaml`
- Profiles/workspaces configured in `profiles.yaml`
