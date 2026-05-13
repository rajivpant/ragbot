# synthesis_engine

The shared substrate library for synthesis-engineering runtimes.

## Purpose

`synthesis_engine` holds the cross-runtime building blocks used by every
synthesis-engineering reference implementation. Ragbot, Ragenie,
synthesis-console, and future runtimes all import from this package
rather than duplicating substrate code.

## Contents

- `config` — `engines.yaml` loading, model/provider resolution, defaults
- `workspaces` — `ai-knowledge-*` discovery, profiles, instruction paths
- `keystore` — API key resolution from `~/.synthesis/`, user-config helpers
- `exceptions` — shared error hierarchy
- `models` — substrate-level Pydantic types
- `llm/` — pluggable LLM backend interface (LiteLLM and direct SDK)
- `vectorstore/` — pluggable vector store interface (pgvector, qdrant)
- `skills/` — Agent Skill discovery, parsing, data model

## Consumers

- **Ragbot** — conversational runtime (`src/ragbot/` in this repo)
- **Ragenie** — procedural runtime (separate repo)

Runtime-specific orchestration, demo modes, API request/response shapes,
and CLI surfaces live in the runtime package, not here. If a feature is
useful to more than one runtime, it belongs in `synthesis_engine`.
