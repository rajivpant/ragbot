"""Metric registry for synthesis_engine.

Two-layer design:

1. **OpenTelemetry metrics**: counters and histograms registered against
   the global :class:`MeterProvider`. These integrate cleanly with any
   OTLP-compatible backend (Datadog, Honeycomb, Phoenix, Langfuse) when
   ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.

2. **Prometheus exposition bridge**: a ``prometheus_client`` registry
   is maintained in parallel so :func:`render_prometheus` produces a
   valid Prometheus exposition format payload for ``GET /api/metrics``.
   This is the path that lets a CTO plug ragbot into Prometheus on day
   one without standing up a collector.

Both layers update synchronously when a recorder is called. The Prometheus
side does not depend on the OTEL Prometheus exporter package (which has
been in flux) — we maintain a tiny shim that mirrors the OTEL metrics into
``prometheus_client`` objects.

Metrics emitted (the May 2026 OTEL GenAI metrics spec where it exists,
plus synthesis-specific extensions):

  gen_ai.client.operation.duration       Histogram  s    Duration of LLM ops.
  gen_ai.client.token.usage              Histogram  {token}  Token counts.
  synthesis.llm.requests                  Counter             Request count by model.
  synthesis.llm.cache.read_input_tokens   Counter             Cumulative cache-read tokens.
  synthesis.llm.cache.creation_input_tokens Counter           Cumulative cache-creation tokens.
  synthesis.llm.cache.uncached_input_tokens Counter           Cumulative uncached input tokens.
  synthesis.tool.calls                    Counter             Tool calls by name + outcome.
  synthesis.retrieval.latency             Histogram s        Retrieval latency.
  synthesis.retrieval.result_count        Histogram          Result counts per call.
  synthesis.agent.iterations              Counter            Total agent loop iterations.
  synthesis.guardrail.outcomes            Counter            Guardrail decisions by outcome.

A rolling-window cache-hit-ratio view is maintained in process for the
``/api/metrics/cache`` shorthand endpoint — it is not an OTEL metric, it is
a derived JSON view computed on demand.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Globals + lifecycle
# ---------------------------------------------------------------------------


@dataclass
class _CacheEvent:
    """One observed LLM call's cache accounting. Recorded for rolling-window views."""

    timestamp: float
    model: str
    cache_read_tokens: int
    cache_creation_tokens: int
    uncached_input_tokens: int

    @property
    def total_input_tokens(self) -> int:
        return (
            self.cache_read_tokens
            + self.cache_creation_tokens
            + self.uncached_input_tokens
        )


@dataclass
class _MetricsState:
    """Mutable state owned by the registry. Protected by _LOCK."""

    meter: Optional[Any] = None
    instruments: Dict[str, Any] = field(default_factory=dict)
    # Prometheus parallel registry (lazy import).
    prom_registry: Optional[Any] = None
    prom_metrics: Dict[str, Any] = field(default_factory=dict)
    # Rolling cache events (bounded deque).
    cache_events: collections.deque = field(default_factory=lambda: collections.deque(maxlen=10_000))


_LOCK = threading.Lock()
_STATE = _MetricsState()
_PROMETHEUS_READER: Optional[Any] = None


# ---------------------------------------------------------------------------
# OTEL bridge: PrometheusMetricReader (in-process collection)
# ---------------------------------------------------------------------------


def _get_or_create_prometheus_reader():
    """Build the in-process metric reader used by /api/metrics scraping.

    We use the official ``opentelemetry.exporter.prometheus.PrometheusMetricReader``
    when available (it implements the OTEL MetricReader contract and
    populates ``prometheus_client.REGISTRY`` directly). When that package
    isn't installed, we fall back to a no-op reader and rely on the
    parallel Prometheus instruments below.
    """

    global _PROMETHEUS_READER
    if _PROMETHEUS_READER is not None:
        return _PROMETHEUS_READER

    try:
        from opentelemetry.exporter.prometheus import PrometheusMetricReader  # type: ignore
        _PROMETHEUS_READER = PrometheusMetricReader()
    except ImportError:
        # No OTEL→Prometheus bridge installed. Fall back to an in-memory
        # reader so the meter provider has at least one reader attached,
        # and rely on the parallel prometheus_client instruments to serve
        # render_prometheus().
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader
        _PROMETHEUS_READER = InMemoryMetricReader()
    return _PROMETHEUS_READER


