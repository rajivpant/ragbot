"""Eval harness for synthesis_engine.

This package contains the offline-eval scaffolding that exercises the agent
loop end-to-end against frozen fixtures. Cases are declared as YAML files
under ``cases/`` and grouped by capability:

  cases/retrieval/        — RAG retrieval correctness (citations, recall).
  cases/tool_selection/   — does the agent pick the right tool?
  cases/refusal/          — does the agent refuse out-of-bounds prompts?
  cases/multi_step_planning/ — does multi-step reasoning land on the right plan?

The runner (``tests.evals.runner``) iterates every case, executes the
appropriate evaluator, and writes a markdown scorecard. See the package
README for the full case schema.
"""
