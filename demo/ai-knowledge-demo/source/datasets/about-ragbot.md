# About Ragbot

Ragbot is an open-source AI assistant that augments large language models
with a personal knowledge base via Retrieval-Augmented Generation (RAG).
It runs as a CLI, a FastAPI backend, and a React web UI.

## What problem does it solve?

Out-of-the-box LLMs answer well from training data but lack the user's
context: personal preferences, ongoing projects, custom procedures, and
domain-specific knowledge. Ragbot keeps that context in markdown files
the user owns, indexes them into a vector store, and retrieves the
relevant pieces at query time.

## Architecture (v3+)

- **Vector store backend** — pluggable, with PostgreSQL + pgvector as
  the default and embedded Qdrant as an opt-in fallback.
- **LLM backend** — also pluggable, with LiteLLM as the default and a
  direct-SDK backend (Anthropic + OpenAI + google-genai) as an
  alternative for users who want a smaller dependency surface.
- **Discovery** — workspaces are discovered from a configurable list of
  AI Knowledge repositories, plus convention-based fallbacks.
- **Skills** — Agent Skills (directories containing `SKILL.md`) are
  treated as first-class content alongside runbooks. References and
  scripts inside a skill are indexed for retrieval.
- **Reasoning** — flagship models with thinking support (Claude Sonnet
  4.6, Claude Opus 4.7, GPT-5.5, GPT-5.5-pro, Gemini 3.x) are wired
  through a single `reasoning_effort` knob that LiteLLM normalises per
  provider. Per-call override via `--thinking-effort` or
  `RAGBOT_THINKING_EFFORT`.

## Who is it for?

Ragbot is most useful for someone who wants a personal AI assistant
that knows their context, runs locally or self-hosted, and can be
shaped with markdown files rather than custom code.

## How is the demo different from a real install?

The demo (which you're using right now) ships with this small bundled
workspace, hard-isolates from any real workspaces on the host, and
displays a yellow "DEMO MODE" banner in the web UI. Disable with
`unset RAGBOT_DEMO`.