# ---------------------------------------------------------------------------
# Public registry API
# ---------------------------------------------------------------------------


def get_metrics_registry() -> Dict[str, Any]:
    """Return a dict view of the active OTEL instruments.

    Used by tests to assert that instruments exist after init_tracer.
    """

    return dict(_STATE.instruments)


def get_meter_provider() -> Optional[Any]:
    from .tracer import get_meter_provider as _get

    return _get()


def cache_stats_snapshot(window_seconds: Optional[float] = None) -> Dict[str, Any]:
    """Return the rolling prompt-cache statistics.

    Parameters
    ----------
    window_seconds:
        If provided, restrict to events within the last N seconds.
        If None, all retained events (up to the deque's max).

    Returns
    -------
    dict with: window_seconds, samples, cache_read_tokens, cache_creation_tokens,
    uncached_input_tokens, total_input_tokens, hit_rate (cache_read / total),
    per_model breakdown.
    """

    now = time.time()
    cutoff = (now - window_seconds) if window_seconds is not None else 0.0

    read = creation = uncached = 0
    per_model: Dict[str, Dict[str, int]] = {}
    sample_count = 0
    with _LOCK:
        for ev in _STATE.cache_events:
            if ev.timestamp < cutoff:
                continue
            sample_count += 1
            read += ev.cache_read_tokens
            creation += ev.cache_creation_tokens
            uncached += ev.uncached_input_tokens
            m = per_model.setdefault(
                ev.model,
                {"samples": 0, "cache_read_tokens": 0,
                 "cache_creation_tokens": 0, "uncached_input_tokens": 0},
            )
            m["samples"] += 1
            m["cache_read_tokens"] += ev.cache_read_tokens
            m["cache_creation_tokens"] += ev.cache_creation_tokens
            m["uncached_input_tokens"] += ev.uncached_input_tokens

    total = read + creation + uncached
    hit_rate = (read / total) if total else 0.0
    return {
        "window_seconds": window_seconds,
        "samples": sample_count,
        "cache_read_tokens": read,
        "cache_creation_tokens": creation,
        "uncached_input_tokens": uncached,
        "total_input_tokens": total,
        "hit_rate": hit_rate,
        "per_model": per_model,
    }


# ---------------------------------------------------------------------------
# Internal: meter binding (called by tracer.init_tracer)
# ---------------------------------------------------------------------------


def _bind_meter_provider(meter_provider) -> None:
    """Create all instruments against the new meter provider."""

    global _STATE

    with _LOCK:
        meter = meter_provider.get_meter("synthesis_engine.observability", "0.1.0")
        _STATE.meter = meter

        # ---- Standard GenAI metrics (OTEL spec) ----------------------------
        _STATE.instruments["llm_operation_duration"] = meter.create_histogram(
            name="gen_ai.client.operation.duration",
            unit="s",
            description="Overall duration of GenAI client operations (chat, embeddings, etc.).",
        )
        _STATE.instruments["llm_token_usage"] = meter.create_histogram(
            name="gen_ai.client.token.usage",
            unit="{token}",
            description="Token usage per GenAI request (input + output).",
        )

        # ---- Synthesis-specific metrics ------------------------------------
        _STATE.instruments["llm_requests"] = meter.create_counter(
            name="synthesis.llm.requests",
            unit="{request}",
            description="Count of LLM requests by model/provider/operation.",
        )
        _STATE.instruments["cache_read_input_tokens"] = meter.create_counter(
            name="synthesis.llm.cache.read_input_tokens",
            unit="{token}",
            description="Cumulative input tokens served from the prompt cache.",
        )
        _STATE.instruments["cache_creation_input_tokens"] = meter.create_counter(
            name="synthesis.llm.cache.creation_input_tokens",
            unit="{token}",
            description="Cumulative input tokens written to the prompt cache.",
        )
        _STATE.instruments["cache_uncached_input_tokens"] = meter.create_counter(
            name="synthesis.llm.cache.uncached_input_tokens",
            unit="{token}",
            description="Cumulative input tokens that bypassed the prompt cache.",
        )
        _STATE.instruments["tool_calls"] = meter.create_counter(
            name="synthesis.tool.calls",
            unit="{call}",
            description="Tool invocations grouped by tool name and outcome.",
        )
        _STATE.instruments["retrieval_latency"] = meter.create_histogram(
            name="synthesis.retrieval.latency",
            unit="s",
            description="Vector / keyword retrieval latency.",
        )
        _STATE.instruments["retrieval_result_count"] = meter.create_histogram(
            name="synthesis.retrieval.result_count",
            unit="{result}",
            description="Number of results returned per retrieval call.",
        )
        _STATE.instruments["agent_iterations"] = meter.create_counter(
            name="synthesis.agent.iterations",
            unit="{iteration}",
            description="Agent loop iterations completed.",
        )
        _STATE.instruments["guardrail_outcomes"] = meter.create_counter(
            name="synthesis.guardrail.outcomes",
            unit="{decision}",
            description="Guardrail decisions grouped by name and outcome.",
        )

        # ---- Parallel Prometheus registry ---------------------------------
        _bind_prometheus_registry()


