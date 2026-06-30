"""
tests/test_hybrid_retrieval.py — Unit tests for BM25 + RRF fusion
================================================================

Tests the tokenizer, BM25Index, and Reciprocal Rank Fusion logic without
requiring the FAISS index to be loaded (keeps the test fast).
"""
import pytest
from hybrid_retrieval import tokenize, BM25Index, reciprocal_rank_fusion


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def test_tokenize_basic():
    assert "python" in tokenize("Python developer with AWS experience")


def test_tokenize_strips_stopwords():
    tokens = tokenize("the engineer is a python developer with the aws experience")
    assert "the" not in tokens
    assert "is" not in tokens
    assert "a" not in tokens
    assert "python" in tokens
    assert "aws" in tokens


def test_tokenize_protects_skill_tokens():
    """Single-letter skill tokens like 'go' and 'r' must survive stopword filtering."""
    tokens = tokenize("I code in go and r")
    assert "go" in tokens
    assert "r" in tokens


def test_tokenize_handles_empty():
    assert tokenize("") == []
    assert tokenize(None) == []


def test_tokenize_case_insensitive():
    assert tokenize("PYTHON") == tokenize("python")
    assert tokenize("React") == tokenize("react")


# ---------------------------------------------------------------------------
# BM25Index
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_candidates():
    return [
        {"id": "c1", "name": "A", "skills": ["python", "react"], "current_title": "Backend Engineer",
         "summary": "Python developer with AWS experience"},
        {"id": "c2", "name": "B", "skills": ["go", "kubernetes"], "current_title": "Senior Backend",
         "summary": "Go engineer building distributed systems"},
        {"id": "c3", "name": "C", "skills": ["python", "pytorch"], "current_title": "ML Engineer",
         "summary": "Python ML engineer specializing in pytorch and deep learning"},
    ]


def test_bm25_builds(sample_candidates):
    idx = BM25Index.build(sample_candidates)
    assert len(idx.candidate_ids) == 3
    assert idx.avg_doc_len > 0


def test_bm25_search_returns_relevant(sample_candidates):
    """Searching for 'python' should surface c1 and c3 (both mention python)."""
    idx = BM25Index.build(sample_candidates)
    results = idx.search("python developer", top_k=3)
    assert len(results) > 0
    result_ids = [r[0] for r in results]
    assert "c1" in result_ids
    assert "c3" in result_ids


def test_bm25_search_no_match_returns_empty(sample_candidates):
    idx = BM25Index.build(sample_candidates)
    results = idx.search("rust cobol fortran", top_k=3)
    # No matches → BM25 returns empty (or scores ≤ 0)
    assert len(results) == 0 or all(r[1] <= 0 for r in results)


def test_bm25_save_load(tmp_path, sample_candidates):
    """The index should round-trip through save/load."""
    idx = BM25Index.build(sample_candidates)
    idx.save(str(tmp_path))
    loaded = BM25Index.load(str(tmp_path))
    assert loaded.candidate_ids == idx.candidate_ids
    assert loaded.avg_doc_len == idx.avg_doc_len
    # Search should produce the same results
    r1 = idx.search("python", top_k=3)
    r2 = loaded.search("python", top_k=3)
    assert [r[0] for r in r1] == [r[0] for r in r2]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def test_rrf_fuses_two_rankings():
    """RRF should combine two rankings and rank items in both higher."""
    dense = [("c1", 0.9, 1), ("c2", 0.8, 2), ("c3", 0.7, 3)]
    sparse = [("c3", 5.0, 1), ("c1", 4.0, 2), ("c4", 3.0, 3)]
    fused = reciprocal_rank_fusion(dense, sparse, k=60)
    assert len(fused) == 4
    # c1 and c3 appear in both → should rank above c4 (sparse only) and c2 (dense only)
    top2_ids = [f[0] for f in fused[:2]]
    assert "c1" in top2_ids
    assert "c3" in top2_ids


def test_rrf_higher_rank_wins():
    """An item ranked #1 in both should beat an item ranked #5 in both."""
    a = [("a", 1.0, 1), ("b", 0.9, 5)]
    b = [("a", 1.0, 1), ("b", 0.9, 5)]
    fused = reciprocal_rank_fusion(a, b, k=60)
    assert fused[0][0] == "a"
    assert fused[1][0] == "b"


def test_rrf_top_k_limit():
    """RRF should respect the top_k limit."""
    dense = [(f"c{i}", 1.0, i) for i in range(1, 21)]
    sparse = [(f"c{i}", 1.0, i) for i in range(1, 21)]
    fused = reciprocal_rank_fusion(dense, sparse, top_k=5)
    assert len(fused) == 5


def test_rrf_empty_inputs():
    """RRF with empty inputs should return an empty list."""
    assert reciprocal_rank_fusion([], []) == []
