"""Core chat engine for Ragbot.

This module contains the main chat functionality extracted from helpers.py
to enable use as a library independent of the UI layer.
"""

from typing import Optional, List, Dict, Callable, Iterator, Any
from litellm import completion
import tiktoken

from .exceptions import ChatError


# Token counting utilities
_tokenizer = None


def get_tokenizer():
    """Get or create a cached tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding('cl100k_base')
    return _tokenizer


def count_tokens(text: str) -> int:
    """Count tokens in a text string using cl100k_base encoding.

    This provides a reasonable approximation for most modern LLMs including
    GPT-4, Claude, and Gemini models.
    """
    if not text:
        return 0
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))


def compact_history(
    history: List[Dict[str, str]],
    max_tokens: int,
    system_tokens: int = 0,
    current_prompt_tokens: int = 0,
    reserve_for_response: int = 4096
) -> List[Dict[str, str]]:
    """
    Compact conversation history to fit within token limits.

    Uses a sliding window approach: keeps the most recent messages while ensuring
    the total fits within the context window.

    Args:
        history: List of message dicts with 'role' and 'content'
        max_tokens: Maximum context window size
        system_tokens: Tokens used by system message
        current_prompt_tokens: Tokens in the current user prompt
        reserve_for_response: Tokens to reserve for the model's response

    Returns:
        Compacted history list
    """
    if not history:
        return []

    available_for_history = max_tokens - system_tokens - current_prompt_tokens - reserve_for_response

    if available_for_history <= 0:
        return []

    tokenizer = get_tokenizer()
    compacted = []
    total_tokens = 0

    # Process from newest to oldest
    for msg in reversed(history):
        msg_tokens = len(tokenizer.encode(msg['content']))
        msg_tokens += 4  # Overhead per message

        if total_tokens + msg_tokens <= available_for_history:
            compacted.insert(0, msg)
            total_tokens += msg_tokens
        else:
            break

    return compacted


def chat(
    prompt: str,
    *,
    curated_datasets: str = "",
    custom_instructions: str = "",
    model: str = "anthropic/claude-sonnet-4-20250514",
    max_tokens: int = 4096,
    max_input_tokens: int = 128000,
    stream: bool = True,
    temperature: float = 0.75,
    history: Optional[List[Dict[str, str]]] = None,
    supports_system_role: bool = True,
    stream_callback: Optional[Callable[[str], None]] = None,
    workspace_name: Optional[str] = None,
    use_rag: bool = True,
    rag_max_tokens: int = 2000
) -> str:
    """
    Send a request to the LLM API with the provided prompt and context.

    This is the core chat function that can be used by CLI, Streamlit, or API.

    Args:
        prompt: The user's input message
        curated_datasets: Context documents as a string
        custom_instructions: Custom instructions as a string
        model: LLM model identifier (litellm format)
        max_tokens: Maximum tokens in the response
        max_input_tokens: Model's context window size (for history compaction)
        stream: Whether to stream the response
        temperature: Creativity level (0-2)
        history: Previous conversation messages
        supports_system_role: Whether the model supports system role
        stream_callback: Callback for streaming chunks
        workspace_name: Workspace name for RAG retrieval
        use_rag: Whether to use RAG for context retrieval
        rag_max_tokens: Maximum tokens for RAG context

    Returns:
        The generated response text

    Raises:
        ChatError: If the LLM call fails
    """
    try:
        # Build system content
        system_content = ""
        if custom_instructions:
            system_content = custom_instructions

        # RAG retrieval
        rag_context = ""
        if use_rag and workspace_name:
            try:
                # Import dynamically to avoid circular imports and optional dependency
                import sys
                import os
                # Add parent directory to path for sibling imports
                parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)
                from rag import is_rag_available, get_relevant_context
                if is_rag_available():
                    rag_context = get_relevant_context(
                        workspace_name, prompt, max_tokens=rag_max_tokens
                    )
            except ImportError:
                pass

        if curated_datasets:
            system_content = f"{system_content}\n{curated_datasets}" if system_content else curated_datasets

        if rag_context:
            system_content = f"{system_content}\n\n{rag_context}" if system_content else rag_context

        # Calculate tokens for history compaction
        system_tokens = count_tokens(system_content) if system_content else 0
        prompt_tokens = count_tokens(prompt)

        # Compact history
        compacted_history = []
        if history:
            past_history = [msg for msg in history if msg.get('content') != prompt]
            compacted_history = compact_history(
                past_history,
                max_tokens=max_input_tokens,
                system_tokens=system_tokens,
                current_prompt_tokens=prompt_tokens,
                reserve_for_response=max_tokens
            )

        # Build messages
        if supports_system_role:
            messages = []
            if system_content.strip():
                messages.append({"role": "system", "content": system_content})
            messages.extend(compacted_history)
            messages.append({"role": "user", "content": prompt})
        else:
            # For models without system role support
            messages = []
            if custom_instructions:
                messages.append({"role": "user", "content": custom_instructions})
                messages.append({"role": "assistant", "content": "I understand. I'll follow these instructions."})
            if curated_datasets:
                messages.append({"role": "user", "content": curated_datasets})
                messages.append({"role": "assistant", "content": "I've reviewed the context information provided."})
            messages.extend(compacted_history)
            messages.append({"role": "user", "content": prompt})

        # Make API call
        if stream and stream_callback:
            response_chunks = []
            llm_response = completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            for chunk in llm_response:
                if chunk and chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        response_chunks.append(delta.content)
                        stream_callback(delta.content)

            return ''.join(response_chunks)
        else:
            llm_response = completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return llm_response.get('choices', [{}])[0].get('message', {}).get('content', '')

    except Exception as e:
        raise ChatError(f"Chat failed: {e}") from e


def chat_stream(
    prompt: str,
    **kwargs
) -> Iterator[str]:
    """
    Generator version of chat that yields response chunks.

    Useful for SSE streaming in FastAPI.

    Args:
        prompt: The user's input message
        **kwargs: Same arguments as chat() except stream and stream_callback

    Yields:
        Response text chunks
    """
    # Remove stream-related kwargs
    kwargs.pop('stream', None)
    kwargs.pop('stream_callback', None)

    # Build same context as chat()
    curated_datasets = kwargs.get('curated_datasets', '')
    custom_instructions = kwargs.get('custom_instructions', '')
    model = kwargs.get('model', 'anthropic/claude-sonnet-4-20250514')
    max_tokens = kwargs.get('max_tokens', 4096)
    max_input_tokens = kwargs.get('max_input_tokens', 128000)
    temperature = kwargs.get('temperature', 0.75)
    history = kwargs.get('history')
    supports_system_role = kwargs.get('supports_system_role', True)
    workspace_name = kwargs.get('workspace_name')
    use_rag = kwargs.get('use_rag', True)
    rag_max_tokens = kwargs.get('rag_max_tokens', 2000)

    # Build system content
    system_content = ""
    if custom_instructions:
        system_content = custom_instructions

    # RAG retrieval
    rag_context = ""
    if use_rag and workspace_name:
        try:
            import sys
            import os
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from rag import is_rag_available, get_relevant_context
            if is_rag_available():
                rag_context = get_relevant_context(
                    workspace_name, prompt, max_tokens=rag_max_tokens
                )
        except ImportError:
            pass

    if curated_datasets:
        system_content = f"{system_content}\n{curated_datasets}" if system_content else curated_datasets

    if rag_context:
        system_content = f"{system_content}\n\n{rag_context}" if system_content else rag_context

    # Calculate tokens for history compaction
    system_tokens = count_tokens(system_content) if system_content else 0
    prompt_tokens = count_tokens(prompt)

    # Compact history
    compacted_history = []
    if history:
        past_history = [msg for msg in history if msg.get('content') != prompt]
        compacted_history = compact_history(
            past_history,
            max_tokens=max_input_tokens,
            system_tokens=system_tokens,
            current_prompt_tokens=prompt_tokens,
            reserve_for_response=max_tokens
        )

    # Build messages
    if supports_system_role:
        messages = []
        if system_content.strip():
            messages.append({"role": "system", "content": system_content})
        messages.extend(compacted_history)
        messages.append({"role": "user", "content": prompt})
    else:
        messages = []
        if custom_instructions:
            messages.append({"role": "user", "content": custom_instructions})
            messages.append({"role": "assistant", "content": "I understand. I'll follow these instructions."})
        if curated_datasets:
            messages.append({"role": "user", "content": curated_datasets})
            messages.append({"role": "assistant", "content": "I've reviewed the context information provided."})
        messages.extend(compacted_history)
        messages.append({"role": "user", "content": prompt})

    # Stream response
    llm_response = completion(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=True
    )

    for chunk in llm_response:
        if chunk and chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                yield delta.content
