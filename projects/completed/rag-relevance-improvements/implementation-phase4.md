# Phase 4 Implementation: Verification & Confidence

**Status:** Complete
**Started:** 2025-12-15
**Completed:** 2025-12-15
**Dependencies:** Phase 3 complete

## Overview

Phase 4 adds a verification layer that runs AFTER the LLM generates a response. This catches hallucinations, provides confidence scores, and optionally triggers corrective retrieval (CRAG).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  EXISTING PIPELINE (Phases 1-3)                                         │
│  Query → Preprocess → Search → Rerank → Context → Generate Response    │
└─────────────────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: VERIFIER STAGE                                                │
│                                                                          │
│  Inputs:                                                                │
│  • Original query                                                       │
│  • Generated response                                                   │
│  • Retrieved context (the chunks that were used)                        │
│                                                                          │
│  Process:                                                               │
│  1. Extract claims from the response                                    │
│  2. For each claim, check if it's supported by the context              │
│  3. Calculate overall confidence score                                  │
│  4. If confidence < threshold, trigger CRAG loop                        │
│                                                                          │
│  Outputs:                                                               │
│  • Verified response (may be corrected or regenerated)                  │
│  • Confidence score (0.0 - 1.0)                                         │
│  • Verification details (which claims were supported/unsupported)       │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. Response Verifier (`verify_response`)

Uses the provider's fast model to verify claims:

```python
def verify_response(
    query: str,
    response: str,
    context: str,
    user_model: Optional[str] = None
) -> VerificationResult:
    """
    Verify that a response is grounded in the retrieved context.

    Returns:
        VerificationResult with:
        - confidence: float (0.0-1.0)
        - is_grounded: bool
        - claims: list of (claim, supported, evidence)
        - suggested_fixes: list of corrections if needed
    """
```

**Verifier Prompt:**

```
You are a fact-checking assistant. Your task is to verify that the response
is grounded in the provided context.

CONTEXT:
{context}

RESPONSE TO VERIFY:
{response}

For each factual claim in the response:
1. Find supporting evidence in the context
2. Mark as SUPPORTED, UNSUPPORTED, or PARTIALLY_SUPPORTED
3. Quote the relevant evidence if found

Respond with JSON:
{
  "overall_confidence": 0.0-1.0,
  "is_grounded": true/false,
  "claims": [
    {
      "claim": "The claim text",
      "status": "SUPPORTED" | "UNSUPPORTED" | "PARTIALLY_SUPPORTED",
      "evidence": "Quote from context if found",
      "reasoning": "Why this is/isn't supported"
    }
  ],
  "suggested_corrections": ["Fix1", "Fix2"]
}
```

### 2. CRAG (Corrective RAG) Loop

If verification fails, trigger corrective retrieval:

```python
def corrective_rag_loop(
    query: str,
    original_response: str,
    verification: VerificationResult,
    context: str,
    user_model: Optional[str] = None,
    max_attempts: int = 2
) -> CRAGResult:
    """
    Attempt to correct a poorly grounded response.

    Strategy:
    1. Identify unsupported claims
    2. Generate targeted queries to find supporting evidence
    3. Retrieve additional context
    4. Regenerate response with enhanced context
    5. Re-verify
    """
```

**CRAG Flow:**

```
Initial Response (low confidence)
        │
        ▼
┌───────────────────────┐
│ Identify Unsupported  │
│ Claims                │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Generate Targeted     │
│ Search Queries        │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Additional Retrieval  │
│ (focused on gaps)     │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Regenerate Response   │
│ (with extra context)  │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Re-verify             │
│ (max N attempts)      │
└───────────────────────┘
```

### 3. Confidence Scoring

Confidence is calculated from verification results:

```python
def calculate_confidence(verification: VerificationResult) -> float:
    """
    Calculate confidence score from claim verification.

    Formula:
    - Base: (supported_claims / total_claims)
    - Penalty: -0.1 for each UNSUPPORTED claim
    - Bonus: +0.1 if no UNSUPPORTED claims

    Returns: 0.0 to 1.0
    """
```

**Confidence Levels:**

| Score | Level | Meaning |
|-------|-------|---------|
| 0.9+ | High | All claims fully supported by context |
| 0.7-0.9 | Medium | Most claims supported, minor gaps |
| 0.5-0.7 | Low | Significant unsupported claims |
| <0.5 | Very Low | Response may contain hallucinations |

### 4. Integration Point

The verification happens in the API/chat layer, after response generation:

