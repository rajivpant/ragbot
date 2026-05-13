# synthesis_engine.observability

The observability substrate for the synthesis-engineering family of
runtimes (Ragbot, Ragenie, synthesis-console, and future siblings). It
follows the OpenTelemetry GenAI semantic conventions, adds a small,
documented set of `synthesis.*` extensions, and ships an in-process
Prometheus bridge so a CTO can scrape metrics on day one without
standing up a collector.

## Architecture

```
synthesis_engine/observability/
├── tracer.py          init_tracer / shutdown_tracer / global providers
├── attributes.py      gen_ai.* and synthesis.* attribute name constants
├── instrumentation.py span context managers and record_* helpers
├── metrics.py         OTEL meter + parallel prometheus_client registry
└── __init__.py        public re-exports (the substrate contract)
```

The substrate exposes four ergonomic surfaces:

1. **Init / lifecycle** — `init_tracer()` and `shutdown_tracer()`. Call
   once at process startup. Idempotent. Silent no-op when OpenTelemetry
   is not installed (so the package is safe to import in minimal
   environments).
2. **Span context managers** — `chat_completion_span`, `retrieval_span`,
   `tool_span`, `guardrail_span`, `agent_iteration_span`. Each starts a
   span with the right pre-populated attributes, auto-records exceptions,
   and records the canonical metric on exit.
3. **Functional recorders** — `record_llm_response`, `record_retrieval_result`,
   `record_tool_result`, `record_cache_hit`. Push response data onto the
   active span and into the metric registry.
4. **Metrics** — `render_prometheus()` for the exposition payload,
   `cache_stats_capture(window_seconds)` for the JSON cache view.

Attribute names are declared in `attributes.py`. The `gen_ai.*` constants
mirror the OpenTelemetry GenAI semantic-conventions spec; the `synthesis.*`
constants are part of the substrate contract — once in use, the name does
not change without a major-version bump of `synthesis_engine`.

## Pluggable backends

The substrate is exporter-agnostic. Pick a backend by setting
`OTEL_EXPORTER_OTLP_ENDPOINT` (and any auth headers via
`OTEL_EXPORTER_OTLP_HEADERS`); the substrate auto-detects the gRPC
OTLP exporter when the corresponding `opentelemetry-exporter-otlp-proto-grpc`
package is installed.

### Datadog

```bash
pip install ddtrace opentelemetry-exporter-otlp-proto-grpc
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp.datadoghq.com"
export OTEL_EXPORTER_OTLP_HEADERS="dd-api-key=$DD_API_KEY"
export OTEL_SERVICE_NAME=ragbot
```

Datadog consumes OTLP natively (gRPC and HTTP). The `gen_ai.*` attributes
populate Datadog's LLM Observability product directly; the `synthesis.*`
extensions show up as custom tags in the trace view.

### Honeycomb

```bash
pip install opentelemetry-exporter-otlp-proto-grpc
export OTEL_EXPORTER_OTLP_ENDPOINT="https://api.honeycomb.io"
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=$HONEYCOMB_API_KEY"
export OTEL_SERVICE_NAME=ragbot
```

Honeycomb is OTLP-native. The substrate's per-span attributes drop into
Honeycomb's query-builder dimensions; the cache-hit-ratio and retrieval
latency histograms work as Honeycomb derived columns.

### Phoenix (or Langfuse)

```bash
pip install arize-phoenix opentelemetry-exporter-otlp-proto-grpc
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:6006/v1/traces"
export OTEL_SERVICE_NAME=ragbot
```

Phoenix is a self-hostable open-source LLM-trace UI. It speaks OTLP and
understands the `gen_ai.*` GenAI conventions out of the box. Langfuse
follows the same pattern — point `OTEL_EXPORTER_OTLP_ENDPOINT` at the
Langfuse OTLP ingest URL with the project credentials in
`OTEL_EXPORTER_OTLP_HEADERS`.

## Prompt-cache discipline

Anthropic's prompt cache delivers a measurable input-token-cost reduction
once the system prompt and large reusable context blocks carry the
`cache_control` annotation. The substrate applies the annotation
automatically:

- **What it does.** `synthesis_engine.llm.cache_control.apply_cache_control_to_messages`
  rewrites the system prompt into a structured block with
  `cache_control: {"type": "ephemeral"}`, and any user-content block
  longer than `cache_min_block_tokens` (default 1024) gets the same
  annotation. The rewrite is invoked by the LiteLLM and Anthropic-direct
  backends before each request.
- **When it triggers.** Only for Anthropic models (model id contains
  `anthropic/` or `claude`). Non-Anthropic models pass through unchanged.
- **How to disable.** Pass `cache_control_enabled: False` in
  `LLMRequest.extra` for a single call, or set the substrate-wide knob
  via the same key in your application config.
- **What you see in telemetry.** Every LLM span carries
  `synthesis.cache.control_enabled` (bool), `gen_ai.usage.cache_read.input_tokens`,
  `gen_ai.usage.cache_creation.input_tokens`, and the derived
  `synthesis.cache.hit_ratio`. The rolling cache view is available at
  `GET /api/metrics/cache?window_minutes=60`.

## Eval harness

Eval cases live under `tests/evals/cases/<category>/<id>.yaml`. The
runner discovers them at startup; no registration step is required.

### Adding a case

```yaml
id: retrieval_basic_grounding
category: retrieval                # optional; defaults to parent directory
description: Agent answers from the corpus, not parametric memory.
prompt: |
  What is X? Cite the chunks you used.
evaluator: citation_match          # one of: keyword_match | citation_match |
                                   # refusal_match | tool_match | exact
expected:
  required_citations: [chunk-1, chunk-2]
  forbidden_citations: [chunk-99]
fixture: rag_corpus_small.md       # optional; relative to tests/evals/fixtures/
inline_response: |                 # deterministic response for reproducibility
  Citing chunk-1 and chunk-2 …
quick: true                        # included in eval-quick by default
live: false                        # when true, harness invokes the live LLM
```

Available evaluators:

| Evaluator         | Purpose                                          |
|-------------------|--------------------------------------------------|
| `keyword_match`   | All `must_contain` keywords present; no `must_not_contain` keywords present. |
| `citation_match`  | Every `required_citations` id appears in the response. |
| `refusal_match`   | Response contains a refusal marker and does not leak forbidden content. |
| `tool_match`      | Response is a JSON tool call with the expected `tool` and `required_args`. |
| `exact`           | Response equals `expected.text` after trim.       |

### Running the suite

```bash
make eval         # full suite; scorecard at tests/evals/last-scorecard.md
make eval-quick   # only cases with quick: true
```

The runner exits non-zero when any non-skipped case fails. Live cases
(`live: true`) are skipped automatically when no provider API key is
configured in the environment, so the suite stays runnable in CI.

## Spec cross-references

- [OpenTelemetry GenAI semantic conventions — Spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OpenTelemetry GenAI semantic conventions — Metrics](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/)
- [Anthropic prompt caching documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/)
