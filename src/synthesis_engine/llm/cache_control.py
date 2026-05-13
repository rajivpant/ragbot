"""Anthropic prompt-cache discipline.

This module transparently rewrites outgoing LLM requests to apply Anthropic's
``cache_control`` annotations on the system prompt and on large reusable
context blocks (RAG-retrieved chunks above a configurable threshold). The
rewrite is provider-conditional — it only triggers for Anthropic models —
and idempotent: a request that already carries cache_control markers
passes through unchanged.

Anthropic's cache hit rate appears in the response metadata under
``usage.cache_read_input_tokens`` and ``usage.cache_creation_input_tokens``;
the substrate observability layer reads those off the response and emits
them as both span attributes and metric values (see
``synthesis_engine.observability.instrumentation.record_llm_response``).

References:
    https://platform.claude.com/docs/en/build-with-claude/prompt-caching

Configuration:
    cache_control_enabled (bool, default True)
        Master switch. Set False per-call (via LLMRequest.extra) to disable
        cache_control for debugging.
    cache_min_block_tokens (int, default 1024)
        Minimum estimated token length for a reusable context block to be
        eligible for cache_control. Below this threshold, blocks fall
        below the Anthropic cache-block size minimum and the annotation
        is a no-op (or worse, churns the cache write counter).
    cache_ttl (str, default "5m")
        Cache TTL. Anthropic supports "5m" and "1h" (the latter at 2x the
        write cost). The substrate defaults to 5m which fits the typical
        chat-turn cadence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Anthropic cache_control requires a minimum block size for caching to be
# worth the overhead. The provider rejects blocks smaller than the model's
# minimum cacheable size with a no-op effect; we apply a configurable
# guard upstream so we don't waste API requests writing to the cache for
# tiny blocks.
DEFAULT_MIN_BLOCK_TOKENS = 1024

# A pragmatic character → token estimate (~4 chars/token for English).
# This is intentionally a rough estimate so we don't pull in tiktoken for
# every request; the threshold is approximate by design.
_CHARS_PER_TOKEN = 4

DEFAULT_TTL = "5m"


@dataclass
class CacheConfig:
    """Per-call configuration for cache_control application."""

    enabled: bool = True
    min_block_tokens: int = DEFAULT_MIN_BLOCK_TOKENS
    ttl: str = DEFAULT_TTL

    @classmethod
    def from_extra(cls, extra: Optional[Dict[str, Any]]) -> "CacheConfig":
        """Build from the ``extra`` field of LLMRequest."""

        if not extra:
            return cls()
        return cls(
            enabled=bool(extra.get("cache_control_enabled", True)),
            min_block_tokens=int(
                extra.get("cache_min_block_tokens", DEFAULT_MIN_BLOCK_TOKENS),
            ),
            ttl=str(extra.get("cache_ttl", DEFAULT_TTL)),
        )


# ---------------------------------------------------------------------------
# Public predicates
# ---------------------------------------------------------------------------


def is_anthropic_model(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith("anthropic/") or "claude" in m


def is_eligible_for_cache(model: str, cfg: CacheConfig) -> bool:
    """Decide whether the request is a candidate for cache_control."""

    return cfg.enabled and is_anthropic_model(model)


# ---------------------------------------------------------------------------
# System-prompt rewrite (LiteLLM / messages-API shape)
#
# LiteLLM passes Anthropic messages through under the OpenAI-compatible
# shape with "messages" containing role/content. To apply cache_control on
# the system prompt under this shape, we rewrite the system message
# content from a plain string into a list of content blocks, each block
# having a cache_control annotation. LiteLLM then translates this into
# Anthropic's messages-API system prompt array correctly.
# ---------------------------------------------------------------------------


def apply_cache_control_to_messages(
    messages: List[Dict[str, Any]],
    cfg: CacheConfig,
    *,
    long_context_threshold_chars: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Rewrite the messages array with cache_control annotations.

    Strategy:

      1. The first system message is wrapped as a single text block with
         cache_control. Subsequent system messages are folded into the
         same block (Anthropic supports multiple system blocks but
         consolidating simplifies the cache boundary).

      2. The last user message is unchanged.

      3. Any user message whose content is longer than
         ``long_context_threshold_chars`` (default = min_block_tokens *
         CHARS_PER_TOKEN) is rewritten with a cache_control block on its
         content. This catches RAG-retrieved context blocks that the
         caller passes inline.

    Returns
    -------
    (rewritten_messages, stats)
        stats includes:
          system_cache_applied: bool
          context_blocks_cached: int
          system_block_estimated_tokens: int
    """

    threshold = (
        long_context_threshold_chars
        if long_context_threshold_chars is not None
        else cfg.min_block_tokens * _CHARS_PER_TOKEN
    )

    rewritten: List[Dict[str, Any]] = []
    stats = {
        "system_cache_applied": False,
        "context_blocks_cached": 0,
        "system_block_estimated_tokens": 0,
    }

    # Coalesce all system messages into one cache_control block so the
    # cache prefix is well-defined.
    system_parts: List[str] = []
    consumed_system = False
    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            if isinstance(content, list):
                # Already structured. Pass through unchanged.
                rewritten.append(m)
                consumed_system = True
                continue
            system_parts.append(str(content))

    if system_parts:
        system_text = "\n\n".join(system_parts)
        system_block = _system_block_with_cache(system_text, cfg)
        rewritten.append(system_block)
        stats["system_cache_applied"] = True
        stats["system_block_estimated_tokens"] = _estimate_tokens(system_text)
        consumed_system = True

    for m in messages:
        if m.get("role") == "system":
            # Already consumed during the system coalescing pass above.
            continue
        content = m.get("content", "")
        if isinstance(content, str) and len(content) >= threshold:
            # Long enough to be a cache-eligible context block.
            rewritten.append({
                "role": m["role"],
                "content": [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": _cache_control_marker(cfg),
                    },
                ],
            })
            stats["context_blocks_cached"] += 1
        else:
            rewritten.append(m)

    return rewritten, stats