```python
# In api/main.py or core chat function

async def chat_with_verification(
    prompt: str,
    workspace: str,
    model: str,
    enable_verification: bool = True,
    enable_crag: bool = True,
    confidence_threshold: float = 0.7
) -> ChatResponse:
    """
    Chat with optional verification and CRAG.

    Flow:
    1. Get relevant context (existing Phase 1-3)
    2. Generate response (existing)
    3. If enable_verification:
       a. Verify response against context
       b. If confidence < threshold and enable_crag:
          - Run CRAG loop
       c. Include confidence in response
    """
```

## Data Structures

```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class ClaimStatus(Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PARTIALLY_SUPPORTED = "partially_supported"

@dataclass
class VerifiedClaim:
    claim: str
    status: ClaimStatus
    evidence: Optional[str]
    reasoning: str

@dataclass
class VerificationResult:
    confidence: float  # 0.0 to 1.0
    is_grounded: bool
    claims: List[VerifiedClaim]
    suggested_corrections: List[str]

@dataclass
class CRAGResult:
    final_response: str
    confidence: float
    attempts: int
    verification_history: List[VerificationResult]
    additional_context_used: bool
```

## API Changes

### Response Format Update

```python
# Before Phase 4
{
    "content": "The response text...",
    "model": "claude-sonnet-4",
    "workspace": "personal"
}

# After Phase 4
{
    "content": "The response text...",
    "model": "claude-sonnet-4",
    "workspace": "personal",
    "verification": {
        "confidence": 0.85,
        "is_grounded": true,
        "claims_checked": 5,
        "claims_supported": 4,
        "crag_attempts": 0
    }
}
```

### New Settings

```python
# In ~/.config/ragbot/config.yaml or API request
verification:
  enabled: true           # Enable/disable verification
  confidence_threshold: 0.7  # Below this triggers CRAG
  max_crag_attempts: 2    # Maximum correction attempts
  show_claims: false      # Include per-claim details in response
```

## Implementation Steps

### Step 1: Verifier Function ✅ Complete
- [x] Create `verify_response()` in rag.py
- [x] Implement claim extraction via LLM
- [x] Implement evidence matching
- [x] Calculate confidence score

### Step 2: CRAG Loop ✅ Complete
- [x] Create `corrective_rag_loop()` in rag.py
- [x] Implement targeted query generation for gaps
- [x] Implement additional retrieval
- [x] Implement response regeneration
- [x] Add attempt limiting

### Step 3: Integration ✅ Complete
- [x] Add `verify_and_correct()` main entry point
- [x] Update response format with confidence
- [x] Add verification settings as function parameters

### Step 4: Frontend (Future)
- [ ] Display confidence indicator in UI
- [ ] Show verification status
- [ ] Allow toggling verification on/off

### Step 5: Tests ✅ Complete
- [x] Unit tests for verify_response (6 tests)
- [x] Unit tests for CRAG loop (3 tests)
- [x] Unit tests for confidence calculation (7 tests)
- [x] Unit tests for main entry point (4 tests)
- [x] Edge cases (empty context, no claims, etc.) (3 tests)
- [x] Total: 23 tests, all passing

## Performance Considerations

| Component | Estimated Latency | Notes |
|-----------|-------------------|-------|
| Claim extraction | ~100-200ms | Fast model, small prompt |
| Evidence matching | ~50-100ms | String matching, fast |
| Confidence calc | <10ms | Simple math |
| CRAG (if needed) | ~500-1500ms | Extra retrieval + regeneration |

**Total overhead (verification only):** ~150-300ms
**Total overhead (with CRAG):** ~700-2000ms

CRAG only triggers when confidence < threshold, so most requests won't incur CRAG latency.

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Hallucination rate | <5% | Manual review of 100 responses |
| Confidence accuracy | >80% | Compare confidence to human judgment |
| CRAG trigger rate | <20% | Log when CRAG activates |
| CRAG success rate | >70% | Does CRAG improve confidence? |

## Testing Strategy

1. **Known Good Responses**: Generate responses we know are grounded, verify they get high confidence
2. **Known Bad Responses**: Inject hallucinations, verify they get low confidence
3. **Edge Cases**: Empty context, very long responses, opinion questions
4. **CRAG Effectiveness**: Compare responses before/after CRAG

## Rollout Plan

1. **Phase 4a**: Verification only (no CRAG), optional via flag
2. **Phase 4b**: Add CRAG loop, default off
3. **Phase 4c**: Enable by default for all requests
