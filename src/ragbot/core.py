"""Core chat engine for Ragbot.

This module contains the main chat functionality extracted from helpers.py
to enable use as a library independent of the UI layer.
"""

from typing import Optional, List, Dict, Callable, Iterator, Any
import litellm
from litellm import completion
import tiktoken

# Enable dropping of unsupported params for models that have different parameter names
# (e.g., GPT-5 models use max_completion_tokens instead of max_tokens)
litellm.drop_params = True

from .exceptions import ChatError
from .keystore import get_api_key
from .config import get_default_model, get_model_info, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, DEFAULT_MAX_INPUT_TOKENS


def _get_api_key_for_model(model: str, workspace: Optional[str] = None) -> Optional[str]:
    """Get the appropriate API key for a model based on its provider.

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4-20250514")
        workspace: Optional workspace for workspace-specific keys

    Returns:
        API key string or None
    """
    model_lower = model.lower()

    if model_lower.startswith("anthropic/") or "claude" in model_lower:
        return get_api_key("anthropic", workspace)
    elif model_lower.startswith("openai/") or model_lower.startswith("gpt") or model_lower.startswith("o1"):
        return get_api_key("openai", workspace)
    elif model_lower.startswith("gemini/") or "gemini" in model_lower:
        return get_api_key("google", workspace)
    elif model_lower.startswith("bedrock/"):
        # AWS Bedrock uses AWS credentials, not API keys
        return None

    return None


def _get_api_key_param_name(model: str) -> Optional[str]:
    """Get the litellm parameter name for the API key based on model provider.

    Args:
        model: Model identifier

    Returns:
        Parameter name (e.g., "api_key") or None if not applicable
    """
    model_lower = model.lower()

    # LiteLLM uses 'api_key' for most providers
    if any(x in model_lower for x in ["anthropic", "claude", "openai", "gpt", "o1", "gemini"]):
        return "api_key"

    return None


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


def _get_engine_from_model(model: str) -> str:
    """Determine the engine/provider from a model by looking it up in engines.yaml.

    Uses engines.yaml as the single source of truth rather than pattern matching
    on model names (which would be fragile for future models like "opengpt").

    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4", "gpt-5.2")

    Returns:
        Engine name ('anthropic', 'openai', or 'google')
    """
    from .config import get_provider_for_model
    return get_provider_for_model(model or "")


def _load_llm_specific_instructions(workspace_name: str, model: str) -> str:
    """Load LLM-specific compiled instructions for a workspace.

    The compiler generates separate instruction files for each LLM platform:
    - claude.md for Anthropic models (Claude)
    - chatgpt.md for OpenAI models (GPT-5.x)
    - gemini.md for Google Gemini models

    When a user switches models mid-conversation, this function ensures the
    correct instructions are loaded for that specific LLM.

    Args:
        workspace_name: Name of the workspace (e.g., 'personal', 'company')
        model: Model identifier to determine which instructions to load

    Returns:
        Instructions content as string, or empty string if not found
    """
    try:
        from .workspaces import get_llm_specific_instruction_path
        import os

        engine = _get_engine_from_model(model)
        instruction_path = get_llm_specific_instruction_path(workspace_name, engine)

        if instruction_path and os.path.isfile(instruction_path):
            with open(instruction_path, 'r') as f:
                return f.read()
    except Exception:
        pass

    return ""


