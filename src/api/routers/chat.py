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

Task registration (Phase 5)
---------------------------

Every streaming chat invocation registers itself with the process-wide
:class:`BackgroundTaskManager` BEFORE the SSE response starts emitting tokens.
The substrate gives the chat stream a task id, a JSONL audit trail, and — most
importantly for the UI — a uniform handle that ⌘B / ⌘. shortcuts can target.

Wire format
~~~~~~~~~~~

The first SSE event is always ``event: task`` with body ``{"task_id": "..."}``.
The rest of the stream carries ``message`` and ``done`` events exactly as
before. Cancellation surfaces as ``event: cancelled`` with a structured reason
body. The placement of ``task`` as the first event means a client that does
not understand it simply skips an unknown event; the existing token-streaming
contract is unchanged.

Cancellation cadence
~~~~~~~~~~~~~~~~~~~~

The streaming generator checks ``task_record.cancellation_requested`` between
LLM token yields. Every 32 tokens is the chosen cadence: frequent enough that
``⌘.`` feels instantaneous, infrequent enough that the check itself is not a
perf hit relative to the LLM's own token cost. Yields are also bounded by an
``asyncio.shield`` so the underlying backend.stream() call does not race the
cancellation observer.

Terminal states
~~~~~~~~~~~~~~~

The task record's terminal state reflects what the user actually saw:

* ``succeeded`` — the stream emitted every token and the upstream backend
  closed the iterator normally.
* ``cancelled`` — the user (or the API) requested cancellation mid-stream;
  the substrate appends a ``cancelled`` line and the stream ends with a
  ``cancelled`` SSE event.
* ``failed`` — the backend raised mid-stream; the substrate captures the
  exception in ``error_summary`` and the stream ends with an ``error`` event.