def _bind_prometheus_registry() -> None:
    """Mirror the OTEL instruments into a prometheus_client registry.

    The OTEL Prometheus exporter (when installed) populates the default
    Prometheus REGISTRY automatically. When it's not installed we maintain
    parallel prometheus_client instruments here so /api/metrics still
    serves a valid Prometheus exposition format response.
    """

    try:
        from prometheus_client import CollectorRegistry, Counter, Histogram
    except ImportError:  # pragma: no cover - prometheus_client is in requirements
        logger.warning("prometheus_client not installed; /api/metrics will return 503.")
        return

    reg = CollectorRegistry()
    _STATE.prom_registry = reg

    # Buckets follow the OTEL GenAI spec (operation.duration buckets).
    _DURATION_BUCKETS = (
        0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64,
        1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92,
    )
    _TOKEN_BUCKETS = (
        1, 4, 16, 64, 256, 1024, 4096, 16384,
        65536, 262144, 1048576, 4194304, 16777216, 67108864,
    )
    _COUNT_BUCKETS = (
        0, 1, 2, 4, 8, 16, 32, 64, 128,
    )

    _STATE.prom_metrics["llm_operation_duration"] = Histogram(
        "gen_ai_client_operation_duration_seconds",
        "Overall duration of GenAI client operations.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model", "gen_ai_operation_name"),
        buckets=_DURATION_BUCKETS,
        registry=reg,
    )
    _STATE.prom_metrics["llm_token_usage"] = Histogram(
        "gen_ai_client_token_usage_tokens",
        "Token usage per GenAI request.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model", "token_kind"),
        buckets=_TOKEN_BUCKETS,
        registry=reg,
    )
    _STATE.prom_metrics["llm_requests"] = Counter(
        "synthesis_llm_requests_total",
        "Count of LLM requests by model / provider / operation.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model", "gen_ai_operation_name", "outcome"),
        registry=reg,
    )
    _STATE.prom_metrics["cache_read_input_tokens"] = Counter(
        "synthesis_llm_cache_read_input_tokens_total",
        "Cumulative input tokens served from the prompt cache.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model"),
        registry=reg,
    )
    _STATE.prom_metrics["cache_creation_input_tokens"] = Counter(
        "synthesis_llm_cache_creation_input_tokens_total",
        "Cumulative input tokens written to the prompt cache.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model"),
        registry=reg,
    )
    _STATE.prom_metrics["cache_uncached_input_tokens"] = Counter(
        "synthesis_llm_cache_uncached_input_tokens_total",
        "Cumulative input tokens that bypassed the prompt cache.",
        labelnames=("gen_ai_provider_name", "gen_ai_request_model"),
        registry=reg,
    )
    _STATE.prom_metrics["tool_calls"] = Counter(
        "synthesis_tool_calls_total",
        "Tool invocations grouped by tool name and outcome.",
        labelnames=("synthesis_tool_name", "outcome"),
        registry=reg,
    )
    _STATE.prom_metrics["retrieval_latency"] = Histogram(
        "synthesis_retrieval_latency_seconds",
        "Vector / keyword retrieval latency.",
        labelnames=("synthesis_workspace", "synthesis_retriever_tier", "synthesis_retrieval_backend"),
        buckets=_DURATION_BUCKETS,
        registry=reg,
    )
    _STATE.prom_metrics["retrieval_result_count"] = Histogram(
        "synthesis_retrieval_result_count",
        "Number of results returned per retrieval call.",
        labelnames=("synthesis_workspace", "synthesis_retriever_tier"),
        buckets=_COUNT_BUCKETS,
        registry=reg,
    )
    _STATE.prom_metrics["agent_iterations"] = Counter(
        "synthesis_agent_iterations_total",
        "Agent loop iterations completed.",
        labelnames=("synthesis_session_id",),
        registry=reg,
    )
    _STATE.prom_metrics["guardrail_outcomes"] = Counter(
        "synthesis_guardrail_outcomes_total",
        "Guardrail decisions grouped by name and outcome.",
        labelnames=("synthesis_guardrail_name", "synthesis_guardrail_outcome"),
        registry=reg,
    )


