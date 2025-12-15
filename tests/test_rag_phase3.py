"""Tests for RAG Phase 3 features.

Phase 3 adds advanced retrieval:
- BM25/keyword search alongside vector search
- Reciprocal Rank Fusion (RRF) for result merging
- LLM-based reranking with provider's fast model

These tests verify:
1. BM25 tokenization and indexing
2. BM25 search functionality
3. Reciprocal Rank Fusion algorithm
4. LLM reranking with fallback
5. Hybrid search combining vector + BM25
"""

import pytest
from unittest.mock import patch, MagicMock

# Import functions to test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rag import (
    bm25_tokenize,
    BM25Index,
    reciprocal_rank_fusion,
    rerank_with_llm,
    hybrid_search,
    RERANKER_PROMPT,
)


class TestBM25Tokenize:
    """Tests for BM25 tokenization."""

    def test_tokenize_basic_text(self):
        """Should tokenize basic text into words."""
        tokens = bm25_tokenize("Hello world this is a test")
        assert 'hello' in tokens
        assert 'world' in tokens
        assert 'test' in tokens

    def test_tokenize_removes_stop_words(self):
        """Should remove common stop words."""
        tokens = bm25_tokenize("the quick brown fox jumps and the lazy dog")
        assert 'the' not in tokens
        assert 'and' not in tokens
        assert 'quick' in tokens
        assert 'brown' in tokens
        assert 'fox' in tokens

    def test_tokenize_handles_punctuation(self):
        """Should handle punctuation correctly."""
        tokens = bm25_tokenize("Hello, world! How are you?")
        assert 'hello' in tokens
        assert 'world' in tokens
        # Punctuation should be stripped

    def test_tokenize_removes_short_tokens(self):
        """Should remove very short tokens (1 char)."""
        tokens = bm25_tokenize("I a the quick brown")
        # "I" and "a" should be removed (stop words or too short)
        assert 'quick' in tokens
        assert 'brown' in tokens

    def test_tokenize_lowercase(self):
        """Should convert to lowercase."""
        tokens = bm25_tokenize("HELLO World TEST")
        assert 'hello' in tokens
        assert 'world' in tokens
        assert 'test' in tokens
        assert 'HELLO' not in tokens

    def test_tokenize_handles_numbers(self):
        """Should include alphanumeric tokens."""
        tokens = bm25_tokenize("version 2.0 has 100 features")
        assert 'version' in tokens
        assert '100' in tokens


class TestBM25Index:
    """Tests for BM25Index class."""

    def test_add_documents(self):
        """Should add documents to the index."""
        index = BM25Index()
        docs = [
            {'text': 'Hello world', 'metadata': {'filename': 'test1.md'}},
            {'text': 'Goodbye world', 'metadata': {'filename': 'test2.md'}},
        ]
        index.add_documents(docs)

        assert len(index.documents) == 2
        assert len(index.doc_tokens) == 2
        assert index.avg_doc_length > 0

    def test_search_returns_results(self):
        """Should return search results."""
        index = BM25Index()
        docs = [
            {'text': 'Python programming language', 'metadata': {'filename': 'python.md'}},
            {'text': 'JavaScript web development', 'metadata': {'filename': 'js.md'}},
            {'text': 'Python data science', 'metadata': {'filename': 'data.md'}},
        ]
        index.add_documents(docs)

        results = index.search("python programming")

        assert len(results) > 0
        # Python docs should rank higher
        filenames = [r[0]['metadata']['filename'] for r in results]
        assert 'python.md' in filenames or 'data.md' in filenames

    def test_search_empty_query(self):
        """Should handle empty query."""
        index = BM25Index()
        docs = [{'text': 'Hello world', 'metadata': {}}]
        index.add_documents(docs)

        results = index.search("")
        assert results == []

    def test_search_no_matches(self):
        """Should return empty for no matches."""
        index = BM25Index()
        docs = [{'text': 'Hello world', 'metadata': {}}]
        index.add_documents(docs)

        results = index.search("xyz123nonexistent")
        assert results == []

    def test_search_respects_limit(self):
        """Should respect result limit."""
        index = BM25Index()
        docs = [
            {'text': f'Document {i} about python', 'metadata': {'filename': f'doc{i}.md'}}
            for i in range(20)
        ]
        index.add_documents(docs)

        results = index.search("python", limit=5)
        assert len(results) <= 5

    def test_index_includes_filename_title(self):
        """Should include filename and title in index."""
        index = BM25Index()
        docs = [
            {
                'text': 'Content about programming',
                'metadata': {'filename': 'biography.md', 'title': 'My Biography'}
            },
        ]
        index.add_documents(docs)

        # Search for filename should find the document
        results = index.search("biography")
        assert len(results) > 0