"""

import asyncio
import json
import logging
import os
import sys
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

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
from synthesis_engine.tasks import (
    BackgroundTaskManager,
    TaskCancelled,
    TaskRecord,
    TaskState,
    default_manager,
    get_default_manager,
)

from ..dependencies import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger("api.routers.chat")


# Cancellation-check cadence: a stream observes the cancellation_requested
# flag every CANCEL_CHECK_EVERY tokens. Frequent enough that ⌘. feels
# responsive (typical model emits ~50 tokens/sec, so the check fires roughly
# every 0.6s), sparse enough that the per-yield branch is amortised.
CANCEL_CHECK_EVERY = 32


def _require_task_manager() -> BackgroundTaskManager:
    """Resolve the process-wide :class:`BackgroundTaskManager`.

    Falls back to lazy-construction so a curl against the chat endpoint on
    a fresh install still works; the lifespan handler wires the same
    singleton at startup so production paths reuse it.
    """

    manager = get_default_manager()
    if manager is None:
        manager = default_manager()
    return manager


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


async def _drive_chat_stream(
    request: ChatRequest,
    task_record: TaskRecord,
    chunk_queue: "asyncio.Queue[Optional[str]]",
    error_box: dict,
) -> None:
    """Drive ``chat_stream`` to completion on a worker task.

    The synchronous ``chat_stream`` iterator runs in a worker thread so the
    SSE event loop stays responsive. Each chunk lands on ``chunk_queue``;
    a sentinel ``None`` signals end-of-stream. Cancellation requests are
    surfaced by raising :class:`TaskCancelled` once the worker observes the
    flag.

    The worker periodically checks ``task_record.cancellation_requested``;
    if it flips, the worker stops draining the upstream iterator, raises
    :class:`TaskCancelled`, and the substrate records the ``cancelled``
    terminal state.
    """

    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in request.history
    ]
    workspace_dir_name = _get_workspace_dir_name(request.workspace)

    def _run_blocking_stream() -> str:
        """Synchronous pump: call ``chat_stream`` and feed the queue.

        Returns a short summary of what was produced so the manager's
        ``result_summary`` is informative. Raises :class:`TaskCancelled`
        when the user-facing cancellation flag flips.
        """

        token_count = 0
        bytes_emitted = 0
        try:
            for chunk in chat_stream(
                request.prompt,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                history=history,
                workspace_name=workspace_dir_name,
                use_rag=request.use_rag,
                rag_max_tokens=request.rag_max_tokens,
                thinking_effort=request.thinking_effort,
                additional_workspaces=request.additional_workspaces,
            ):
                token_count += 1
                bytes_emitted += len(chunk)
                # Cooperative cancellation. The substrate's contract is
                # check-then-raise; the manager translates the exception
                # into the ``cancelled`` terminal state.
                if (
                    token_count % CANCEL_CHECK_EVERY == 0
                    and task_record.cancellation_requested
                ):
                    raise TaskCancelled(
                        f"cancelled after {token_count} chunks"
                    )
                # Hand the chunk to the SSE producer via the queue.
                # ``put_nowait`` is safe because the queue is unbounded.
                chunk_queue.put_nowait(chunk)
            return f"emitted {token_count} chunks ({bytes_emitted} bytes)"
        finally:
            # Sentinel that signals end-of-stream regardless of whether
            # the iterator exited normally or via cancellation/error.
            chunk_queue.put_nowait(None)

    try:
        summary = await asyncio.to_thread(_run_blocking_stream)
        return summary
    except TaskCancelled:
        # Re-raise so the manager records the cancelled terminal state.
        raise
    except Exception as exc:  # noqa: BLE001 — surfaced via task record
        error_box["error"] = exc
        # Re-raise so the manager records the failed terminal state.
        raise


async def generate_chat_stream(
    request: ChatRequest,
) -> AsyncIterator[dict]:
    """Generate SSE events for streaming chat response.

    Registers the stream as a BackgroundTask BEFORE emitting any event, so
    the very first SSE event the client receives is ``event: task`` with
    the task_id. The web UI reads this event to populate its
    ``currentTaskIdRef``; from that moment forward ⌘B / ⌘. have a real
    target.

    LLM-specific instructions are automatically loaded by core.py based on
    the model being used.
    """

    manager = _require_task_manager()
    chunk_queue: "asyncio.Queue[Optional[str]]" = asyncio.Queue()
    error_box: dict = {}

    # The manager calls the factory with the live task record; we close
    # over the queue + error_box from the enclosing scope.
    async def _coro_factory(record: TaskRecord) -> str:
        summary = await _drive_chat_stream(request, record, chunk_queue, error_box)
        return summary

    handle = manager.start_task(
        name="chat_stream",
        coro_factory=_coro_factory,
        metadata={
            "workspace": request.workspace,
            "model": request.model,
            "stream": True,
        },
    )
    task_id = handle.task_id

    # First event: announce the task id. This MUST land before any
    # ``message`` event so the client populates its task ref before
    # streaming starts.
    yield {
        "event": "task",
        "data": json.dumps({"task_id": task_id}),
    }

    cancelled_yielded = False
    try:
        while True:
            chunk = await chunk_queue.get()
            if chunk is None:
                break
            yield {
                "event": "message",
                "data": json.dumps({"content": chunk}),
            }

        # Drain side-effects: await the underlying task so we observe
        # the terminal state recorded by the manager.
        final_record = await handle.await_result()

        if final_record.state == TaskState.CANCELLED:
            cancelled_yielded = True
            yield {
                "event": "cancelled",
                "data": json.dumps(
                    {
                        "task_id": task_id,
                        "reason": final_record.error_summary or "cancelled",
                    },
                ),
            }
        elif final_record.state == TaskState.FAILED:
            exc = error_box.get("error")
            err_text = str(exc) if exc is not None else (
                final_record.error_summary or "chat stream failed"
            )
            yield {
                "event": "error",
                "data": json.dumps({"task_id": task_id, "error": err_text}),
            }
        else:
            yield {
                "event": "done",
                "data": json.dumps(
                    {"task_id": task_id, "status": "complete"},
                ),
            }
    except asyncio.CancelledError:
        # The HTTP client disconnected; flip the substrate-level cancel
        # so the worker thread exits at the next cancellation check.
        manager.cancel_task(task_id, reason="client_disconnect")
        raise


@router.post("", response_model=None)
async def chat_endpoint(request: ChatRequest):
    """Send a chat message and receive a response.

    LLM-specific instructions are automatically loaded based on the model:
    - Claude models use claude.md
    - GPT/o1/o3 models use chatgpt.md
    - Gemini models use gemini.md

    If stream=True (default), returns Server-Sent Events. The first event
    is ``task`` with the task id; subsequent events carry tokens; the
    final event is ``done``, ``cancelled``, or ``error``.

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
            thinking_effort=request.thinking_effort,
            additional_workspaces=request.additional_workspaces,
        )

        return ChatResponse(
            response=response_text,
            model=request.model,
            workspace=request.workspace,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
