"""LLM-backend abstraction for Ragbot.

Two backends ship:

    - litellm  — default. Wraps :mod:`litellm`. Best provider/model coverage,
                 handles the long tail of provider quirks. Pinned >=1.83.0
                 (post-March-2026 supply-chain incident) in requirements.txt.
    - direct   — opt-in. Calls each provider's official SDK directly
                 (anthropic, openai, google-genai). Smaller surface area,
                 shorter dependency chain, no third-party gateway. Useful for
                 users who want to retire LiteLLM, or for benchmarking.

Selection via the ``RAGBOT_LLM_BACKEND`` env var (default: ``litellm``).
The interface is provider-agnostic: a single :class:`LLMBackend` ABC with
``complete()``, ``stream()``, and ``healthcheck()`` methods that exchange
``LLMRequest`` and ``LLMResponse`` dataclasses.

Adding a new backend (e.g., Bifrost, Portkey, OpenRouter) is a single new
file implementing :class:`LLMBackend`, plus one selection arm in
``get_llm_backend()`` below.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .base import (
    LLMBackend,
    LLMRequest,
    LLMResponse,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)


_BACKEND: Optional[LLMBackend] = None


def _resolve_backend_name() -> str:
    name = os.environ.get("RAGBOT_LLM_BACKEND", "litellm").strip().lower()
    if name not in ("litellm", "direct"):
        logger.warning(
            "Unknown RAGBOT_LLM_BACKEND=%r, falling back to litellm.", name,
        )
        return "litellm"
    return name


def get_llm_backend(refresh: bool = False) -> LLMBackend:
    """Return the configured LLM backend (cached singleton).

    When ``refresh`` is True, the cache is dropped and the backend is
    rebuilt — useful for tests that swap env vars.
    """

    global _BACKEND
    if _BACKEND is not None and not refresh:
        return _BACKEND

    name = _resolve_backend_name()
    if name == "direct":
        try:
            from .direct_backend import DirectBackend  # noqa: WPS433
            _BACKEND = DirectBackend()
            return _BACKEND
        except Exception as exc:  # pragma: no cover - construction failure path
            logger.warning(
                "Direct backend unavailable (%s); falling back to litellm.", exc,
            )

    from .litellm_backend import LiteLLMBackend  # noqa: WPS433
    _BACKEND = LiteLLMBackend()
    return _BACKEND


def reset_llm_backend() -> None:
    """Drop the cached backend (test hook)."""

    global _BACKEND
    _BACKEND = None


__all__ = [
    "LLMBackend",
    "LLMRequest",
    "LLMResponse",
    "LLMUnavailableError",
    "get_llm_backend",
    "reset_llm_backend",
]
