"""
Tests for Phase 4: Response Verification and CRAG

Tests the hallucination detection, confidence scoring, and corrective RAG features.
"""

import pytest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rag import (
    ClaimStatus,
    VerifiedClaim,
    VerificationResult,
    CRAGResult,
    calculate_confidence,
    verify_response,
    generate_crag_queries,
    verify_and_correct,
)


class TestClaimStatus:
    """Test the ClaimStatus enum."""

    def test_claim_status_values(self):
        """Test that all expected statuses exist."""
        assert ClaimStatus.SUPPORTED.value == "supported"
        assert ClaimStatus.UNSUPPORTED.value == "unsupported"
        assert ClaimStatus.PARTIALLY_SUPPORTED.value == "partially_supported"


class TestCalculateConfidence:
    """Test the confidence calculation function."""

    def test_all_supported(self):
        """All supported claims should give high confidence."""
        claims = [
            VerifiedClaim("Claim 1", ClaimStatus.SUPPORTED, "evidence", "reason"),
            VerifiedClaim("Claim 2", ClaimStatus.SUPPORTED, "evidence", "reason"),
            VerifiedClaim("Claim 3", ClaimStatus.SUPPORTED, "evidence", "reason"),
        ]
        confidence = calculate_confidence(claims)
        assert confidence >= 0.9  # Should be high (1.0 + 0.1 bonus, capped at 1.0)

    def test_all_unsupported(self):
        """All unsupported claims should give low confidence."""
        claims = [
            VerifiedClaim("Claim 1", ClaimStatus.UNSUPPORTED, None, "reason"),
            VerifiedClaim("Claim 2", ClaimStatus.UNSUPPORTED, None, "reason"),
        ]
        confidence = calculate_confidence(claims)
        assert confidence < 0.3  # Should be very low

    def test_mixed_claims(self):
        """Mixed claims should give medium confidence."""
        claims = [
            VerifiedClaim("Claim 1", ClaimStatus.SUPPORTED, "evidence", "reason"),
            VerifiedClaim("Claim 2", ClaimStatus.PARTIALLY_SUPPORTED, "evidence", "reason"),
            VerifiedClaim("Claim 3", ClaimStatus.UNSUPPORTED, None, "reason"),
        ]
        confidence = calculate_confidence(claims)
        assert 0.3 < confidence < 0.8  # Should be medium

    def test_empty_claims(self):
        """No claims should return 1.0 (assume grounded)."""
        confidence = calculate_confidence([])
        assert confidence == 1.0

    def test_all_partial(self):
        """All partially supported should give medium confidence."""
        claims = [
            VerifiedClaim("Claim 1", ClaimStatus.PARTIALLY_SUPPORTED, "partial", "reason"),
            VerifiedClaim("Claim 2", ClaimStatus.PARTIALLY_SUPPORTED, "partial", "reason"),
        ]
        confidence = calculate_confidence(claims)
        assert 0.5 < confidence < 0.8  # Base 0.5 + 0.1 bonus (no unsupported)

    def test_confidence_clamped(self):
        """Confidence should be clamped to [0.0, 1.0]."""
        # Many supported claims shouldn't exceed 1.0
        claims = [
            VerifiedClaim(f"Claim {i}", ClaimStatus.SUPPORTED, "evidence", "reason")
            for i in range(10)
        ]
        confidence = calculate_confidence(claims)
        assert confidence <= 1.0

        # Many unsupported claims shouldn't go below 0.0
        claims = [
            VerifiedClaim(f"Claim {i}", ClaimStatus.UNSUPPORTED, None, "reason")
            for i in range(10)
        ]
        confidence = calculate_confidence(claims)
        assert confidence >= 0.0


