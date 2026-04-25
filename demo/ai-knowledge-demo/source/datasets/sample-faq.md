# Sample FAQ — Demo Workspace

A small collection of question-and-answer entries the demo can retrieve
from. Useful for showing how RAG-augmented chat handles direct factual
queries.

## Q: What backends does ragbot support for vectors?

PostgreSQL with the `pgvector` extension is the default. Embedded Qdrant
is retained as an opt-in fallback for users who want zero database
setup. Selection via the `RAGBOT_VECTOR_BACKEND` env var.

## Q: What backends does ragbot support for LLM calls?

LiteLLM is the default. A direct-SDK backend (Anthropic + OpenAI +
google-genai) is available as an opt-in alternative. Selection via the
`RAGBOT_LLM_BACKEND` env var. Adding a new backend (Bifrost, Portkey,
OpenRouter, etc.) is one new file in `src/ragbot/llm/`.

## Q: How are skills different from runbooks?

A runbook is a single markdown file. A skill is a directory containing
a `SKILL.md` plus optional references and scripts. The compiler treats
skills as first-class content; the indexer chunks the full directory
tree and tags every chunk with `skill_name` for retrieval.

## Q: Can I switch models mid-conversation?

Yes. The model picker in the web UI is per-message; the LLM-specific
instructions for the new model are auto-loaded on the next call.
Conversation history carries forward.

## Q: Where does the demo data live?

In `demo/ai-knowledge-demo/` and `demo/skills/` inside the ragbot repo.
When `RAGBOT_DEMO=1`, the discovery resolver returns only those
locations and ignores everything else.
