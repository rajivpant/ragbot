# Small RAG fixture corpus

Used by `cases/retrieval/rag_basic_question.yaml` for citation-style scoring.

## chunk-1: What is RAG?

Retrieval-Augmented Generation (RAG) is a technique that combines a retrieval
component (typically a vector store) with a generative language model. The
retrieval step pulls relevant context from a knowledge corpus at query time,
and the generation step uses that context as additional input to the model.
The pattern is widely used in production chat assistants because it grounds
the model's output in a corpus the operator controls, instead of relying
solely on the model's parametric memory.

## chunk-2: Why RAG matters

RAG mitigates two common failure modes of pure-LLM systems: (1) hallucination
on facts that are not in the training data, and (2) staleness — the model
cannot know about events that happened after its training cutoff. By
retrieving up-to-date documents at inference time, RAG narrows both gaps.

## chunk-3: When NOT to use RAG

RAG is not always the right tool. For purely creative tasks, for problems
the model already knows well from training, or for queries where retrieval
latency would dominate end-to-end response time, plain LLM inference is
often a better fit.

## chunk-4: Components of a RAG pipeline

A typical RAG pipeline contains: an indexer (chunks documents and writes
embeddings), a retriever (queries the vector store with the user prompt
embedding), an optional reranker, and a generator (the LLM that produces
the final answer). The boundary between these components is where most
RAG-system engineering attention belongs.
