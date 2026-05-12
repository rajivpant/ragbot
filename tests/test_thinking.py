"""Tests for the LiteLLM thinking / reasoning_effort wiring (loose end)."""

from __future__ import annotations

import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from ragbot.core import _resolve_thinking_for_model, _normalise_effort  # noqa: E402


class TestNormaliseEffort:
    @pytest.mark.parametrize("raw,expected", [
        ("high", "high"),
        ("HIGH", "high"),
        (" medium ", "medium"),
        ("low", "low"),
        ("minimal", "minimal"),
        ("off", "off"),
        ("auto", "auto"),
        ("default", "auto"),
        ("nope", None),
        (None, None),
        ("", None),
    ])
    def test_normalise(self, raw, expected):
        assert _normalise_effort(raw) == expected


class TestResolveThinkingForModel:
    """Behavioural rules:

    * Flagship model with thinking metadata → default ``medium``.
    * Non-flagship model with thinking metadata:
        - if engines.yaml declares a discrete ``modes:`` list and ``off`` is
          NOT among them (OpenAI / Gemini style, where reasoning is always
          on), default to the LOWEST listed mode (typically ``minimal``) so
          the provider's own reasoning default doesn't consume the entire
          output budget on long-context calls.
        - otherwise (Claude with ``mode: adaptive`` or no modes listed) →
          default to ``off`` (send no thinking params; provider's neutral
          default applies).
    * Model without thinking metadata → never pass thinking params.
    * Explicit override (per-call) wins over both env and engines.yaml default.
    * Env-var override wins over engines.yaml default but loses to per-call.
    """

    def test_flagship_claude_4_7_uses_adaptive_thinking_shape(self, monkeypatch):
        # Claude 4.7+ requires the new ``thinking.type.adaptive`` shape;
        # LiteLLM's reasoning_effort mapper still emits the older
        # ``thinking.type.enabled`` form which the API rejects.
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("anthropic/claude-opus-4-7")
        assert out == {"thinking": {"type": "adaptive"}, "temperature": 1.0}

    def test_non_flagship_with_thinking_defaults_to_off(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("anthropic/claude-sonnet-4-6")
        assert out == {}

    def test_model_without_thinking_metadata_returns_empty(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("anthropic/claude-haiku-4-5-20251001")
        assert out == {}

    def test_per_call_override_for_claude_4_6_uses_reasoning_effort_with_temp_override(self, monkeypatch):
        # Pre-4.7 Claude still supports reasoning_effort via LiteLLM's mapper,
        # but extended thinking on Anthropic requires temperature=1.
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("anthropic/claude-sonnet-4-6", requested_effort="high")
        assert out == {"reasoning_effort": "high", "temperature": 1.0}

    def test_per_call_off_disables_flagship_default(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("anthropic/claude-opus-4-7", requested_effort="off")
        assert out == {}

    def test_env_var_overrides_engines_yaml_default(self, monkeypatch):
        # Sonnet defaults to off; env says low.
        monkeypatch.setenv("RAGBOT_THINKING_EFFORT", "low")
        out = _resolve_thinking_for_model("anthropic/claude-sonnet-4-6")
        assert out == {"reasoning_effort": "low", "temperature": 1.0}

    def test_per_call_override_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("RAGBOT_THINKING_EFFORT", "high")
        out = _resolve_thinking_for_model("anthropic/claude-sonnet-4-6", requested_effort="low")
        assert out == {"reasoning_effort": "low", "temperature": 1.0}

    def test_models_without_thinking_metadata_ignore_overrides(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        # Haiku has no thinking block — even an explicit high should be silent.
        out = _resolve_thinking_for_model(
            "anthropic/claude-haiku-4-5-20251001",
            requested_effort="high",
        )
        assert out == {}

    def test_unknown_effort_value_falls_through_to_engines_default(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model(
            "anthropic/claude-opus-4-7",
            requested_effort="ridiculous",
        )
        # Falls back to engines.yaml default (flagship → adaptive thinking shape).
        assert out == {"thinking": {"type": "adaptive"}, "temperature": 1.0}

    def test_gemini_flagship_defaults_to_medium(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("gemini/gemini-3.1-pro-preview")
        # Non-Anthropic provider — no temperature override needed.
        assert out == {"reasoning_effort": "medium"}

    def test_openai_flagship_defaults_to_medium(self, monkeypatch):
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("openai/gpt-5.5-pro")
        assert out == {"reasoning_effort": "medium"}

    def test_openai_non_flagship_defaults_to_minimal(self, monkeypatch):
        """GPT-5.5 (non-flagship, `modes: [minimal, low, medium, high]`,
        no `off`) should default to the lowest listed mode so the provider's
        own reasoning default doesn't consume the output-token budget on
        long-context calls."""
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("openai/gpt-5.5")
        assert out == {"reasoning_effort": "minimal"}

    def test_gemini_non_flagship_defaults_to_minimal(self, monkeypatch):
        """Gemini 3 Flash (non-flagship, same `modes:` shape as GPT-5.5)
        gets the same lowest-mode default treatment."""
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("gemini/gemini-3-flash-preview")
        assert out == {"reasoning_effort": "minimal"}

    def test_per_call_off_still_disables_non_flagship_with_modes(self, monkeypatch):
        """User can still pick ``off`` explicitly on a non-flagship GPT/Gemini
        model — the per-call override beats the engines.yaml default policy."""
        monkeypatch.delenv("RAGBOT_THINKING_EFFORT", raising=False)
        out = _resolve_thinking_for_model("openai/gpt-5.5", requested_effort="off")
        assert out == {}
