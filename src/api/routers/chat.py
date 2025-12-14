"""Chat API endpoints."""

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
from helpers import load_files

from ..dependencies import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


def load_workspace_context(workspace_name: str) -> tuple[str, str]:
    """Load instructions and datasets for a workspace.

    Returns:
        Tuple of (custom_instructions, curated_datasets)
    """
    if not workspace_name:
        return "", ""

    try:
        workspace = get_workspace(workspace_name)
        instructions_content = ""
        datasets_content = ""

        if workspace.get("instructions"):
            instructions_content, _ = load_files(
                workspace["instructions"], "custom_instructions"
            )
        if workspace.get("datasets"):
            datasets_content, _ = load_files(
                workspace["datasets"], "curated_datasets"
            )

        return instructions_content, datasets_content
    except WorkspaceNotFoundError:
        return "", ""


async def generate_chat_stream(request: ChatRequest):
    """Generate SSE events for streaming chat response."""
    custom_instructions, curated_datasets = load_workspace_context(request.workspace)

    # Convert history to dict format
    history = [{"role": msg.role.value, "content": msg.content} for msg in request.history]

    try:
        for chunk in chat_stream(
            request.prompt,
            curated_datasets=curated_datasets,
            custom_instructions=custom_instructions,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            history=history,
            workspace_name=request.workspace,
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

    If stream=True (default), returns Server-Sent Events.
    If stream=False, returns a JSON response.
    """
    if request.stream:
        return EventSourceResponse(generate_chat_stream(request))

    # Non-streaming response
    custom_instructions, curated_datasets = load_workspace_context(request.workspace)
    history = [{"role": msg.role.value, "content": msg.content} for msg in request.history]

    try:
        response_text = chat(
            request.prompt,
            curated_datasets=curated_datasets,
            custom_instructions=custom_instructions,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            history=history,
            stream=False,
            workspace_name=request.workspace,
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
