"""Pydantic models for the Ragbot library."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Role of a message in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """A single message in conversation history."""
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    """Request model for chat API."""
    prompt: str = Field(..., description="User's message")
    workspace: Optional[str] = Field(None, description="Workspace name for context")
    model: str = Field("anthropic/claude-sonnet-4-20250514", description="Model to use")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Creativity level (None uses model default from engines.yaml)")
    max_tokens: int = Field(4096, ge=1, le=8192, description="Max response tokens")
    use_rag: bool = Field(True, description="Use RAG for context retrieval")
    rag_max_tokens: int = Field(2000, ge=0, description="Max tokens for RAG context")
    history: List[Message] = Field(default_factory=list, description="Conversation history")
    stream: bool = Field(True, description="Stream the response")


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    response: str
    model: str
    workspace: Optional[str] = None
    tokens_used: Optional[int] = None


class WorkspaceInfo(BaseModel):
    """Information about a workspace."""
    name: str = Field(..., description="Display name")
    dir_name: str = Field(..., description="Directory name")
    description: Optional[str] = None
    status: str = Field("active", description="Workspace status")
    type: str = Field("project", description="Workspace type")
    inherits_from: List[str] = Field(default_factory=list)
    has_instructions: bool = False
    has_datasets: bool = False
    has_source: bool = False
    repo_path: Optional[str] = None


class WorkspaceList(BaseModel):
    """List of workspaces response."""
    workspaces: List[WorkspaceInfo]
    count: int


class IndexStatus(BaseModel):
    """RAG index status for a workspace."""
    workspace: str
    indexed: bool
    document_count: int = 0
    last_indexed: Optional[str] = None


class IndexRequest(BaseModel):
    """Request to index a workspace."""
    force: bool = Field(False, description="Force re-indexing even if up to date")


class ModelInfo(BaseModel):
    """Information about an available model."""
    id: str
    name: str
    provider: str
    context_window: int
    supports_streaming: bool = True
    supports_system_role: bool = True


class ModelsResponse(BaseModel):
    """List of available models."""
    models: List[ModelInfo]
    default_model: str


class ApiKeyStatus(BaseModel):
    """API key configuration status."""
    provider: str
    configured: bool
    source: str = Field("default", description="Where the key comes from: 'default', 'workspace', or 'none'")


class ConfigResponse(BaseModel):
    """Configuration response."""
    version: str
    ai_knowledge_root: Optional[str] = None
    workspace_count: int = 0
    rag_available: bool = False
    default_model: str = "anthropic/claude-sonnet-4-20250514"
    default_workspace: Optional[str] = None
    api_keys: Dict[str, bool] = Field(default_factory=dict, description="Provider to configured status")
    workspaces_with_keys: List[str] = Field(default_factory=list, description="Workspaces with custom API keys")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str
    rag_available: bool = False
