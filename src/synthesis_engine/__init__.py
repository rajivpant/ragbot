"""synthesis_engine: shared substrate library for synthesis-engineering runtimes.

This package holds the cross-runtime building blocks used by Ragbot, Ragenie,
synthesis-console, and other reference implementations of the
synthesis-engineering methodology. Application-specific code (chat orchestration,
demo mode, API request/response models, CLI entry points) stays in its own
runtime package; everything here is fair game for any synthesis runtime to import.

Public submodules:
    config       — engines.yaml loading, model/provider resolution, temperature defaults
    workspaces   — ai-knowledge-* discovery, profiles, instruction-path resolution
    keystore     — API key resolution from ~/.synthesis/, user-config helpers
    exceptions   — base error hierarchy (SynthesisError → ConfigurationError, etc.)
    models       — substrate-level Pydantic types (WorkspaceInfo, WorkspaceList, ModelInfo)
    llm          — pluggable LLM backend interface (LiteLLM, direct SDK)
    vectorstore  — pluggable vector store interface (pgvector default; ABC for swap-ins)
    skills       — Agent Skill discovery, parsing, and data model
"""
