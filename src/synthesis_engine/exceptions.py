"""Shared exception hierarchy for synthesis-engineering runtimes.

Every error raised by the substrate inherits from :class:`SynthesisError`.
Runtimes (Ragbot, Ragenie, synthesis-console) may add their own runtime-
scoped exception classes, but the substrate's base class lives here so a
caller that wants to catch "any synthesis-substrate error" has a single
type to use.
"""


class SynthesisError(Exception):
    """Base exception for synthesis-engine substrate errors.

    Catch this to handle any error originating in the substrate (config
    loading, workspace discovery, vector store, LLM dispatch, skill
    parsing, etc.). Runtime-specific exceptions should define their own
    base class in the runtime package; the substrate hierarchy stays
    neutral.
    """
    pass


class ConfigurationError(SynthesisError):
    """Error in configuration loading or parsing."""
    pass


class WorkspaceError(SynthesisError):
    """Error related to workspace operations."""
    pass


class WorkspaceNotFoundError(WorkspaceError):
    """Requested workspace was not found."""
    pass


class ChatError(SynthesisError):
    """Error during chat/LLM operations."""
    pass


class RAGError(SynthesisError):
    """Error during RAG operations."""
    pass


class IndexingError(RAGError):
    """Error during index creation or update."""
    pass