class TestReciprocalRankFusion:
    """Tests for Reciprocal Rank Fusion."""

    def test_rrf_basic_merge(self):
        """Should merge two result lists."""
        list1 = [
            ({'metadata': {'filename': 'a.md', 'char_start': 0}}, 0.9),
            ({'metadata': {'filename': 'b.md', 'char_start': 0}}, 0.8),
        ]
        list2 = [
            ({'metadata': {'filename': 'b.md', 'char_start': 0}}, 0.95),
            ({'metadata': {'filename': 'c.md', 'char_start': 0}}, 0.85),
        ]

        merged = reciprocal_rank_fusion([list1, list2])

        # b.md appears in both lists, should rank higher
        filenames = [r[0]['metadata']['filename'] for r in merged]
        assert 'b.md' in filenames
        assert 'a.md' in filenames
        assert 'c.md' in filenames

    def test_rrf_empty_lists(self):
        """Should handle empty lists."""
        merged = reciprocal_rank_fusion([[], []])
        assert merged == []

    def test_rrf_single_list(self):
        """Should handle single list."""
        list1 = [
            ({'metadata': {'filename': 'a.md', 'char_start': 0}}, 0.9),
        ]

        merged = reciprocal_rank_fusion([list1])
        assert len(merged) == 1

    def test_rrf_preserves_documents(self):
        """Should preserve document content."""
        list1 = [
            ({'text': 'Hello', 'metadata': {'filename': 'a.md', 'char_start': 0}}, 0.9),
        ]

        merged = reciprocal_rank_fusion([list1])
        assert merged[0][0]['text'] == 'Hello'

    def test_rrf_boosts_documents_in_multiple_lists(self):
        """Documents in multiple lists should rank higher."""
        # Create lists where 'shared.md' appears in all, 'unique.md' in only one
        lists = [
            [
                ({'metadata': {'filename': 'shared.md', 'char_start': 0}}, 0.5),
                ({'metadata': {'filename': 'unique1.md', 'char_start': 0}}, 0.9),
            ],
            [
                ({'metadata': {'filename': 'shared.md', 'char_start': 0}}, 0.5),
                ({'metadata': {'filename': 'unique2.md', 'char_start': 0}}, 0.9),
            ],
            [
                ({'metadata': {'filename': 'shared.md', 'char_start': 0}}, 0.5),
                ({'metadata': {'filename': 'unique3.md', 'char_start': 0}}, 0.9),
            ],
        ]

        merged = reciprocal_rank_fusion(lists)

        # shared.md should be first (appears in all 3 lists)
        assert merged[0][0]['metadata']['filename'] == 'shared.md'


class TestRerankerPrompt:
    """Tests for reranker prompt template."""

    def test_reranker_prompt_has_required_placeholders(self):
        """Reranker prompt should have all required placeholders."""
        assert '{query}' in RERANKER_PROMPT
        assert '{chunks}' in RERANKER_PROMPT
        assert '{num_chunks}' in RERANKER_PROMPT

    def test_reranker_prompt_requests_scores(self):
        """Reranker prompt should request relevance scores."""
        assert 'score' in RERANKER_PROMPT.lower()
        assert '0-10' in RERANKER_PROMPT or '0 to 10' in RERANKER_PROMPT.lower()

    def test_reranker_prompt_describes_scale(self):
        """Reranker prompt should describe scoring scale."""
        assert 'relevant' in RERANKER_PROMPT.lower()
        assert 'not relevant' in RERANKER_PROMPT.lower() or '0-2' in RERANKER_PROMPT


class TestRerankWithLLM:
    """Tests for LLM-based reranking."""

    def test_rerank_returns_results_when_llm_fails(self):
        """Should return original results when LLM unavailable."""
        results = [
            {'text': 'Doc 1', 'score': 0.9, 'metadata': {}},
            {'text': 'Doc 2', 'score': 0.8, 'metadata': {}},
        ]

        with patch('rag._call_fast_llm', return_value=None):
            reranked = rerank_with_llm("test query", results)

        # Should return same results
        assert len(reranked) == 2
        assert reranked[0]['text'] == 'Doc 1'

    def test_rerank_applies_llm_scores(self):
        """Should apply LLM scores when available."""
        results = [
            {'text': 'Doc 1', 'score': 0.9, 'metadata': {}},
            {'text': 'Doc 2', 'score': 0.8, 'metadata': {}},
        ]

        mock_response = '{"scores": [5, 9]}'

        with patch('rag._call_fast_llm', return_value=mock_response):
            reranked = rerank_with_llm("test query", results)

        # Doc 2 should now rank higher (LLM score 9 vs 5)
        assert reranked[0]['llm_score'] == 9
        assert reranked[1]['llm_score'] == 5

    def test_rerank_handles_markdown_json(self):
        """Should handle JSON wrapped in markdown."""
        results = [
            {'text': 'Doc 1', 'score': 0.9, 'metadata': {}},
        ]

        mock_response = '```json\n{"scores": [8]}\n```'

        with patch('rag._call_fast_llm', return_value=mock_response):
            reranked = rerank_with_llm("test query", results)

        assert reranked[0]['llm_score'] == 8

    def test_rerank_respects_top_k(self):
        """Should only rerank top_k results."""
        results = [
            {'text': f'Doc {i}', 'score': 0.9 - i*0.1, 'metadata': {}}
            for i in range(10)
        ]

        mock_response = '{"scores": [9, 8, 7]}'  # Only 3 scores

        with patch('rag._call_fast_llm', return_value=mock_response):
            reranked = rerank_with_llm("test query", results, top_k=3)

        # First 3 should have LLM scores
        assert reranked[0].get('llm_score') is not None
        # Rest should not have LLM scores
        assert reranked[5].get('llm_score') is None

    def test_rerank_handles_invalid_json(self):
        """Should handle invalid JSON gracefully."""
        results = [
            {'text': 'Doc 1', 'score': 0.9, 'metadata': {}},
        ]

        mock_response = 'not valid json'

        with patch('rag._call_fast_llm', return_value=mock_response):
            reranked = rerank_with_llm("test query", results)

        # Should return results with null LLM score
        assert reranked[0].get('llm_score') is None

    def test_rerank_empty_results(self):
        """Should handle empty results."""
        reranked = rerank_with_llm("test query", [])
        assert reranked == []


