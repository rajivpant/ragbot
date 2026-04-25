"""Direct-SDK LLM backend.

Calls each provider's official SDK directly:

* Anthropic via :mod:`anthropic`
* OpenAI    via :mod:`openai`
* Google    via :mod:`google.genai`

This is an opt-in escape hatch from LiteLLM. Selection happens at the
top-level ``RAGBOT_LLM_BACKEND=direct`` env var. The module dispatches
on the provider prefix in the model id (``anthropic/...``, ``openai/...``,
``gemini/...``); models without a recognised prefix fall back to
LiteLLM via a graceful :class:`LLMUnavailableError`.

Provider-quirk handling parity with the litellm backend:

* GPT-5.x ``max_completion_tokens`` rename is honoured.
* Claude 4.7+ ``thinking={"type": "adaptive"}`` shape is sent directly.
* Anthropic + thinking → ``temperature=1`` is enforced.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from .base import LLMBackend, LLMRequest, LLMResponse, LLMUnavailableError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------


def _provider_for(model: str) -> str:
    m = model.lower()
    if m.startswith("anthropic/") or "claude" in m:
        return "anthropic"
    if m.startswith("openai/") or m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"):
        return "openai"
    if m.startswith("gemini/") or "gemini" in m:
        return "google"
    return "unknown"


def _strip_provider(model: str) -> str:
    for prefix in ("anthropic/", "openai/", "gemini/"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def _is_claude_4_7_or_newer(model: str) -> bool:
    m = model.lower()
    return any(
        marker in m for marker in (
            "opus-4-7", "sonnet-4-7", "haiku-4-7", "claude-4-7",
        )
    )


# ---------------------------------------------------------------------------
# Effort → Anthropic budget tokens (heuristic, used when caller asks for a
# specific effort level on Claude 4.7+ which only accepts adaptive mode).
# ---------------------------------------------------------------------------


_EFFORT_TO_BUDGET = {
    "minimal": 1024,
    "low": 4096,
    "medium": 16384,
    "high": 64000,
}


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class DirectBackend(LLMBackend):
    backend_name = "direct"

    def __init__(self) -> None:
        # Lazy SDK probes — we don't fail construction if one is missing,
        # only when a request actually targets that provider.
        self._anthropic_client: Optional[Any] = None
        self._openai_client: Optional[Any] = None
        self._google_client: Optional[Any] = None

    # ---- complete --------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        provider = _provider_for(request.model)
        if provider == "anthropic":
            return self._anthropic_complete(request)
        if provider == "openai":
            return self._openai_complete(request)
        if provider == "google":
            return self._google_complete(request)
        raise LLMUnavailableError(
            f"Direct backend does not recognise model provider for {request.model!r}. "
            f"Set RAGBOT_LLM_BACKEND=litellm to use the LiteLLM backend, "
            f"or extend DirectBackend with a new provider."
        )

    # ---- stream ----------------------------------------------------------

    def stream(
        self,
        request: LLMRequest,
        on_chunk: Callable[[str], None],
    ) -> str:
        provider = _provider_for(request.model)
        if provider == "anthropic":
            return self._anthropic_stream(request, on_chunk)
        if provider == "openai":
            return self._openai_stream(request, on_chunk)
        if provider == "google":
            return self._google_stream(request, on_chunk)
        raise LLMUnavailableError(
            f"Direct backend does not recognise model provider for {request.model!r}."
        )

    # ---- healthcheck ----------------------------------------------------

    def healthcheck(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": self.backend_name, "ok": True, "providers": {}}
        for name, importer in (
            ("anthropic", self._import_anthropic),
            ("openai", self._import_openai),
            ("google", self._import_google_genai),
        ):
            try:
                mod = importer()
                info["providers"][name] = {
                    "available": True,
                    "version": getattr(mod, "__version__", None),
                }
            except Exception as exc:  # noqa: BLE001
                info["providers"][name] = {"available": False, "reason": str(exc)}
                info["ok"] = info["ok"] and False
        # Direct backend is "ok" if at least one provider is available.
        info["ok"] = any(p["available"] for p in info["providers"].values())
        return info

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _import_anthropic(self):
        import anthropic  # type: ignore
        return anthropic

    def _get_anthropic_client(self, api_key: Optional[str]):
        anthropic = self._import_anthropic()
        # Always rebuild when api_key is provided (test isolation, multi-key).
        if api_key:
            return anthropic.Anthropic(api_key=api_key)
        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic()
        return self._anthropic_client

    def _build_anthropic_kwargs(self, request: LLMRequest) -> Dict[str, Any]:
        # Anthropic's messages API splits system out of messages.
        system = ""
        messages = []
        for m in request.messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system = (system + "\n" + content).strip() if system else content
            else:
                messages.append({"role": role, "content": content})

        kwargs: Dict[str, Any] = {
            "model": _strip_provider(request.model),
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if system:
            kwargs["system"] = system

        thinking = request.thinking
        if thinking is None and request.reasoning_effort:
            if _is_claude_4_7_or_newer(request.model):
                budget = _EFFORT_TO_BUDGET.get(request.reasoning_effort, 16384)
                thinking = {"type": "adaptive", "budget_tokens": budget}
            else:
                # Older claude — still uses enabled shape.
                budget = _EFFORT_TO_BUDGET.get(request.reasoning_effort, 16384)
                thinking = {"type": "enabled", "budget_tokens": budget}

        if thinking is not None:
            kwargs["thinking"] = thinking
            kwargs["temperature"] = 1.0
        elif request.temperature is not None:
            kwargs["temperature"] = request.temperature

        if request.extra:
            kwargs.update(request.extra)
        return kwargs

    def _anthropic_complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_anthropic_client(request.api_key)
        kwargs = self._build_anthropic_kwargs(request)
        msg = client.messages.create(**kwargs)
        # `msg.content` is a list of content blocks; concatenate the text ones.
        parts = []
        for block in getattr(msg, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        usage = getattr(msg, "usage", None)
        return LLMResponse(
            text="".join(parts),
            model=getattr(msg, "model", request.model),
            backend=self.backend_name,
            finish_reason=getattr(msg, "stop_reason", None),
            usage={
                "prompt_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "output_tokens", 0) or 0),
                "total_tokens": int(
                    (getattr(usage, "input_tokens", 0) or 0)
                    + (getattr(usage, "output_tokens", 0) or 0)
                ),
            } if usage else {},
        )

    def _anthropic_stream(
        self,
        request: LLMRequest,
        on_chunk: Callable[[str], None],
    ) -> str:
        client = self._get_anthropic_client(request.api_key)
        kwargs = self._build_anthropic_kwargs(request)
        chunks = []
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if not text:
                    continue
                chunks.append(text)
                try:
                    on_chunk(text)
                except Exception as exc:  # pragma: no cover
                    logger.warning("on_chunk raised: %s", exc)
        return "".join(chunks)

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    def _import_openai(self):
        import openai  # type: ignore
        return openai

    def _get_openai_client(self, api_key: Optional[str]):
        openai = self._import_openai()
        if api_key:
            return openai.OpenAI(api_key=api_key)
        if self._openai_client is None:
            self._openai_client = openai.OpenAI()
        return self._openai_client

    def _build_openai_kwargs(self, request: LLMRequest) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": _strip_provider(request.model),
            "messages": request.messages,
        }
        # GPT-5.x uses max_completion_tokens.
        model_lower = request.model.lower()
        if "gpt-5" in model_lower or "gpt5" in model_lower:
            kwargs["max_completion_tokens"] = request.max_tokens
        else:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.reasoning_effort:
            kwargs["reasoning_effort"] = request.reasoning_effort
        if request.extra:
            kwargs.update(request.extra)
        return kwargs

    def _openai_complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_openai_client(request.api_key)
        kwargs = self._build_openai_kwargs(request)
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0] if resp.choices else None
        text = choice.message.content if choice and choice.message else ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text or "",
            model=getattr(resp, "model", request.model),
            backend=self.backend_name,
            finish_reason=getattr(choice, "finish_reason", None) if choice else None,
            usage={
                "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            } if usage else {},
        )

    def _openai_stream(
        self,
        request: LLMRequest,
        on_chunk: Callable[[str], None],
    ) -> str:
        client = self._get_openai_client(request.api_key)
        kwargs = self._build_openai_kwargs(request)
        chunks = []
        for chunk in client.chat.completions.create(**kwargs, stream=True):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                chunks.append(text)
                try:
                    on_chunk(text)
                except Exception as exc:  # pragma: no cover
                    logger.warning("on_chunk raised: %s", exc)
        return "".join(chunks)

    # ------------------------------------------------------------------
    # Google (google-genai)
    # ------------------------------------------------------------------

    def _import_google_genai(self):
        from google import genai as google_genai  # type: ignore
        return google_genai

    def _get_google_client(self, api_key: Optional[str]):
        google_genai = self._import_google_genai()
        if api_key:
            return google_genai.Client(api_key=api_key)
        if self._google_client is None:
            self._google_client = google_genai.Client()
        return self._google_client

    def _build_google_request(self, request: LLMRequest):
        google_genai = self._import_google_genai()
        # Concatenate non-system messages into a single contents list,
        # per google-genai's chat-style usage. System messages become
        # config.system_instruction.
        contents = []
        system_instruction = None
        for m in request.messages:
            if m.get("role") == "system":
                system_instruction = (
                    (system_instruction + "\n" + m["content"]).strip()
                    if system_instruction
                    else m["content"]
                )
            else:
                contents.append(m.get("content", ""))

        # google-genai 1.x: pass config via types.GenerateContentConfig.
        try:
            from google.genai import types  # type: ignore
            config_kwargs: Dict[str, Any] = {}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if request.temperature is not None:
                config_kwargs["temperature"] = request.temperature
            if request.max_tokens:
                config_kwargs["max_output_tokens"] = request.max_tokens
            if request.reasoning_effort:
                # Map effort to ThinkingConfig.thinking_budget if SDK supports it.
                budget = _EFFORT_TO_BUDGET.get(request.reasoning_effort)
                if budget and hasattr(types, "ThinkingConfig"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=budget,
                    )
            config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        except ImportError:
            config = None

        return _strip_provider(request.model), "\n\n".join(contents) or "", config

    def _google_complete(self, request: LLMRequest) -> LLMResponse:
        client = self._get_google_client(request.api_key)
        model_id, contents, config = self._build_google_request(request)
        kwargs: Dict[str, Any] = {"model": model_id, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        resp = client.models.generate_content(**kwargs)
        return LLMResponse(
            text=resp.text or "",
            model=model_id,
            backend=self.backend_name,
        )

    def _google_stream(
        self,
        request: LLMRequest,
        on_chunk: Callable[[str], None],
    ) -> str:
        client = self._get_google_client(request.api_key)
        model_id, contents, config = self._build_google_request(request)
        kwargs: Dict[str, Any] = {"model": model_id, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        chunks = []
        for chunk in client.models.generate_content_stream(**kwargs):
            text = getattr(chunk, "text", None)
            if text:
                chunks.append(text)
                try:
                    on_chunk(text)
                except Exception as exc:  # pragma: no cover
                    logger.warning("on_chunk raised: %s", exc)
        return "".join(chunks)
