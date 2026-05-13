"""Observability substrate for synthesis_engine.

This package provides OpenTelemetry-based observability that is shared across
every synthesis_engine consumer (Ragbot, Ragenie, synthesis-console, future
runtimes). The package is intentionally substrate-clean: it depends only on
the OpenTelemetry API + SDK plus the standard library. It MUST NOT depend on
ragbot, ragenie, or any specific runtime.

Public surface (everything documented here is part of the substrate contract):

    init_tracer(service_name, exporter=None)
        Initialise the global tracer + meter providers. Call once at process
        startup. Idempotent. If never called, OTEL's no-op tracer is used and
        observability is silently disabled.

    shutdown_tracer()
        Flush and shut down providers. Useful in tests and at clean shutdown.

    chat_completion_span(model, provider, operation="chat", attributes=None)
        Context manager that wraps an LLM completion call with a span named
        per the OTEL GenAI spec ("chat <model>"). Records usage tokens, finish
        reason, and cache hit metadata via record_llm_response().

    retrieval_span(workspace, query, k, attributes=None)
        Context manager that wraps a vector store retrieval call. Records
        latency, top score, and result count via record_retrieval_result().

    tool_span(tool_name, attributes=None)
        Context manager for tool execution. Records success/failure via
        record_tool_result().

    guardrail_span(guardrail_name, attributes=None)
        Context manager for a guardrail / policy check.

    agent_iteration_span(iteration, attributes=None)
        Context manager for one iteration of an agent loop.

    record_*(...) helpers
        Functional helpers that callers can use from inside their own span
        contexts when they need to push attribute updates without nesting
        another span.

The metric registry lives in :mod:`synthesis_engine.observability.metrics`
and is exposed via :func:`get_meter_provider` for the metrics router to
scrape into Prometheus exposition format.

Attribute names follow the OpenTelemetry GenAI semantic conventions where
they exist (``gen_ai.*``). Synthesis-specific attributes (``synthesis.*``)
are documented in :mod:`synthesis_engine.observability.attributes` with
explicit semantics and stability guarantees.

The package operates correctly when OpenTelemetry is uninstalled, by
detecting the absence of the SDK and degrading to no-op spans. This keeps
the substrate runnable in minimal deployments.
"""

from __future__ import annotations

from .attributes import (
    # OTEL GenAI standard attributes (re-exported for ergonomic access).
    GEN_AI_SYSTEM,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
    GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    # Synthesis-specific extensions.
    SYNTHESIS_WORKSPACE,
    SYNTHESIS_TOOL_NAME,
    SYNTHESIS_RETRIEVER_TIER,
    SYNTHESIS_GUARDRAIL_NAME,
    SYNTHESIS_GUARDRAIL_OUTCOME,
    SYNTHESIS_AGENT_ITERATION,
    SYNTHESIS_RETRIEVAL_K,
    SYNTHESIS_RETRIEVAL_QUERY_LENGTH,
    SYNTHESIS_RETRIEVAL_TOP_SCORE,
    SYNTHESIS_RETRIEVAL_RESULT_COUNT,
    SYNTHESIS_CACHE_HIT_RATIO,
    SYNTHESIS_CACHE_CONTROL_ENABLED,
)
from .instrumentation import (
    agent_iteration_span,
    chat_completion_span,
    guardrail_span,
    retrieval_span,
    tool_span,
    record_llm_response,
    record_retrieval_result,
    record_tool_result,
    record_cache_hit,
)
from .metrics import (
    get_metrics_registry,
    get_meter_provider,
    render_prometheus,
    cache_stats_capture,
)
from .tracer import (
    init_tracer,
    shutdown_tracer,
    get_tracer,
    get_tracer_provider,
)

__all__ = [
    # Init / lifecycle
    "init_tracer",
    "shutdown_tracer",
    "get_tracer",
    "get_tracer_provider",
    # Instrumentation context managers
    "chat_completion_span",
    "retrieval_span",
    "tool_span",
    "guardrail_span",
    "agent_iteration_span",
    # Functional recorders
    "record_llm_response",
    "record_retrieval_result",
    "record_tool_result",
    "record_cache_hit",
    # Metrics
    "get_metrics_registry",
    "get_meter_provider",
    "render_prometheus",
    "cache_stats_capture",
    # Standard OTEL GenAI attributes
    "GEN_AI_SYSTEM",
    "GEN_AI_PROVIDER_NAME",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_MAX_TOKENS",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_RESPONSE_FINISH_REASONS",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_TOOL_TYPE",
    # Synthesis-specific attributes
    "SYNTHESIS_WORKSPACE",
    "SYNTHESIS_TOOL_NAME",
    "SYNTHESIS_RETRIEVER_TIER",
    "SYNTHESIS_GUARDRAIL_NAME",
    "SYNTHESIS_GUARDRAIL_OUTCOME",
    "SYNTHESIS_AGENT_ITERATION",
    "SYNTHESIS_RETRIEVAL_K",
    "SYNTHESIS_RETRIEVAL_QUERY_LENGTH",
    "SYNTHESIS_RETRIEVAL_TOP_SCORE",
    "SYNTHESIS_RETRIEVAL_RESULT_COUNT",
    "SYNTHESIS_CACHE_HIT_RATIO",
    "SYNTHESIS_CACHE_CONTROL_ENABLED",
]