def chat(
    prompt: str,
    *,
    curated_datasets: str = "",
    custom_instructions: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_input_tokens: Optional[int] = None,
    stream: bool = True,
    temperature: Optional[float] = None,
    history: Optional[List[Dict[str, str]]] = None,
    supports_system_role: bool = True,
    stream_callback: Optional[Callable[[str], None]] = None,
    workspace_name: Optional[str] = None,
    use_rag: bool = True,
    rag_max_tokens: int = 2000,
    auto_load_instructions: bool = True
) -> str:
    """
    Send a request to the LLM API with the provided prompt and context.

    This is the core chat function that can be used by CLI, Streamlit, or API.

    **LLM-Specific Instructions:**
    When workspace_name is provided and custom_instructions is empty, this function
    automatically loads the appropriate LLM-specific instructions based on the model:
    - Anthropic models (Claude) → compiled/{workspace}/instructions/claude.md
    - OpenAI models (GPT-5.x) → compiled/{workspace}/instructions/chatgpt.md
    - Google models (Gemini) → compiled/{workspace}/instructions/gemini.md

    This ensures that when users switch models mid-conversation, the correct
    instructions are always used for that specific LLM platform.

    Args:
        prompt: The user's input message
        curated_datasets: Context documents as a string (legacy, use RAG instead)
        custom_instructions: Custom instructions as a string (if empty and workspace
            provided, LLM-specific instructions are auto-loaded)
        model: LLM model identifier (litellm format, e.g., "anthropic/claude-sonnet-4")
        max_tokens: Maximum tokens in the response
        max_input_tokens: Model's context window size (for history compaction)
        stream: Whether to stream the response
        temperature: Creativity level (0-2)
        history: Previous conversation messages
        supports_system_role: Whether the model supports system role
        stream_callback: Callback for streaming chunks
        workspace_name: Workspace name for instruction loading and RAG retrieval
        use_rag: Whether to use RAG for context retrieval
        rag_max_tokens: Maximum tokens for RAG context
        auto_load_instructions: If True and workspace_name provided, auto-load
            LLM-specific instructions (default: True)

    Returns:
        The generated response text

    Raises:
        ChatError: If the LLM call fails
    """
    # Apply defaults from engines.yaml configuration
    if model is None:
        model = get_default_model()
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS
    if max_input_tokens is None:
        max_input_tokens = DEFAULT_MAX_INPUT_TOKENS
    if temperature is None:
        # Get model-specific temperature from engines.yaml, fall back to global default
        model_info = get_model_info(model)
        if model_info and 'temperature' in model_info:
            temperature = model_info['temperature']
        else:
            temperature = DEFAULT_TEMPERATURE

    try:
        # Build system content - auto-load LLM-specific instructions if available
        system_content = ""

        if custom_instructions:
            # User provided explicit instructions - use them
            system_content = custom_instructions
        elif auto_load_instructions and workspace_name:
            # Auto-load LLM-specific instructions based on model
            # This ensures correct instructions when user switches models mid-conversation
            system_content = _load_llm_specific_instructions(workspace_name, model)

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

        # Get API key for the model
        api_key = _get_api_key_for_model(model, workspace_name)

        # Build completion kwargs - handle model-specific parameter names
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "api_key": api_key
        }

        # All GPT-5.x models use max_completion_tokens instead of max_tokens
        model_lower = model.lower()
        if 'gpt-5' in model_lower or 'gpt5' in model_lower:
            completion_kwargs["max_completion_tokens"] = max_tokens
        else:
            completion_kwargs["max_tokens"] = max_tokens

        # Make API call
        if stream and stream_callback:
            response_chunks = []
            llm_response = completion(
                **completion_kwargs,
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
            llm_response = completion(**completion_kwargs)
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

    **LLM-Specific Instructions:**
    Like chat(), when workspace_name is provided and custom_instructions is empty,
    this function automatically loads the appropriate LLM-specific instructions
    based on the model. This ensures correct instructions when users switch models.

    Args:
        prompt: The user's input message
        **kwargs: Same arguments as chat() except stream and stream_callback

    Yields:
        Response text chunks
    """
    # Remove stream-related kwargs
    kwargs.pop('stream', None)
    kwargs.pop('stream_callback', None)

    # Build same context as chat() - get defaults from engines.yaml configuration
    curated_datasets = kwargs.get('curated_datasets', '')
    custom_instructions = kwargs.get('custom_instructions', '')
    model = kwargs.get('model') or get_default_model()
    max_tokens = kwargs.get('max_tokens') or DEFAULT_MAX_TOKENS
    max_input_tokens = kwargs.get('max_input_tokens') or DEFAULT_MAX_INPUT_TOKENS

    # Get model-specific temperature from engines.yaml, fall back to global default
    temperature = kwargs.get('temperature')
    if temperature is None:
        model_info = get_model_info(model)
        if model_info and 'temperature' in model_info:
            temperature = model_info['temperature']
        else:
            temperature = DEFAULT_TEMPERATURE

    history = kwargs.get('history')
    supports_system_role = kwargs.get('supports_system_role', True)
    workspace_name = kwargs.get('workspace_name')
    use_rag = kwargs.get('use_rag', True)
    rag_max_tokens = kwargs.get('rag_max_tokens', 2000)
    auto_load_instructions = kwargs.get('auto_load_instructions', True)

    # Build system content - auto-load LLM-specific instructions if available
    system_content = ""

    if custom_instructions:
        # User provided explicit instructions - use them
        system_content = custom_instructions
    elif auto_load_instructions and workspace_name:
        # Auto-load LLM-specific instructions based on model
        # This ensures correct instructions when user switches models mid-conversation
        system_content = _load_llm_specific_instructions(workspace_name, model)

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

    # Get API key for the model
    api_key = _get_api_key_for_model(model, workspace_name)

    # Build completion kwargs - handle model-specific parameter names
    completion_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "api_key": api_key
    }

    # All GPT-5.x models use max_completion_tokens instead of max_tokens
    model_lower = model.lower()
    if 'gpt-5' in model_lower or 'gpt5' in model_lower:
        completion_kwargs["max_completion_tokens"] = max_tokens
    else:
        completion_kwargs["max_tokens"] = max_tokens

    # Stream response
    llm_response = completion(**completion_kwargs)

    for chunk in llm_response:
        if chunk and chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                yield delta.content
