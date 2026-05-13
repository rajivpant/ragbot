"""Shared exception hierarchy for synthesis-engineering runtimes."""


class RagbotError(Exception):
    """Base exception for synthesis-engine errors.

    Named `RagbotError` because Ragbot was the first runtime built on this
    substrate. Treat it as the substrate's base exception: any synthesis
    runtime surfaces errors through this hierarchy.
    """
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
