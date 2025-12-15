"""Chat API endpoints.

LLM-Specific Instructions:
The chat functions in core.py automatically load the appropriate LLM-specific
instructions based on the model being used:
- Anthropic models (Claude) → compiled/{workspace}/instructions/claude.md
- OpenAI models (GPT, o1, o3) → compiled/{workspace}/instructions/chatgpt.md
- Google models (Gemini) → compiled/{workspace}/instructions/gemini.md

When users switch models mid-conversation, the correct instructions are
automatically loaded for each request. This is handled centrally in core.py
to avoid code duplication between CLI and API.
"""

import os
import sys
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ragbot import (
    ChatRequest,
    ChatResponse,
    chat,
    chat_stream,
    get_workspace,
    WorkspaceNotFoundError,
)

from ..dependencies import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_workspace_dir_name(workspace_name: Optional[str]) -> Optional[str]:
    """Get the directory name for a workspace.

    Args:
        workspace_name: Display name or dir_name of workspace

    Returns:
        The dir_name used for file paths, or None if not found
    """
    if not workspace_name:
        return None

    try:
        workspace = get_workspace(workspace_name)
        return workspace.get("dir_name", workspace_name)
    except WorkspaceNotFoundError:
        return None


async def generate_chat_stream(request: ChatRequest):
    """Generate SSE events for streaming chat response.

    LLM-specific instructions are automatically loaded by core.py based on
    the model being used. When users switch models mid-conversation, the
    correct instructions (claude.md, chatgpt.md, or gemini.md) are loaded
    for each request.
    """
    # Convert history to dict format
    history = [{"role": msg.role.value, "content": msg.content} for msg in request.history]

    # Get workspace dir_name for file path resolution
    workspace_dir_name = _get_workspace_dir_name(request.workspace)

    try:
        # core.py automatically loads LLM-specific instructions based on model
        for chunk in chat_stream(
            request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            history=history,
            workspace_name=workspace_dir_name,
            use_rag=request.use_rag,
            rag_max_tokens=request.rag_max_tokens,
        ):
            yield {
                "event": "message",
                "data": json.dumps({"content": chunk})
            }

        yield {
            "event": "done",
            "data": json.dumps({"status": "complete"})
        }
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }


@router.post("", response_model=None)
async def chat_endpoint(request: ChatRequest):
    """Send a chat message and receive a response.

    LLM-specific instructions are automatically loaded based on the model:
    - Claude models use claude.md
    - GPT/o1/o3 models use chatgpt.md
    - Gemini models use gemini.md

    If stream=True (default), returns Server-Sent Events.
    If stream=False, returns a JSON response.
    """
    if request.stream:
        return EventSourceResponse(generate_chat_stream(request))

    # Non-streaming response
    history = [{"role": msg.role.value, "content": msg.content} for msg in request.history]
    workspace_dir_name = _get_workspace_dir_name(request.workspace)

    try:
        # core.py automatically loads LLM-specific instructions based on model
        response_text = chat(
            request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            history=history,
            stream=False,
            workspace_name=workspace_dir_name,
            use_rag=request.use_rag,
            rag_max_tokens=request.rag_max_tokens,
        )

        return ChatResponse(
            response=response_text,
            model=request.model,
            workspace=request.workspace,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