class TestVerifyResponse:
    """Test the verify_response function."""

    @patch('rag._call_fast_llm')
    def test_verify_supported_response(self, mock_llm):
        """Test verification of a well-grounded response."""
        mock_llm.return_value = json.dumps({
            "overall_confidence": 0.95,
            "is_grounded": True,
            "claims": [
                {
                    "claim": "The sky is blue",
                    "status": "SUPPORTED",
                    "evidence": "The context mentions the sky is blue",
                    "reasoning": "Direct match"
                }
            ],
            "suggested_corrections": []
        })

        result = verify_response(
            query="What color is the sky?",
            response="The sky is blue.",
            context="The sky appears blue due to light scattering.",
            user_model="test-model"
        )

        assert result is not None
        assert result.confidence == 0.95
        assert result.is_grounded is True
        assert len(result.claims) == 1
        assert result.claims[0].status == ClaimStatus.SUPPORTED

    @patch('rag._call_fast_llm')
    def test_verify_unsupported_response(self, mock_llm):
        """Test verification catches hallucinations."""
        mock_llm.return_value = json.dumps({
            "overall_confidence": 0.2,
            "is_grounded": False,
            "claims": [
                {
                    "claim": "The moon is made of cheese",
                    "status": "UNSUPPORTED",
                    "evidence": None,
                    "reasoning": "No evidence in context"
                }
            ],
            "suggested_corrections": ["Remove claim about cheese"]
        })

        result = verify_response(
            query="What is the moon made of?",
            response="The moon is made of cheese.",
            context="The moon is made of rock and dust.",
            user_model="test-model"
        )

        assert result is not None
        assert result.confidence == 0.2
        assert result.is_grounded is False
        assert len(result.claims) == 1
        assert result.claims[0].status == ClaimStatus.UNSUPPORTED
        assert len(result.suggested_corrections) == 1

    @patch('rag._call_fast_llm')
    def test_verify_no_response(self, mock_llm):
        """Test that empty response returns None."""
        result = verify_response(
            query="Test",
            response="",
            context="Some context",
            user_model="test-model"
        )
        assert result is None

    @patch('rag._call_fast_llm')
    def test_verify_no_context(self, mock_llm):
        """Test that empty context returns None."""
        result = verify_response(
            query="Test",
            response="Some response",
            context="",
            user_model="test-model"
        )
        assert result is None

    @patch('rag._call_fast_llm')
    def test_verify_llm_failure(self, mock_llm):
        """Test graceful handling of LLM failure."""
        mock_llm.return_value = None

        result = verify_response(
            query="Test",
            response="Some response",
            context="Some context",
            user_model="test-model"
        )
        assert result is None

    @patch('rag._call_fast_llm')
    def test_verify_invalid_json(self, mock_llm):
        """Test graceful handling of invalid JSON from LLM."""
        mock_llm.return_value = "Not valid JSON {{{{"

        result = verify_response(
            query="Test",
            response="Some response",
            context="Some context",
            user_model="test-model"
        )
        assert result is None


class TestGenerateCRAGQueries:
    """Test the CRAG query generation function."""

    @patch('rag._call_fast_llm')
    def test_generate_queries(self, mock_llm):
        """Test CRAG query generation from unsupported claims."""
        mock_llm.return_value = json.dumps({
            "queries": [
                "moon composition",
                "what is the moon made of",
                "lunar surface materials"
            ]
        })

        claims = [
            VerifiedClaim("The moon is made of cheese", ClaimStatus.UNSUPPORTED, None, "No evidence")
        ]

        queries = generate_crag_queries(
            query="What is the moon made of?",
            unsupported_claims=claims,
            user_model="test-model"
        )

        assert len(queries) == 3
        assert "moon composition" in queries

    @patch('rag._call_fast_llm')
    def test_generate_queries_empty_claims(self, mock_llm):
        """Test that empty claims returns empty queries."""
        queries = generate_crag_queries(
            query="Test",
            unsupported_claims=[],
            user_model="test-model"
        )
        assert queries == []
        mock_llm.assert_not_called()

    @patch('rag._call_fast_llm')
    def test_generate_queries_fallback(self, mock_llm):
        """Test fallback query generation when LLM fails."""
        mock_llm.return_value = None

        claims = [
            VerifiedClaim("The quick brown fox jumps over the lazy dog", ClaimStatus.UNSUPPORTED, None, "No evidence")
        ]

        queries = generate_crag_queries(
            query="Test",
            unsupported_claims=claims,
            user_model="test-model"
        )

        # Should use fallback - extract first 5 words of claim
        assert len(queries) >= 1


