"""Ragbot - AI Knowledge Assistant Library.

This package provides the core functionality for Ragbot:
- Chat engine with streaming support
- Workspace discovery and management
- Configuration loading
- Pydantic models for API integration

Example usage:
    from ragbot import chat, discover_workspaces, get_workspace

    # List available workspaces
    workspaces = discover_workspaces()

    # Get a specific workspace
    workspace = get_workspace("rajiv")

    # Chat with context from workspace
    response = chat(
        prompt="Hello!",
        workspace_name="rajiv",
        model="anthropic/claude-sonnet-4-20250514"
    )
"""

from .config import (
    VERSION,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    get_all_models,
    get_model_info,
    get_default_model,
    get_available_models,
    check_api_keys,
    load_yaml_config,
    load_data_config,
)

from .core import (
    chat,
    chat_stream,
    count_tokens,
    compact_history,
)

from .workspaces import (
    discover_workspaces,
    discover_ai_knowledge_repos,
    find_ai_knowledge_root,
    resolve_workspace_paths,
    workspace_to_profile,
    load_workspaces_as_profiles,
    get_workspace,
    get_workspace_info,
    list_workspace_info,
)

from .exceptions import (
    RagbotError,
    ConfigurationError,
    WorkspaceError,
    WorkspaceNotFoundError,
    ChatError,
    RAGError,
    IndexingError,
)

from .models import (
    MessageRole,
    Message,
    ChatRequest,
    ChatResponse,
    WorkspaceInfo,
    WorkspaceList,
    IndexStatus,
    IndexRequest,
    ModelInfo,
    ModelsResponse,
    ConfigResponse,
    HealthResponse,
)

__version__ = VERSION

__all__ = [
    # Version
    "VERSION",
    "__version__",
    # Config
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "get_all_models",
    "get_model_info",
    "get_default_model",
    "get_available_models",
    "check_api_keys",
    "load_yaml_config",
    "load_data_config",
    # Core
    "chat",
    "chat_stream",
    "count_tokens",
    "compact_history",
    # Workspaces
    "discover_workspaces",
    "discover_ai_knowledge_repos",
    "find_ai_knowledge_root",
    "resolve_workspace_paths",
    "workspace_to_profile",
    "load_workspaces_as_profiles",
    "get_workspace",
    "get_workspace_info",
    "list_workspace_info",
    # Exceptions
    "RagbotError",
    "ConfigurationError",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "ChatError",
    "RAGError",
    "IndexingError",
    # Models
    "MessageRole",
    "Message",
    "ChatRequest",
    "ChatResponse",
    "WorkspaceInfo",
    "WorkspaceList",
    "IndexStatus",
    "IndexRequest",
    "ModelInfo",
    "ModelsResponse",
    "ConfigResponse",
    "HealthResponse",
]
