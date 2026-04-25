# AI Assistants — A Brief Overview

A general-purpose primer used by the demo so RAG queries about AI
assistants have something concrete to retrieve.

## The basic shape

A modern AI assistant is a large language model wrapped by:

1. **Custom instructions** — a system prompt that defines tone, persona,
   and conventions.
2. **A knowledge layer** — either uploaded documents, a connected
   filesystem, or a retrieval index over a curated corpus.
3. **A tool layer** — function calls or MCP servers that let the
   assistant act on the world (read files, send emails, run scripts).

## Why retrieval matters

Even with large context windows, dumping every potentially-relevant
document into every prompt wastes tokens and increases latency. A
retrieval step picks the few pieces most relevant to the current
question and includes only those, which is cheaper and usually more
accurate than stuffing the whole corpus.

## Hybrid retrieval

Vector search (embeddings + cosine similarity) finds semantically
similar content but can miss exact-term matches. Keyword search (BM25,
or Postgres full-text search) finds exact-term matches but misses
semantic equivalents. Hybrid retrieval runs both and merges the
rankings — typically with reciprocal rank fusion — for results that
are accurate on both axes.

## Personal vs general

A general-purpose assistant (web ChatGPT, Gemini, etc.) is trained on
a broad corpus and answers from that. A personal assistant adds the
user's own context: preferences, ongoing work, custom procedures,
domain knowledge. The retrieval layer is what makes "personal"
practical; without it, the assistant is just the base model with a
short custom prompt.