class TestVerifyAndCorrect:
    """Test the main verify_and_correct entry point."""

    @patch('rag.verify_response')
    def test_verification_disabled(self, mock_verify):
        """Test that verification can be disabled."""
        result = verify_and_correct(
            query="Test",
            response="Response",
            context="Context",
            workspace_name="test",
            enable_verification=False
        )

        assert result['response'] == "Response"
        assert result['confidence'] == 1.0
        assert result['is_grounded'] is True
        assert result['verification'] is None
        mock_verify.assert_not_called()

    @patch('rag.verify_response')
    def test_high_confidence_no_crag(self, mock_verify):
        """Test that high confidence doesn't trigger CRAG."""
        mock_verify.return_value = VerificationResult(
            confidence=0.95,
            is_grounded=True,
            claims=[
                VerifiedClaim("Test claim", ClaimStatus.SUPPORTED, "evidence", "reason")
            ],
            suggested_corrections=[]
        )

        result = verify_and_correct(
            query="Test",
            response="Response",
            context="Context",
            workspace_name="test",
            enable_crag=True,
            confidence_threshold=0.7
        )

        assert result['confidence'] == 0.95
        assert result['crag_used'] is False
        assert result['crag_attempts'] == 0

    @patch('rag.corrective_rag_loop')
    @patch('rag.verify_response')
    def test_low_confidence_triggers_crag(self, mock_verify, mock_crag):
        """Test that low confidence triggers CRAG when enabled."""
        mock_verify.return_value = VerificationResult(
            confidence=0.4,
            is_grounded=False,
            claims=[
                VerifiedClaim("Bad claim", ClaimStatus.UNSUPPORTED, None, "No evidence")
            ],
            suggested_corrections=["Fix the claim"]
        )

        mock_crag.return_value = CRAGResult(
            final_response="Improved response",
            confidence=0.85,
            attempts=1,
            verification_history=[],
            additional_context_used=True
        )

        result = verify_and_correct(
            query="Test",
            response="Original response",
            context="Context",
            workspace_name="test",
            enable_crag=True,
            confidence_threshold=0.7
        )

        assert result['crag_used'] is True
        assert result['response'] == "Improved response"
        assert result['confidence'] == 0.85

    @patch('rag.verify_response')
    def test_crag_disabled(self, mock_verify):
        """Test that CRAG doesn't run when disabled."""
        mock_verify.return_value = VerificationResult(
            confidence=0.4,
            is_grounded=False,
            claims=[
                VerifiedClaim("Bad claim", ClaimStatus.UNSUPPORTED, None, "No evidence")
            ],
            suggested_corrections=[]
        )

        result = verify_and_correct(
            query="Test",
            response="Response",
            context="Context",
            workspace_name="test",
            enable_crag=False,
            confidence_threshold=0.7
        )

        assert result['crag_used'] is False
        assert result['confidence'] == 0.4  # Original low confidence


class TestDataStructures:
    """Test the Phase 4 data structures."""

    def test_verified_claim(self):
        """Test VerifiedClaim dataclass."""
        claim = VerifiedClaim(
            claim="Test claim",
            status=ClaimStatus.SUPPORTED,
            evidence="Some evidence",
            reasoning="Good reasoning"
        )
        assert claim.claim == "Test claim"
        assert claim.status == ClaimStatus.SUPPORTED
        assert claim.evidence == "Some evidence"

    def test_verification_result(self):
        """Test VerificationResult dataclass."""
        result = VerificationResult(
            confidence=0.85,
            is_grounded=True,
            claims=[],
            suggested_corrections=[]
        )
        assert result.confidence == 0.85
        assert result.is_grounded is True

    def test_crag_result(self):
        """Test CRAGResult dataclass."""
        result = CRAGResult(
            final_response="Final response",
            confidence=0.9,
            attempts=2,
            verification_history=[],
            additional_context_used=True
        )
        assert result.final_response == "Final response"
        assert result.attempts == 2
        assert result.additional_context_used is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
