"""Unit tests for RAG Phase 1 improvements.

Tests for:
- Query preprocessing (contraction expansion, document detection)
- Full document retrieval
- Enhanced search with preprocessing
- Increased context budget (16K tokens)

Run with: pytest tests/test_rag_phase1.py -v
"""

import pytest
import os
import sys

# Add src directory to path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


class TestContractionExpansion:
    """Tests for contraction expansion functionality."""

    def test_expand_basic_contractions(self):
        """Basic contractions should be expanded."""
        from rag import expand_contractions

        assert expand_contractions("what's in my biography") == "what is in my biography"
        assert expand_contractions("where's the document") == "where is the document"
        assert expand_contractions("it's important") == "it is important"

    def test_expand_negative_contractions(self):
        """Negative contractions should be expanded."""
        from rag import expand_contractions

        assert expand_contractions("I can't find it") == "i cannot find it"
        assert expand_contractions("don't do that") == "do not do that"
        assert expand_contractions("won't work") == "will not work"

    def test_expand_pronoun_contractions(self):
        """Pronoun contractions should be expanded."""
        from rag import expand_contractions

        assert expand_contractions("I'm ready") == "i am ready"
        assert expand_contractions("you're here") == "you are here"
        assert expand_contractions("we've done it") == "we have done it"

    def test_preserve_non_contractions(self):
        """Non-contraction text should be preserved."""
        from rag import expand_contractions

        # Regular text without contractions
        assert expand_contractions("show me the biography") == "show me the biography"
        assert expand_contractions("read this file") == "read this file"

    def test_lowercase_output(self):
        """Output should be lowercase."""
        from rag import expand_contractions

        assert expand_contractions("What's IN MY Biography") == "what is in my biography"

    def test_multiple_contractions(self):
        """Multiple contractions in one query should all be expanded."""
        from rag import expand_contractions

        result = expand_contractions("I'm sure it's what we're looking for")
        assert "i am" in result
        assert "it is" in result
        assert "we are" in result


class TestDocumentRequestDetection:
    """Tests for detecting document lookup requests."""

    def test_detect_show_me_pattern(self):
        """'Show me X' patterns should be detected as document requests."""
        from rag import detect_document_request

        is_doc, hint = detect_document_request("show me my biography")
        assert is_doc is True
        assert hint == "biography"

        is_doc, hint = detect_document_request("show me the author bios")
        assert is_doc is True
        assert "author" in hint or "bios" in hint

    def test_detect_whats_in_pattern(self):
        """'What's in X' patterns should be detected as document requests."""
        from rag import detect_document_request

        is_doc, hint = detect_document_request("what's in my biography")
        assert is_doc is True
        assert hint == "biography"

        is_doc, hint = detect_document_request("what is in the config file")
        assert is_doc is True
        assert "config" in hint

    def test_detect_use_runbook_pattern(self):
        """'Use X runbook' patterns should be detected as document requests."""
        from rag import detect_document_request

        is_doc, hint = detect_document_request("use the author-bios runbook")
        assert is_doc is True
        assert "author" in hint or "bios" in hint

    def test_detect_display_pattern(self):
        """'Display X' patterns should be detected as document requests."""
        from rag import detect_document_request

        is_doc, hint = detect_document_request("display my resume")
        assert is_doc is True
        assert hint == "resume"

    def test_general_questions_not_detected(self):
        """General questions should NOT be detected as document requests."""
        from rag import detect_document_request

        is_doc, hint = detect_document_request("How do I write a blog post?")
        assert is_doc is False

        is_doc, hint = detect_document_request("What are the best practices for coding?")
        assert is_doc is False

        is_doc, hint = detect_document_request("Tell me about machine learning")
        assert is_doc is False


class TestQueryPreprocessing:
    """Tests for the full query preprocessing pipeline."""

    def test_preprocess_document_request(self):
        """Document requests should be fully preprocessed."""
        from rag import preprocess_query

        result = preprocess_query("what's in my biography")

        assert result['original_query'] == "what's in my biography"
        assert result['processed_query'] == "what is in my biography"
        assert result['is_document_request'] is True
        assert result['document_hint'] == "biography"
        assert "biography" in result['search_terms']

    def test_preprocess_general_query(self):
        """General queries should be preprocessed without document flag."""
        from rag import preprocess_query

        result = preprocess_query("How do I write a blog post?")

        assert result['is_document_request'] is False
        assert result['document_hint'] is None
        assert "write" in result['search_terms'] or "blog" in result['search_terms']

    def test_search_terms_exclude_stop_words(self):
        """Search terms should exclude common stop words."""
        from rag import preprocess_query

        result = preprocess_query("show me the biography of my family")

        # Stop words like 'the', 'my', 'of', 'me', 'show' should be excluded
        stop_words_found = [w for w in result['search_terms']
                           if w in {'the', 'my', 'of', 'me', 'show', 'a', 'an'}]
        assert len(stop_words_found) == 0

        # But meaningful terms should remain
        assert "biography" in result['search_terms'] or "family" in result['search_terms']


