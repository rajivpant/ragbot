"""Tests for the LLM-backend abstraction (Phase 3.1)."""

from __future__ import annotations

import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from synthesis_engine.llm import (  # noqa: E402
    LLMBackend,
    LLMRequest,
    LLMResponse,
    LLMUnavailableError,
    get_llm_backend,
    reset_llm_backend,
)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


class TestLLMRequest:
    def test_defaults_are_safe(self):
        r = LLMRequest(model="anthropic/claude-sonnet-4-6", messages=[])
        assert r.temperature is None
        assert r.max_tokens == 4096
        assert r.api_key is None
        assert r.thinking is None
        assert r.reasoning_effort is None
        assert r.extra == {}


class TestLLMResponse:
    def test_response_has_expected_fields(self):
        r = LLMResponse(text="hi", model="x", backend="litellm")
        assert r.text == "hi"
        assert r.model == "x"
        assert r.backend == "litellm"
        assert r.usage == {}


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def setup_method(self):
        reset_llm_backend()

    def teardown_method(self):
        reset_llm_backend()

    def test_default_is_litellm(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_LLM_BACKEND", raising=False)
        b = get_llm_backend()
        assert isinstance(b, LLMBackend)
        assert b.backend_name == "litellm"

    def test_explicit_litellm(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_LLM_BACKEND", "litellm")
        b = get_llm_backend()
        assert b.backend_name == "litellm"

    def test_unknown_value_falls_back_to_litellm(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_LLM_BACKEND", "nonsense")
        b = get_llm_backend()
        assert b.backend_name == "litellm"

    def test_direct_backend_when_env_set(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_LLM_BACKEND", "direct")
        b = get_llm_backend()
        # If anthropic/openai/google-genai are all installed, direct backend
        # constructs cleanly. If a SDK is missing, the resolver falls back to
        # litellm. Either is acceptable; both are valid LLMBackend instances.
        assert b.backend_name in {"direct", "litellm"}

    def test_singleton_caching(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_LLM_BACKEND", raising=False)
        first = get_llm_backend()
        second = get_llm_backend()
        assert first is second

    def test_reset_clears_cache(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_LLM_BACKEND", raising=False)
        first = get_llm_backend()
        reset_llm_backend()
        second = get_llm_backend()
        assert first is not second


# ---------------------------------------------------------------------------
# LiteLLM backend kwargs builder
# ---------------------------------------------------------------------------


class TestLiteLLMKwargsBuilder:
    """Verify the request → litellm.completion kwargs translation."""

    def _build(self, **overrides):
        from synthesis_engine.llm.litellm_backend import _build_completion_kwargs
        req = LLMRequest(model="anthropic/claude-sonnet-4-6", messages=[{"role": "user", "content": "hi"}])
        for k, v in overrides.items():
            setattr(req, k, v)
        return _build_completion_kwargs(req)

    def test_max_tokens_for_non_gpt5(self):
        out = self._build(max_tokens=512)
        assert out["max_tokens"] == 512
        assert "max_completion_tokens" not in out

    def test_max_completion_tokens_for_gpt5(self):
        from synthesis_engine.llm.litellm_backend import _build_completion_kwargs
        req = LLMRequest(model="openai/gpt-5.5", messages=[], max_tokens=512)
        out = _build_completion_kwargs(req)
        assert out["max_completion_tokens"] == 512
        assert "max_tokens" not in out

    def test_anthropic_with_reasoning_effort_forces_temperature_one(self):
        out = self._build(reasoning_effort="medium")
        assert out["reasoning_effort"] == "medium"
        assert out["temperature"] == 1.0

    def test_claude_4_7_uses_adaptive_thinking_shape(self):
        from synthesis_engine.llm.litellm_backend import _build_completion_kwargs
        req = LLMRequest(
            model="anthropic/claude-opus-4-7",
            messages=[],
            reasoning_effort="high",
        )
        out = _build_completion_kwargs(req)
        # 4.7+ skips reasoning_effort and sends adaptive thinking directly.
        assert out["thinking"] == {"type": "adaptive"}
        assert out["temperature"] == 1.0
        assert "reasoning_effort" not in out

    def test_explicit_thinking_passes_through(self):
        out = self._build(thinking={"type": "adaptive", "budget_tokens": 8000})
        assert out["thinking"] == {"type": "adaptive", "budget_tokens": 8000}
        assert out["temperature"] == 1.0  # anthropic forces temp=1

    def test_gemini_reasoning_effort_does_not_force_temperature(self):
        from synthesis_engine.llm.litellm_backend import _build_completion_kwargs
        req = LLMRequest(
            model="gemini/gemini-3.1-pro-preview",
            messages=[],
            reasoning_effort="medium",
        )
        out = _build_completion_kwargs(req)
        assert out["reasoning_effort"] == "medium"
        # Gemini doesn't share the Anthropic temp=1 rule.
        assert "temperature" not in out

    def test_extra_kwargs_pass_through_and_override(self):
        out = self._build(extra={"top_p": 0.9, "max_tokens": 999})
        assert out["top_p"] == 0.9
        # extra overrides the default-built max_tokens.
        assert out["max_tokens"] == 999


# ---------------------------------------------------------------------------
# DirectBackend healthcheck (no live calls)
# ---------------------------------------------------------------------------


class TestDirectBackendHealthcheck:
    def test_reports_provider_availability(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_LLM_BACKEND", "direct")
        reset_llm_backend()
        b = get_llm_backend()
        if b.backend_name != "direct":
            pytest.skip("DirectBackend not available; provider SDK missing.")
        h = b.healthcheck()
        assert h["backend"] == "direct"
        assert isinstance(h.get("providers"), dict)
        # At least one provider should be available in the test environment.
        assert any(p["available"] for p in h["providers"].values())
        reset_llm_backend()
