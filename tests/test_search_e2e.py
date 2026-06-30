"""
tests/test_search_e2e.py — Integration test: end-to-end search on synthetic data
================================================================================

Builds a tiny 1,000-candidate index from scratch and runs a real search
against it. This is the "smoke test" that proves the whole pipeline works
end-to-end.

Marked as `slow` because it loads the sentence-transformers model (~3 sec).
Run with:  pytest tests/test_search_e2e.py -m "not slow"  to skip.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def built_index(tmp_path_factory):
    """Build a 100-candidate hybrid index once per test module."""
    # Generate 100 candidates
    candidates_jsonl = tmp_path_factory.mktemp("data") / "candidates.jsonl"
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "generate_synthetic_data.py"),
         "--count", "100", "--out", str(candidates_jsonl)],
        check=True, cwd=str(REPO_ROOT),
    )
    # Build the hybrid index
    index_dir = tmp_path_factory.mktemp("output")
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "precompute.py"),
         "--candidates", str(candidates_jsonl),
         "--output", str(index_dir),
         "--model", "mini", "--index", "flat", "--hybrid"],
        check=True, cwd=str(REPO_ROOT),
    )
    return {"index_dir": str(index_dir), "candidates": str(candidates_jsonl)}


@pytest.mark.slow
def test_search_returns_results(built_index):
    """A search against the built index should return ranked candidates."""
    from search import run_search
    results, jd, timing, _, _ = run_search(
        jd_text="Senior Backend Engineer with Go, PostgreSQL, and Kubernetes experience",
        index_dir=built_index["index_dir"],
        candidates_path=built_index["candidates"],
        top_k=10, model_key="mini", use_llm=False, llm_client=None,
        use_hybrid=True,
    )
    assert len(results) > 0
    assert len(results) <= 10
    # The top result should have a score
    assert "score_10" in results[0]
    assert 0 <= results[0]["score_10"] <= 10
    # Timing should be present
    assert "total_ms" in timing
    assert timing["total_ms"] > 0


@pytest.mark.slow
def test_search_results_are_ranked(built_index):
    """Results should be sorted by score descending."""
    from search import run_search
    results, _, _, _, _ = run_search(
        jd_text="Senior Backend Engineer with Go and PostgreSQL",
        index_dir=built_index["index_dir"],
        candidates_path=built_index["candidates"],
        top_k=10, model_key="mini", use_llm=False, llm_client=None,
        use_hybrid=True,
    )
    scores = [r["score_10"] for r in results]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.slow
def test_search_results_have_reasoning(built_index):
    """Every result should have a non-empty reasoning string."""
    from search import run_search
    results, _, _, _, _ = run_search(
        jd_text="Senior Backend Engineer",
        index_dir=built_index["index_dir"],
        candidates_path=built_index["candidates"],
        top_k=5, model_key="mini", use_llm=False, llm_client=None,
        use_hybrid=True,
    )
    for r in results:
        assert r["reasoning"]
        assert len(r["reasoning"]) > 5


@pytest.mark.slow
def test_search_results_have_skills(built_index):
    """Every result should have matched_skills and missing_skills lists."""
    from search import run_search
    results, _, _, _, _ = run_search(
        jd_text="Senior Backend Engineer with Go, PostgreSQL, Kubernetes, AWS, Kafka",
        index_dir=built_index["index_dir"],
        candidates_path=built_index["candidates"],
        top_k=5, model_key="mini", use_llm=False, llm_client=None,
        use_hybrid=True,
    )
    for r in results:
        assert isinstance(r["matched_skills"], list)
        assert isinstance(r["missing_skills"], list)


@pytest.mark.slow
def test_hybrid_and_dense_both_work(built_index):
    """Both hybrid=True and hybrid=False should return results (no crash)."""
    from search import run_search
    for hybrid in (True, False):
        results, _, _, _, _ = run_search(
            jd_text="Senior Backend Engineer with Go",
            index_dir=built_index["index_dir"],
            candidates_path=built_index["candidates"],
            top_k=5, model_key="mini", use_llm=False, llm_client=None,
            use_hybrid=hybrid,
        )
        assert len(results) > 0, f"hybrid={hybrid} returned no results"