class TestSearchWithPreprocessing:
    """Tests for search function with preprocessing.

    Note: These tests require RAG infrastructure (Qdrant, embeddings).
    They are skipped if RAG is not available.
    """

    @pytest.fixture
    def check_rag_available(self):
        """Check if RAG infrastructure is available."""
        from rag import is_rag_available
        if not is_rag_available():
            pytest.skip("RAG not available (Qdrant/embeddings not installed)")

    def test_search_uses_preprocessing(self, check_rag_available):
        """Search should use query preprocessing by default."""
        from rag import search

        # This test verifies the function accepts the preprocessing parameter
        # Actual results depend on indexed content
        results = search("test_workspace", "what's in my biography", limit=5, use_preprocessing=True)
        # Should not raise an error
        assert isinstance(results, list)

    def test_search_can_disable_preprocessing(self, check_rag_available):
        """Search should work with preprocessing disabled."""
        from rag import search

        results = search("test_workspace", "what's in my biography", limit=5, use_preprocessing=False)
        assert isinstance(results, list)


class TestContextBudget:
    """Tests for the increased context budget."""

    def test_default_context_budget_is_16k(self):
        """Default context budget should be 16000 tokens."""
        from rag import get_relevant_context
        import inspect

        # Check the default value in the function signature
        sig = inspect.signature(get_relevant_context)
        max_tokens_param = sig.parameters.get('max_tokens')
        assert max_tokens_param is not None
        assert max_tokens_param.default == 16000

    def test_core_default_rag_budget_is_16k(self):
        """Core chat function should default to 16K RAG tokens."""
        import inspect
        from ragbot.core import chat

        sig = inspect.signature(chat)
        rag_max_tokens_param = sig.parameters.get('rag_max_tokens')
        assert rag_max_tokens_param is not None
        assert rag_max_tokens_param.default == 16000


class TestFullDocumentRetrieval:
    """Tests for full document retrieval functionality.

    Note: These tests require RAG infrastructure and indexed content.
    """

    def test_find_full_document_returns_correct_structure(self):
        """find_full_document should return correct structure or None."""
        from rag import find_full_document, is_rag_available

        if not is_rag_available():
            pytest.skip("RAG not available")

        # Test with a non-existent workspace (should return None gracefully)
        result = find_full_document("nonexistent_workspace", "biography", ["biography"])

        # Should return None for non-existent workspace, not raise an error
        assert result is None or isinstance(result, dict)

        if result is not None:
            # If it returns something, verify structure
            assert 'content' in result
            assert 'filename' in result
            assert 'source_file' in result


class TestDocumentLookupPatterns:
    """Tests for the document lookup pattern matching."""

    def test_all_patterns_work(self):
        """All defined patterns should work correctly."""
        from rag import detect_document_request

        test_cases = [
            ("show me my biography", True, "biography"),
            ("show the readme", True, "readme"),
            ("display my resume", True, "resume"),
            ("get me the config", True, "config"),
            ("read my notes", True, "notes"),
            ("open the manual", True, "manual"),
            ("use the deploy runbook", True, "deploy"),
            ("what's in my biography", True, "biography"),
            ("what is in the readme", True, "readme"),
            ("what does my config say", True, "config"),
        ]

        for query, expected_is_doc, expected_in_hint in test_cases:
            is_doc, hint = detect_document_request(query)
            assert is_doc == expected_is_doc, f"Failed for: {query}"
            if expected_in_hint:
                assert hint is not None, f"Expected hint for: {query}"
                assert expected_in_hint in hint.lower(), f"Expected '{expected_in_hint}' in hint for: {query}, got: {hint}"


class TestIntegration:
    """Integration tests that verify the full pipeline."""

    def test_whats_in_my_biography_query(self):
        """The problematic 'what's in my biography' query should be handled correctly."""
        from rag import preprocess_query

        result = preprocess_query("what's in my biography")

        # Should detect as document request
        assert result['is_document_request'] is True

        # Should extract 'biography' as the document hint
        assert result['document_hint'] == "biography"

        # Should have 'biography' in search terms
        assert "biography" in result['search_terms']

        # Contraction should be expanded
        assert "what is" in result['processed_query']
        assert "what's" not in result['processed_query']

    def test_show_me_my_biography_query(self):
        """The 'show me my biography' query should be handled correctly."""
        from rag import preprocess_query

        result = preprocess_query("show me my biography")

        assert result['is_document_request'] is True
        assert result['document_hint'] == "biography"
        assert "biography" in result['search_terms']


# Marker for expensive tests that require full infrastructure
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "requires_rag: marks tests as requiring RAG infrastructure"
    )
