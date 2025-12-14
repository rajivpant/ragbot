"""Custom exceptions for the Ragbot library."""


class RagbotError(Exception):
    """Base exception for all Ragbot errors."""
    pass


class ConfigurationError(RagbotError):
    """Error in configuration loading or parsing."""
    pass


class WorkspaceError(RagbotError):
    """Error related to workspace operations."""
    pass


class WorkspaceNotFoundError(WorkspaceError):
    """Requested workspace was not found."""
    pass


class ChatError(RagbotError):
    """Error during chat/LLM operations."""
    pass


class RAGError(RagbotError):
    """Error during RAG operations."""
    pass


class IndexingError(RAGError):
    """Error during index creation or update."""
    pass
