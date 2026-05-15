"""Span / metric attribute names used across the synthesis_engine observability surface.

Two namespaces are defined here:

1. ``gen_ai.*`` — OpenTelemetry GenAI semantic conventions (May 2026 status:
   in development, recommended for adoption by Datadog, Honeycomb, Phoenix,
   Langfuse, and other backends). We follow the spec exactly and re-export
   the constants for use across the substrate. Source:
   https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/

2. ``synthesis.*`` — Synthesis-specific extensions. Used for telemetry that
   has no equivalent in the OTEL GenAI spec (workspace identity, retrieval
   tier, guardrail outcomes, cache control state). Each attribute is
   documented inline with type, semantics, and stability.

Stability commitments for ``synthesis.*``:

  - Constants added in this module are part of the substrate contract. Once
    in use, the attribute name does not change without a major-version bump
    of synthesis_engine.
  - The semantic meaning of an attribute does not change between minor
    versions. If semantics shift, a new attribute name is introduced and
    the old one is kept for one minor cycle with a deprecation warning.
  - Values for synthesis.* attributes are documented enums where applicable
    (see SYNTHESIS_GUARDRAIL_OUTCOME). Backends can rely on the value set.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# OpenTelemetry GenAI semantic conventions (May 2026)
#
# See https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/ for the
# authoritative spec. Status of these attributes is "in development" as of
# May 2026 — names should be considered the canonical 2026 set but may be
# promoted to stable in subsequent OTEL releases.
# ---------------------------------------------------------------------------

# Required: provider identifier (anthropic, openai, google, etc.).
GEN_AI_SYSTEM = "gen_ai.system"  # deprecated alias kept for back-compat
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"

# Required: operation type. One of: "chat", "embeddings", "text_completion",
# "generate_content", "execute_tool", etc.
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"

# Conditionally required: model id as sent in the request.
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"

# Recommended: request parameters.
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_TOP_K = "gen_ai.request.top_k"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GEN_AI_REQUEST_SEED = "gen_ai.request.seed"
GEN_AI_REQUEST_STREAM = "gen_ai.request.stream"
GEN_AI_REQUEST_CHOICE_COUNT = "gen_ai.request.choice.count"
GEN_AI_REQUEST_ENCODING_FORMATS = "gen_ai.request.encoding_formats"

# Recommended: response identification.
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_RESPONSE_TIME_TO_FIRST_CHUNK = "gen_ai.response.time_to_first_chunk"

# Recommended: token usage and cache accounting.
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS = "gen_ai.usage.cache_creation.input_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_USAGE_REASONING_OUTPUT_TOKENS = "gen_ai.usage.reasoning.output_tokens"

# Conditionally required: session/conversation identity (cross-turn correlation).
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_OUTPUT_TYPE = "gen_ai.output.type"

# Tool execution (the OTEL spec covers tool-call subspans).
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_TYPE = "gen_ai.tool.type"  # "function", "extension", "datastore"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"

# Retrieval / RAG (the OTEL spec covers retrieval as a sub-domain of GenAI).
GEN_AI_DATA_SOURCE_ID = "gen_ai.data_source.id"

# Agent identity (when the LLM call is made on behalf of a named agent).
GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"

# Embeddings.
GEN_AI_EMBEDDINGS_DIMENSION_COUNT = "gen_ai.embeddings.dimension.count"


# ---------------------------------------------------------------------------
# Synthesis-specific attributes
#
# Each constant documents its type, semantics, value range, and stability
# guarantees. Backends that consume these attributes (Datadog dashboards,
# Honeycomb queries, Phoenix evaluators) should be able to rely on this
# contract.
# ---------------------------------------------------------------------------

# str. The ai-knowledge workspace name the operation is scoped to.
# Required on every retrieval span; recommended on LLM spans when the call
# is made on behalf of a specific workspace.
# Examples: "personal", "client-a", "synthesis_skills".
SYNTHESIS_WORKSPACE = "synthesis.workspace"

# str. The local tool name as recognized by the agent loop. Distinct from
# gen_ai.tool.name (which is the upstream provider's tool identifier) because
# the substrate may translate names at the boundary.
SYNTHESIS_TOOL_NAME = "synthesis.tool_name"

# str. The retrieval tier in a multi-tier retriever pipeline. The substrate
# does not enforce an enum — runtimes name their own tiers. Suggested values:
#   "vector"        — pure vector ANN search
#   "keyword"       — FTS / BM25
#   "hybrid"        — fused vector + keyword
#   "entity"        — entity-graph lookup
#   "session"       — session-memory lookup
SYNTHESIS_RETRIEVER_TIER = "synthesis.retriever.tier"

# str. The guardrail name being evaluated. Examples: "pii_check",
# "confidentiality_boundary", "out_of_scope_refusal".
SYNTHESIS_GUARDRAIL_NAME = "synthesis.guardrail.name"

# str. Enum: "allow", "deny", "warn", "redact". The guardrail's decision.
SYNTHESIS_GUARDRAIL_OUTCOME = "synthesis.guardrail.outcome"

# int. The 0-indexed iteration counter inside an agent loop (one increment
# per planning/execution cycle).
SYNTHESIS_AGENT_ITERATION = "synthesis.agent.iteration"

# int. The k parameter passed to a retrieval call.
SYNTHESIS_RETRIEVAL_K = "synthesis.retrieval.k"

# int. The character length of the retrieval query. Used to track query
# distribution without recording the query text itself (privacy default).
SYNTHESIS_RETRIEVAL_QUERY_LENGTH = "synthesis.retrieval.query_length"

# double. The score of the top-ranked retrieval result. Useful for tracking
# retrieval quality degradation over time.
SYNTHESIS_RETRIEVAL_TOP_SCORE = "synthesis.retrieval.top_score"

# int. The number of results returned (may be < k if the corpus is smaller).
SYNTHESIS_RETRIEVAL_RESULT_COUNT = "synthesis.retrieval.result_count"

# str. The vector store backend name (e.g., "pgvector"). Substrate consumers
# that plug in alternative backends behind the VectorStore ABC report their
# own backend_name value here so retrieval-latency dashboards can split by
# backend when more than one ships in the same deployment.
SYNTHESIS_RETRIEVAL_BACKEND = "synthesis.retrieval.backend"

# str. The content_type filter applied to a retrieval call, when set.
SYNTHESIS_RETRIEVAL_CONTENT_TYPE = "synthesis.retrieval.content_type"

# double. The cache-hit ratio for a single LLM call's prompt:
#   cache_read_input_tokens / (cache_read_input_tokens + cache_creation_input_tokens + uncached_input_tokens)
# Range [0.0, 1.0]. Recorded as both a span attribute and a histogram metric.
SYNTHESIS_CACHE_HIT_RATIO = "synthesis.cache.hit_ratio"

# bool. Whether the substrate auto-applied cache_control on the request.
# False when the caller explicitly disabled caching via the config knob.
SYNTHESIS_CACHE_CONTROL_ENABLED = "synthesis.cache.control_enabled"

# str. The backend name reported by the LLM backend ("litellm", "direct").
# Distinct from gen_ai.provider.name (which is the *upstream* provider
# identifier — anthropic, openai, google).
SYNTHESIS_LLM_BACKEND = "synthesis.llm.backend"

# str. The reasoning effort level passed in the request, when set.
# Values: "minimal", "low", "medium", "high".
SYNTHESIS_REASONING_EFFORT = "synthesis.reasoning_effort"

# str. The session id (when one is available — agent loop sessions, MCP
# request ids, etc.). Distinct from gen_ai.conversation.id which is the
# upstream chat thread.
SYNTHESIS_SESSION_ID = "synthesis.session.id"


# ---------------------------------------------------------------------------
# Operation-name enum values for gen_ai.operation.name
# ---------------------------------------------------------------------------

OP_CHAT = "chat"
OP_EMBEDDINGS = "embeddings"
OP_TEXT_COMPLETION = "text_completion"
OP_GENERATE_CONTENT = "generate_content"
OP_EXECUTE_TOOL = "execute_tool"
OP_RETRIEVAL = "retrieval"  # synthesis-specific; OTEL has no formal name


# ---------------------------------------------------------------------------
# Provider-name enum values for gen_ai.provider.name
#
# Per the OTEL GenAI spec, the standard provider identifiers are:
#   "openai", "anthropic", "google.gemini", "aws.bedrock", "azure.openai",
#   "cohere", "mistral_ai", "ibm.watson", "perplexity", "x.ai", "deepseek".
# We expose the ones the substrate routes to today.
# ---------------------------------------------------------------------------

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDER_GOOGLE = "google.gemini"
PROVIDER_OLLAMA = "ollama"
PROVIDER_UNKNOWN = "unknown"


__all__ = [
    # Standard
    "GEN_AI_SYSTEM",
    "GEN_AI_PROVIDER_NAME",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_MAX_TOKENS",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_REQUEST_TOP_P",
    "GEN_AI_REQUEST_TOP_K",
    "GEN_AI_REQUEST_STOP_SEQUENCES",
    "GEN_AI_REQUEST_FREQUENCY_PENALTY",
    "GEN_AI_REQUEST_PRESENCE_PENALTY",
    "GEN_AI_REQUEST_SEED",
    "GEN_AI_REQUEST_STREAM",
    "GEN_AI_REQUEST_CHOICE_COUNT",
    "GEN_AI_REQUEST_ENCODING_FORMATS",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_RESPONSE_ID",
    "GEN_AI_RESPONSE_FINISH_REASONS",
    "GEN_AI_RESPONSE_TIME_TO_FIRST_CHUNK",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS",
    "GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS",
    "GEN_AI_USAGE_REASONING_OUTPUT_TOKENS",
    "GEN_AI_CONVERSATION_ID",
    "GEN_AI_OUTPUT_TYPE",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_TOOL_TYPE",
    "GEN_AI_TOOL_CALL_ID",
    "GEN_AI_TOOL_DESCRIPTION",
    "GEN_AI_DATA_SOURCE_ID",
    "GEN_AI_AGENT_ID",
    "GEN_AI_AGENT_NAME",
    "GEN_AI_AGENT_DESCRIPTION",
    "GEN_AI_AGENT_VERSION",
    "GEN_AI_EMBEDDINGS_DIMENSION_COUNT",
    # Synthesis extensions
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
    "SYNTHESIS_RETRIEVAL_BACKEND",
    "SYNTHESIS_RETRIEVAL_CONTENT_TYPE",
    "SYNTHESIS_CACHE_HIT_RATIO",
    "SYNTHESIS_CACHE_CONTROL_ENABLED",
    "SYNTHESIS_LLM_BACKEND",
    "SYNTHESIS_REASONING_EFFORT",
    "SYNTHESIS_SESSION_ID",
    # Op enums
    "OP_CHAT",
    "OP_EMBEDDINGS",
    "OP_TEXT_COMPLETION",
    "OP_GENERATE_CONTENT",
    "OP_EXECUTE_TOOL",
    "OP_RETRIEVAL",
    # Provider enums
    "PROVIDER_ANTHROPIC",
    "PROVIDER_OPENAI",
    "PROVIDER_GOOGLE",
    "PROVIDER_OLLAMA",
    "PROVIDER_UNKNOWN",
]