# ---------------------------------------------------------------------------
# System-prompt rewrite (Anthropic direct SDK shape)
#
# The Anthropic direct SDK splits ``system`` out of ``messages``. The
# system can be a plain string OR a list of content blocks; only the
# latter supports cache_control. We always promote to the list form
# when caching is requested.
# ---------------------------------------------------------------------------


def apply_cache_control_to_anthropic_system(
    system: Optional[str],
    messages: List[Dict[str, Any]],
    cfg: CacheConfig,
    *,
    long_context_threshold_chars: Optional[int] = None,
) -> Tuple[Any, List[Dict[str, Any]], Dict[str, Any]]:
    """Build the cache_control-annotated system + messages for the
    direct Anthropic SDK.

    Returns
    -------
    (system, messages, stats)
        ``system`` becomes a list[block] when caching is applied (or stays
        None / str if the input was empty / caching not requested).
        ``messages`` matches the caller's structure with cache_control
        applied to long user-content blocks.
    """

    threshold = (
        long_context_threshold_chars
        if long_context_threshold_chars is not None
        else cfg.min_block_tokens * _CHARS_PER_TOKEN
    )

    stats = {
        "system_cache_applied": False,
        "context_blocks_cached": 0,
        "system_block_estimated_tokens": 0,
    }

    new_system: Any = system
    if isinstance(system, str) and system.strip():
        new_system = [
            {
                "type": "text",
                "text": system,
                "cache_control": _cache_control_marker(cfg),
            },
        ]
        stats["system_cache_applied"] = True
        stats["system_block_estimated_tokens"] = _estimate_tokens(system)

    new_messages: List[Dict[str, Any]] = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str) and len(content) >= threshold:
            new_messages.append({
                "role": m["role"],
                "content": [
                    {
                        "type": "text",
                        "text": content,
                        "cache_control": _cache_control_marker(cfg),
                    },
                ],
            })
            stats["context_blocks_cached"] += 1
        else:
            new_messages.append(m)
    return new_system, new_messages, stats


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _system_block_with_cache(text: str, cfg: CacheConfig) -> Dict[str, Any]:
    """Build a litellm/anthropic-style system message with cache_control."""

    return {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": text,
                "cache_control": _cache_control_marker(cfg),
            },
        ],
    }


def _cache_control_marker(cfg: CacheConfig) -> Dict[str, str]:
    marker: Dict[str, str] = {"type": "ephemeral"}
    if cfg.ttl and cfg.ttl != DEFAULT_TTL:
        # Anthropic's 1h TTL is opt-in. The 5m default does not need a TTL key.
        marker["ttl"] = cfg.ttl
    return marker


def _estimate_tokens(text: str) -> int:
    """Cheap character → token estimate."""

    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


# ---------------------------------------------------------------------------
# Response cache-metadata extraction
# ---------------------------------------------------------------------------


@dataclass
class CacheMetadata:
    """Extracted cache accounting from an Anthropic / LiteLLM response."""

    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    uncached_input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_input_tokens(self) -> int:
        return (
            self.cache_read_input_tokens
            + self.cache_creation_input_tokens
            + self.uncached_input_tokens
        )

    @property
    def hit_ratio(self) -> float:
        total = self.total_input_tokens
        return (self.cache_read_input_tokens / total) if total else 0.0


def extract_cache_metadata(response_usage: Any) -> CacheMetadata:
    """Read cache accounting off an Anthropic / LiteLLM usage object.

    Anthropic puts the cache counters under ``usage.cache_read_input_tokens``
    and ``usage.cache_creation_input_tokens``. LiteLLM normalises these
    onto the usage payload as well (or under ``_response_ms`` metadata in
    older versions — both are handled).
    """

    meta = CacheMetadata()
    if response_usage is None:
        return meta

    def _get(key: str) -> int:
        # Object form (Anthropic SDK), dict form (LiteLLM).
        val = getattr(response_usage, key, None)
        if val is None and isinstance(response_usage, dict):
            val = response_usage.get(key)
        return int(val or 0)

    # Anthropic's *uncached* input tokens appear under input_tokens. LiteLLM
    # maps this onto prompt_tokens — read both.
    meta.uncached_input_tokens = max(
        _get("input_tokens"),
        _get("prompt_tokens"),
    )
    meta.cache_read_input_tokens = _get("cache_read_input_tokens")
    meta.cache_creation_input_tokens = _get("cache_creation_input_tokens")
    meta.output_tokens = max(
        _get("output_tokens"),
        _get("completion_tokens"),
    )
    return meta


__all__ = [
    "CacheConfig",
    "CacheMetadata",
    "DEFAULT_MIN_BLOCK_TOKENS",
    "DEFAULT_TTL",
    "apply_cache_control_to_anthropic_system",
    "apply_cache_control_to_messages",
    "extract_cache_metadata",
    "is_anthropic_model",
    "is_eligible_for_cache",
]
