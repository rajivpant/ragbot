"""LiteLLM backend (default).

Wraps :func:`litellm.completion`. Provides:

* Provider-agnostic completion via LiteLLM's OpenAI-compatible API.
* Handles the GPT-5.x ``max_completion_tokens`` parameter rename.
* Honours the Anthropic constraint that extended thinking requires
  ``temperature=1``.
* Routes Claude 4.7+ around LiteLLM's still-pre-adaptive thinking shape
  (LiteLLM <=1.83.13 emits ``thinking.type.enabled`` for newer Claude
  models, which the API now rejects). For 4.7+ we send the new
  ``thinking={"type": "adaptive"}`` directly.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from .base import LLMBackend, LLMRequest, LLMResponse, LLMUnavailableError

logger = logging.getLogger(__name__)


def _is_anthropic_model(model: str) -> bool:
    m = model.lower()
    return m.startswith("anthropic/") or "claude" in m


def _is_claude_4_7_or_newer(model: str) -> bool:
    m = model.lower()
    # Match opus-4-7, sonnet-4-7, haiku-4-7, and anything claude-x-y where x*10+y >= 47.
    # Conservative: explicit substrings for the known-good 4.7 family.
    return any(
        marker in m for marker in (
            "opus-4-7", "sonnet-4-7", "haiku-4-7", "claude-4-7",
        )
    )


def _build_completion_kwargs(req: LLMRequest) -> Dict[str, Any]:
    """Translate a generic LLMRequest into litellm.completion kwargs."""

    kwargs: Dict[str, Any] = {
        "model": req.model,
        "messages": req.messages,
        "api_key": req.api_key,
    }
    if req.temperature is not None:
        kwargs["temperature"] = req.temperature

    # GPT-5.x uses max_completion_tokens, not max_tokens.
    model_lower = req.model.lower()
    if "gpt-5" in model_lower or "gpt5" in model_lower:
        kwargs["max_completion_tokens"] = req.max_tokens
    else:
        kwargs["max_tokens"] = req.max_tokens

    # Reasoning / thinking handling.
    if req.thinking is not None:
        # Caller provided the provider-native shape; pass it through.
        kwargs["thinking"] = req.thinking
        if _is_anthropic_model(req.model):
            kwargs["temperature"] = 1.0
    elif req.reasoning_effort:
        if _is_anthropic_model(req.model) and _is_claude_4_7_or_newer(req.model):
            # LiteLLM through 1.83.13 sends the older ``thinking.type.enabled``
            # shape via reasoning_effort. Claude 4.7+ rejects that — use
            # the new adaptive shape directly.
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["temperature"] = 1.0
        else:
            kwargs["reasoning_effort"] = req.reasoning_effort
            if _is_anthropic_model(req.model):
                # Claude 4.5/4.6 with reasoning_effort still requires temp=1.
                kwargs["temperature"] = 1.0

    # Free-form passthrough (last so it can override anything above).
    if req.extra:
        kwargs.update(req.extra)

    return kwargs


class LiteLLMBackend(LLMBackend):
    backend_name = "litellm"

    def __init__(self) -> None:
        try:
            import litellm  # type: ignore
        except ImportError as exc:
            raise LLMUnavailableError(
                "litellm is not installed; pip install -r requirements.txt"
            ) from exc

        self._litellm = litellm
        # Drop unsupported params at the LiteLLM layer; we still build kwargs
        # carefully ourselves above to avoid round-tripping wrong values.
        litellm.drop_params = True

    def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs = _build_completion_kwargs(request)
        response = self._litellm.completion(**kwargs)

        # LiteLLM responses behave like dicts but expose attribute access
        # for the OpenAI-compatible nested fields. Use attribute access
        # (with dict fallback) so we work across versions.
        choices = getattr(response, "choices", None) or response.get("choices", [])
        choice = choices[0] if choices else None

        text = ""
        finish_reason = None
        if choice is not None:
            # ``choice.message.content`` (object access) is the canonical path.
            msg = getattr(choice, "message", None)
            if msg is None and isinstance(choice, dict):
                msg = choice.get("message")
            if msg is not None:
                content = getattr(msg, "content", None)
                if content is None and isinstance(msg, dict):
                    content = msg.get("content")
                text = content or ""
            finish_reason = (
                getattr(choice, "finish_reason", None)
                or (choice.get("finish_reason") if isinstance(choice, dict) else None)
            )

        usage_obj = getattr(response, "usage", None) or response.get("usage", {})
        prompt_tok = getattr(usage_obj, "prompt_tokens", None)
        if prompt_tok is None and isinstance(usage_obj, dict):
            prompt_tok = usage_obj.get("prompt_tokens")
        completion_tok = getattr(usage_obj, "completion_tokens", None)
        if completion_tok is None and isinstance(usage_obj, dict):
            completion_tok = usage_obj.get("completion_tokens")
        total_tok = getattr(usage_obj, "total_tokens", None)
        if total_tok is None and isinstance(usage_obj, dict):
            total_tok = usage_obj.get("total_tokens")

        return LLMResponse(
            text=text,
            model=getattr(response, "model", None) or response.get("model", request.model),
            backend=self.backend_name,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": int(prompt_tok or 0),
                "completion_tokens": int(completion_tok or 0),
                "total_tokens": int(total_tok or 0),
            },
        )

    def stream(
        self,
        request: LLMRequest,
        on_chunk: Callable[[str], None],
    ) -> str:
        kwargs = _build_completion_kwargs(request)
        response = self._litellm.completion(**kwargs, stream=True)
        chunks = []
        for chunk in response:
            if not chunk or not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta if chunk.choices else None
            text = getattr(delta, "content", None)
            if text:
                chunks.append(text)
                try:
                    on_chunk(text)
                except Exception as exc:  # pragma: no cover
                    logger.warning("on_chunk callback raised: %s", exc)
        return "".join(chunks)

    def healthcheck(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": self.backend_name, "ok": True}
        try:
            import litellm  # type: ignore

            ver = getattr(litellm, "__version__", None) or getattr(
                litellm, "version", None,
            )
            if ver:
                info["litellm_version"] = str(ver)
        except Exception:
            pass
        return info