class TestHybridSearch:
    """Tests for hybrid search function."""

    def test_hybrid_search_without_bm25(self):
        """Should work without BM25 (vector only)."""
        with patch('rag.search') as mock_search:
            mock_search.return_value = [
                {'text': 'Result 1', 'score': 0.9, 'metadata': {'filename': 'a.md', 'char_start': 0}}
            ]
            with patch('rag._get_qdrant_client', return_value=None):
                results = hybrid_search('test_workspace', 'query', use_bm25=False)

        assert len(results) == 1
        mock_search.assert_called_once()

    def test_hybrid_search_handles_missing_collection(self):
        """Should gracefully handle missing collection."""
        with patch('rag.search') as mock_search:
            mock_search.return_value = []
            with patch('rag._get_qdrant_client', return_value=None):
                results = hybrid_search('nonexistent', 'query')

        assert results == []


class TestIntegration:
    """Integration tests for Phase 3 features."""

    def test_bm25_finds_exact_matches(self):
        """BM25 should find documents with exact keyword matches."""
        index = BM25Index()
        docs = [
            {'text': 'Machine learning algorithms', 'metadata': {'filename': 'ml.md'}},
            {'text': 'Deep learning neural networks', 'metadata': {'filename': 'dl.md'}},
            {'text': 'Biography of a person', 'metadata': {'filename': 'bio.md'}},
        ]
        index.add_documents(docs)

        results = index.search("biography")

        # Biography doc should be found
        assert len(results) > 0
        filenames = [r[0]['metadata']['filename'] for r in results]
        assert 'bio.md' in filenames

    def test_rrf_improves_coverage(self):
        """RRF should combine results from multiple sources."""
        # Simulate vector search favoring semantic similarity
        vector_results = [
            ({'metadata': {'filename': 'semantic.md', 'char_start': 0}}, 0.9),
            ({'metadata': {'filename': 'both.md', 'char_start': 0}}, 0.7),
        ]

        # Simulate BM25 favoring keyword matches
        bm25_results = [
            ({'metadata': {'filename': 'keyword.md', 'char_start': 0}}, 2.5),
            ({'metadata': {'filename': 'both.md', 'char_start': 0}}, 1.8),
        ]

        merged = reciprocal_rank_fusion([vector_results, bm25_results])

        # Both.md should rank high (appears in both)
        filenames = [r[0]['metadata']['filename'] for r in merged]
        assert 'both.md' in filenames[:2]  # Should be in top 2

        # All three documents should be present
        assert 'semantic.md' in filenames
        assert 'keyword.md' in filenames


class TestFallbackBehavior:
    """Tests for graceful degradation."""

    def test_hybrid_search_falls_back_to_vector(self):
        """Should fall back to vector search when BM25 fails."""
        mock_vector_results = [
            {'text': 'Result', 'score': 0.9, 'metadata': {'filename': 'test.md', 'char_start': 0}}
        ]

        with patch('rag.search', return_value=mock_vector_results):
            with patch('rag._get_qdrant_client', return_value=None):  # BM25 will fail
                results = hybrid_search('test', 'query')

        # Should still return vector results
        assert len(results) == 1

    def test_rerank_preserves_order_on_failure(self):
        """Reranking should preserve original order on LLM failure."""
        results = [
            {'text': 'First', 'score': 0.9, 'metadata': {}},
            {'text': 'Second', 'score': 0.8, 'metadata': {}},
            {'text': 'Third', 'score': 0.7, 'metadata': {}},
        ]

        with patch('rag._call_fast_llm', return_value=None):
            reranked = rerank_with_llm("query", results)

        # Order should be preserved
        assert reranked[0]['text'] == 'First'
        assert reranked[1]['text'] == 'Second'
        assert reranked[2]['text'] == 'Third'
