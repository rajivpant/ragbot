# Lessons Learned: RAG Phase 2 - Provider-Agnostic Design

**Date:** 2025-12-15
**Project:** RAG Relevance Improvements
**Phase:** Phase 2 Query Intelligence

## Summary

Successfully implemented RAG Phase 2 with provider-agnostic model selection. Key insight: use configuration-based categories instead of hardcoded model names.

## Key Lessons

### 1. Model Categories > Hardcoded Names

**The Request:**
User explicitly said: "Don't hardcode model names like haiku - use model categories from engines.yaml."

**The Implementation:**
```python
# BAD: Hardcoded model name
fast_model = "anthropic/claude-haiku-4-5-20251001"

# GOOD: Category-based selection
fast_model = get_fast_model_for_provider(user_model)
```

**Why It Matters:**
- Ragbot supports multiple LLM providers (Anthropic, OpenAI, Google)
- Users can switch models mid-conversation
- API keys are provider-specific
- Billing should be consistent (don't charge OpenAI user for Anthropic calls)

**The Solution:**
engines.yaml already had categories (`small`, `medium`, `large`). Added:
```python
def get_model_by_category(provider, category):
    """Get model for provider by category."""

def get_fast_model_for_provider(model_id):
    """Get fast model for same provider as given model."""
```

**Result:**
- Anthropic → claude-haiku-4-5-20251001
- OpenAI → gpt-5-mini
- Google → gemini-2.5-flash-lite

### 2. Configuration Already Had What We Needed

**The Insight:**
Before adding new code, check existing configuration. engines.yaml already defined:
```yaml
anthropic:
  models:
    - id: anthropic/claude-haiku-4-5-20251001
      category: small  # <-- Already there!
```

The category system was already designed for exactly this use case. We just needed to expose it through helper functions.

**Lesson:**
Don't reinvent - leverage existing architecture.

### 3. Graceful Fallback is Non-Negotiable

**Design Principle:**
Phase 2 LLM features should enhance RAG, not break it.

**Implementation:**
Every Phase 2 function has a fallback path:
```python
def plan_query(query, user_model, workspace):
    # Try LLM-based planning
    response = _call_fast_llm(prompt, user_model, workspace)
    if response:
        # Use LLM plan
        ...
    else:
        # Fallback to Phase 1 heuristics
        return preprocess_query(query)
```

**Result:**
- LLM available → Full Phase 2 intelligence
- LLM unavailable → Phase 1 heuristics (still better than pre-Phase-1)
- Never fails completely

### 4. API Key Resolution Follows Provider

**The Challenge:**
When user selects "claude-opus", auxiliary calls should also use Anthropic API key, not OpenAI's.

**The Solution:**
1. Get user's model provider: `provider = get_provider_for_model(user_model)`
2. Get fast model for same provider: `fast_model = get_fast_model_for_provider(user_model)`
3. Get API key for provider: `api_key = get_api_key(api_key_name, workspace)`

**Why It Works:**
- Consistent billing (one provider per conversation)
- Consistent rate limits (same account)
- User controls which providers they use

### 5. JSON Parsing Needs Robustness

**The Problem:**
LLMs sometimes return JSON wrapped in markdown:
```
```json
{"key": "value"}
```
```

**The Solution:**
```python
json_str = response
if '```json' in json_str:
    json_str = json_str.split('```json')[1].split('```')[0]
elif '```' in json_str:
    json_str = json_str.split('```')[1].split('```')[0]
plan = json.loads(json_str.strip())
```

**Lesson:**
LLM output is variable - always handle common variations.

## What Would I Do Differently?

1. **Check existing config first** - The category system was already in engines.yaml. Spent time thinking about architecture that was already designed.

2. **Test with multiple providers earlier** - Initially tested only with Anthropic. Multi-provider testing revealed the importance of API key consistency.

## Metrics to Track

For future evaluation:
- Planner accuracy: % of queries correctly classified by type
- Multi-query coverage: Do expanded queries find more relevant docs?
- HyDE effectiveness: Compare with/without HyDE for factual queries
- Provider consistency: Are auxiliary calls using correct provider?

## Related Documents

- [implementation-phase2.md](../active/rag-relevance-improvements/implementation-phase2.md)
- [2025-12-15-rag-phase1-insights.md](2025-12-15-rag-phase1-insights.md)