def _reset_metrics() -> None:
    """Drop the entire metrics state. Test-only."""

    global _STATE, _PROMETHEUS_READER

    with _LOCK:
        _STATE = _MetricsState()
        _PROMETHEUS_READER = None


# ---------------------------------------------------------------------------
# Recorder helpers (used by instrumentation.py)
# ---------------------------------------------------------------------------


def _record_otel_and_prom(
    instrument_key: str,
    value,
    *,
    otel_attrs: Optional[Dict[str, Any]] = None,
    prom_labels: Optional[Tuple[str, ...]] = None,
) -> None:
    """Push a value through both the OTEL instrument and the Prometheus mirror."""

    inst = _STATE.instruments.get(instrument_key)
    if inst is not None:
        try:
            if hasattr(inst, "record"):  # histogram
                inst.record(value, attributes=otel_attrs or {})
            elif hasattr(inst, "add"):  # counter
                inst.add(value, attributes=otel_attrs or {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("OTEL instrument %s record failed: %s", instrument_key, exc)

    prom = _STATE.prom_metrics.get(instrument_key)
    if prom is not None and prom_labels is not None:
        try:
            if hasattr(prom, "observe"):  # histogram
                prom.labels(*prom_labels).observe(value)
            elif hasattr(prom, "inc"):  # counter
                prom.labels(*prom_labels).inc(value)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Prom instrument %s record failed: %s", instrument_key, exc)


def _record_cache_event(
    model: str,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    uncached_input_tokens: int,
) -> None:
    """Push a cache event into the rolling window deque."""

    with _LOCK:
        _STATE.cache_events.append(
            _CacheEvent(
                timestamp=time.time(),
                model=model,
                cache_read_tokens=int(cache_read_tokens or 0),
                cache_creation_tokens=int(cache_creation_tokens or 0),
                uncached_input_tokens=int(uncached_input_tokens or 0),
            ),
        )


# ---------------------------------------------------------------------------
# Prometheus exposition format
# ---------------------------------------------------------------------------


def render_prometheus() -> Tuple[bytes, str]:
    """Render the current registry as Prometheus exposition format.

    Returns
    -------
    (body, content_type)
        body: bytes — the exposition payload.
        content_type: str — the canonical Content-Type header value.
    """

    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    except ImportError:  # pragma: no cover
        return (b"", "text/plain; charset=utf-8")

    if _STATE.prom_registry is None:
        return (b"# synthesis_engine metrics not initialized\n", "text/plain; version=0.0.4; charset=utf-8")

    return (generate_latest(_STATE.prom_registry), CONTENT_TYPE_LATEST)


__all__ = [
    "get_metrics_registry",
    "get_meter_provider",
    "cache_stats_snapshot",
    "render_prometheus",
]
