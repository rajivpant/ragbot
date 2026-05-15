"""Tracer + meter provider initialization for synthesis_engine.

Design (Approach A — module-level singleton via the OTEL global provider):

  init_tracer() sets the process-wide tracer and meter providers. All
  call sites obtain tracers via :func:`get_tracer` which delegates to the
  OTEL global. This matches the OTEL design (telemetry is a process-wide
  cross-cutting concern); the alternative (per-request dependency
  injection) would bleed observability into every public API surface of
  synthesis_engine and violate the substrate-cleanliness constraint.

Initialization is idempotent: a second call with the same configuration
is a no-op; a call with a different exporter rebuilds providers. If
init_tracer() is never called, OTEL's no-op tracer is used and
observability is silently disabled — this is the right default for
unit tests and minimal deployments.

Exporter selection priority:

  1. Explicit ``exporter`` parameter to init_tracer (highest priority).
     The test suite passes InMemorySpanExporter here.
  2. ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var present → OTLP gRPC
     exporter (the OTEL standard env var; respected by every collector).
  3. ``RAGBOT_OTEL_CONSOLE=1`` env var → ConsoleSpanExporter (dev default).
  4. Otherwise → silent no-op (production-safe default: no telemetry
     flows out unless explicitly configured).

Environment variables consumed (all OTEL-standard except where noted):

  OTEL_EXPORTER_OTLP_ENDPOINT             OTLP collector endpoint for all
                                          signals (traces + metrics) unless
                                          a per-signal override is set.
  OTEL_EXPORTER_OTLP_METRICS_ENDPOINT     Per-signal override for metric
                                          export. Set to the literal string
                                          "none" (or empty when the unified
                                          endpoint is set) to disable
                                          metric OTLP export while keeping
                                          trace export intact. Used by the
                                          bundled docker-compose stack
                                          because Jaeger accepts traces but
                                          not metrics over OTLP.
  OTEL_EXPORTER_OTLP_HEADERS              Optional headers for OTLP (API key, etc.).
  OTEL_EXPORTER_OTLP_PROTOCOL             "grpc" (default) | "http/protobuf".
  OTEL_SERVICE_NAME                       Overrides the service_name parameter.
  OTEL_RESOURCE_ATTRIBUTES                Additional resource attributes (k=v,k=v).
  RAGBOT_OTEL_CONSOLE                     "1" → force console exporter
                                          (non-standard; useful for local
                                          dev when no OTLP collector is
                                          running).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_INIT_LOCK = threading.Lock()
_INITIALIZED = False
_TRACER_PROVIDER: Optional[Any] = None
_METER_PROVIDER: Optional[Any] = None
_LAST_CONFIG: Optional[dict] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_tracer(
    service_name: str = "synthesis_engine",
    *,
    exporter: Optional[Any] = None,
    metric_reader: Optional[Any] = None,
    resource_attributes: Optional[dict] = None,
    force: bool = False,
) -> Optional[Any]:
    """Initialise the OpenTelemetry tracer and meter providers.

    Parameters
    ----------
    service_name:
        The OTEL ``service.name`` resource attribute. The substrate default
        is ``synthesis_engine``; runtimes should pass their own name
        (``ragbot``, ``ragenie``, ``synthesis-console``) so traces are
        attributable to the runtime that emitted them.
    exporter:
        Optional span exporter instance. If provided, this exporter is
        used directly (a ``SimpleSpanProcessor`` wraps it so spans flush
        synchronously — useful in tests). If None, exporter selection
        falls back to the env-var rules in the module docstring.
    metric_reader:
        Optional metric reader instance. If provided, used directly.
        If None, a periodic OTLP reader is used when
        ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, otherwise no reader is
        attached (metrics still accumulate via the Prometheus bridge).
    resource_attributes:
        Optional dict of additional resource attributes merged into the
        ``Resource`` (e.g., ``{"deployment.environment": "staging"}``).
    force:
        If True, re-initialise even if already initialised.

    Returns
    -------
    The constructed TracerProvider, or None if OpenTelemetry is not
    installed. When None is returned, all subsequent ``get_tracer()``
    calls return the OTEL API's no-op tracer and instrumentation is
    silently disabled.
    """

    global _INITIALIZED, _TRACER_PROVIDER, _METER_PROVIDER, _LAST_CONFIG

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
    except ImportError:
        logger.info(
            "OpenTelemetry SDK not installed; observability disabled. "
            "Install opentelemetry-api / opentelemetry-sdk to enable.",
        )
        return None

    with _INIT_LOCK:
        config_key = {
            "service_name": os.environ.get("OTEL_SERVICE_NAME") or service_name,
            "exporter_id": id(exporter) if exporter is not None else None,
            "metric_reader_id": id(metric_reader) if metric_reader is not None else None,
            "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
            "console": os.environ.get("RAGBOT_OTEL_CONSOLE"),
            "resource_attributes": _hashable_dict(resource_attributes or {}),
        }
        if _INITIALIZED and not force and config_key == _LAST_CONFIG:
            return _TRACER_PROVIDER

        # Honour the documented priority order: an explicit ``exporter``
        # already wired in by a previous init_tracer call WINS over a later
        # env-var driven call that passes no exporter. Tests install an
        # InMemorySpanExporter session-wide; without this guard, a
        # FastAPI app startup inside a test (e.g., TestClient lifespan
        # firing api.main's init_tracer with no exporter) would replace
        # the provider and silently drop test spans.
        if (
            _INITIALIZED
            and not force
            and exporter is None
            and _LAST_CONFIG is not None
            and _LAST_CONFIG.get("exporter_id") is not None
        ):
            return _TRACER_PROVIDER

        # Re-init path. The previous providers (if any) own the current
        # Prometheus reader singleton; OTEL refuses to attach the same
        # reader to a second MeterProvider. Flush + drop the old state
        # inline (we already hold ``_INIT_LOCK``, so we cannot call
        # ``shutdown_tracer`` here without deadlocking).
        if _INITIALIZED:
            if _TRACER_PROVIDER is not None:
                try:
                    _TRACER_PROVIDER.shutdown()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Tracer provider shutdown raised: %s", exc)
            if _METER_PROVIDER is not None:
                try:
                    _METER_PROVIDER.shutdown()
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Meter provider shutdown raised: %s", exc)
            from .metrics import _reset_metrics
            _reset_metrics()
            _TRACER_PROVIDER = None
            _METER_PROVIDER = None
            _INITIALIZED = False

        # ----- Resource ----------------------------------------------------
        resource = _build_resource(
            service_name=config_key["service_name"],
            extra=resource_attributes,
        )

        # ----- Tracer provider --------------------------------------------
        tracer_provider = TracerProvider(resource=resource)

        if exporter is not None:
            # Tests inject InMemorySpanExporter here. SimpleSpanProcessor
            # gives synchronous flush, which tests need to observe spans
            # immediately after the operation.
            tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
        else:
            otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                        OTLPSpanExporter,
                    )
                except ImportError:  # pragma: no cover - optional dep
                    logger.warning(
                        "opentelemetry-exporter-otlp-proto-grpc not installed; "
                        "OTLP endpoint will be ignored.",
                    )
                else:
                    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                    tracer_provider.add_span_processor(
                        BatchSpanProcessor(otlp_exporter),
                    )
            elif os.environ.get("RAGBOT_OTEL_CONSOLE") == "1":
                tracer_provider.add_span_processor(
                    SimpleSpanProcessor(ConsoleSpanExporter()),
                )

        trace.set_tracer_provider(tracer_provider)
        _TRACER_PROVIDER = tracer_provider

        # ----- Meter provider ---------------------------------------------
        # Metric-endpoint resolution honours the OTEL standard per-signal
        # env-var hierarchy:
        #
        #   1. ``OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`` — explicit metrics
        #      endpoint (or the literal string ``"none"`` / empty to
        #      disable metric OTLP export entirely while keeping the
        #      Prometheus reader attached for ``/api/metrics``).
        #   2. ``OTEL_EXPORTER_OTLP_ENDPOINT`` — unified fallback for all
        #      signals (the value used for trace export above).
        #
        # The ``"none"`` sentinel exists because the bundled docker-compose
        # stack points the unified endpoint at Jaeger, which accepts traces
        # over OTLP but not metrics — without an opt-out, the metric
        # exporter would print ``UNIMPLEMENTED`` errors on every export
        # interval. Operators with a real OTLP-metrics-accepting collector
        # (Prometheus OTLP receiver, Phoenix, Datadog) override the env to
        # the collector's URL.
        readers = []
        if metric_reader is not None:
            readers.append(metric_reader)
        else:
            metrics_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
            if metrics_endpoint is None:
                metrics_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            if metrics_endpoint and metrics_endpoint.strip().lower() != "none":
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                        OTLPMetricExporter,
                    )
                except ImportError:  # pragma: no cover
                    pass
                else:
                    readers.append(
                        PeriodicExportingMetricReader(
                            OTLPMetricExporter(endpoint=metrics_endpoint),
                            export_interval_millis=30_000,
                        ),
                    )

        # Always attach an in-process aggregating reader so the
        # /api/metrics endpoint can scrape current values without
        # talking to an external collector. This is what makes the
        # Prometheus exposition format work locally.
        from .metrics import _get_or_create_prometheus_reader

        readers.append(_get_or_create_prometheus_reader())

        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=readers,
        )
        metrics.set_meter_provider(meter_provider)
        _METER_PROVIDER = meter_provider

        # ----- Bind metrics ------------------------------------------------
        from .metrics import _bind_meter_provider

        _bind_meter_provider(meter_provider)

        _INITIALIZED = True
        _LAST_CONFIG = config_key
        logger.info(
            "synthesis_engine.observability initialised: service_name=%s exporter=%s",
            config_key["service_name"],
            "explicit" if exporter is not None else (
                "otlp" if config_key["otlp_endpoint"] else
                "console" if config_key["console"] == "1" else
                "noop"
            ),
        )
        return tracer_provider


def shutdown_tracer() -> None:
    """Flush and shut down the tracer and meter providers."""

    global _INITIALIZED, _TRACER_PROVIDER, _METER_PROVIDER, _LAST_CONFIG

    with _INIT_LOCK:
        if _TRACER_PROVIDER is not None:
            try:
                _TRACER_PROVIDER.shutdown()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Tracer provider shutdown raised: %s", exc)
        if _METER_PROVIDER is not None:
            try:
                _METER_PROVIDER.shutdown()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Meter provider shutdown raised: %s", exc)

        from .metrics import _reset_metrics

        _reset_metrics()

        _TRACER_PROVIDER = None
        _METER_PROVIDER = None
        _INITIALIZED = False
        _LAST_CONFIG = None


def get_tracer(name: str = "synthesis_engine") -> Any:
    """Return a tracer for the given name.

    When OTEL is not installed, returns the API's no-op tracer.
    """

    try:
        from opentelemetry import trace
    except ImportError:  # pragma: no cover - OTEL is in requirements
        return _NoOpTracer()

    return trace.get_tracer(name)


def get_tracer_provider() -> Optional[Any]:
    """Return the active TracerProvider (None if uninitialised)."""

    return _TRACER_PROVIDER


def get_meter_provider() -> Optional[Any]:
    """Return the active MeterProvider (None if uninitialised)."""

    return _METER_PROVIDER


def is_initialized() -> bool:
    return _INITIALIZED


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_resource(service_name: str, extra: Optional[dict]):
    """Build an OTEL Resource respecting OTEL_RESOURCE_ATTRIBUTES."""

    from opentelemetry.sdk.resources import Resource

    attrs: dict = {"service.name": service_name}
    # Environment override.
    env_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES")
    if env_attrs:
        for pair in env_attrs.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                attrs[k.strip()] = v.strip()
    if extra:
        attrs.update(extra)
    return Resource.create(attrs)


def _hashable_dict(d: dict):
    """Convert a dict to a hashable form for cache-key comparison."""

    return tuple(sorted((k, str(v)) for k, v in d.items()))


# ---------------------------------------------------------------------------
# Fallback no-op tracer (only used if OTEL isn't installed)
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Minimal no-op span; matches the API surface we use."""

    def set_attribute(self, *args, **kwargs):
        return None

    def set_attributes(self, *args, **kwargs):
        return None

    def set_status(self, *args, **kwargs):
        return None

    def record_exception(self, *args, **kwargs):
        return None

    def add_event(self, *args, **kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def end(self):
        return None


class _NoOpTracer:
    def start_as_current_span(self, *args, **kwargs):
        return _NoOpSpan()

    def start_span(self, *args, **kwargs):
        return _NoOpSpan()


__all__ = [
    "init_tracer",
    "shutdown_tracer",
    "get_tracer",
    "get_tracer_provider",
    "get_meter_provider",
    "is_initialized",
]
