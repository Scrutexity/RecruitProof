"""
tests/test_ranker.py — Unit tests for the MultiSignalRanker
==========================================================

Tests the 5-signal scoring rubric (Semantic 40 + Role-Fit 20 + Skills 15 +
Behavioral 15 + Career 10) and the missing-skills detection logic.
"""
import pytest
from ranker import MultiSignalRanker, generate_reasoning


@pytest.fixture
def jd():
    return {
        "title": "Senior Backend Engineer",
        "seniority": "senior",
        "required_skills": ["go", "postgresql", "kafka", "kubernetes", "aws"],
        "nice_to_have": ["graphql", "distributed systems"],
        "min_yoe": 7,
        "location": "Remote (US)",
        "remote_ok": True,
        "visa_required": True,
    }


@pytest.fixture
def strong_candidate():
    return {
        "id": "c1", "name": "Strong Cand",
        "current_title": "Senior Backend Engineer",
        "current_company": "Stripe",
        "location": "Remote (US)",
        "years_experience": 8,
        "skills": ["go", "postgresql", "kafka", "kubernetes", "aws", "distributed systems"],
        "open_to_remote": True,
        "last_active_days_ago": 3,
        "response_rate": 85,
        "previously_applied": True,
        "promotions_last_5y": 2,
        "current_tenure_years": 3.5,
        "title_progressed": True,
    }


@pytest.fixture
def weak_candidate():
    return {
        "id": "c2", "name": "Weak Cand",
        "current_title": "Junior Frontend Engineer",
        "current_company": "Small Startup",
        "location": "Tokyo, JP",
        "years_experience": 2,
        "skills": ["react", "typescript", "tailwind css"],
        "open_to_remote": False,
        "last_active_days_ago": 200,
        "response_rate": 30,
        "previously_applied": False,
        "promotions_last_5y": 0,
        "current_tenure_years": 0.4,
        "title_progressed": False,
    }


def test_strong_candidate_scores_high(jd, strong_candidate):
    """A strong candidate with all required skills + senior title should score ≥ 8."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(strong_candidate, semantic_sim=0.92)
    assert cs.score_10 >= 8.0, f"Expected ≥ 8.0, got {cs.score_10}"
    assert cs.semantic >= 0.9
    assert cs.role_fit >= 0.8
    assert cs.skills_match >= 0.7


def test_weak_candidate_scores_low(jd, weak_candidate):
    """A weak candidate with no skill overlap should score < 5."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(weak_candidate, semantic_sim=0.55)
    assert cs.score_10 < 5.0, f"Expected < 5.0, got {cs.score_10}"


def test_strong_beats_weak(jd, strong_candidate, weak_candidate):
    """Strong candidate must outscore weak candidate."""
    ranker = MultiSignalRanker(jd)
    strong_cs = ranker.score(strong_candidate, semantic_sim=0.92)
    weak_cs = ranker.score(weak_candidate, semantic_sim=0.55)
    assert strong_cs.score_10 > weak_cs.score_10


def test_missing_skills_detected(jd, strong_candidate):
    """If a candidate is missing a required skill, it should appear in missing_skills."""
    # Remove one required skill from the candidate
    cand = dict(strong_candidate)
    cand["skills"] = ["go", "postgresql", "kafka", "kubernetes"]  # missing aws
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(cand, semantic_sim=0.9)
    assert "aws" in cs.missing_skills
    assert "go" in cs.matched_skills
    assert "aws" not in cs.matched_skills


def test_full_coverage_no_missing(jd, strong_candidate):
    """A candidate with all required skills should have empty missing_skills."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(strong_candidate, semantic_sim=0.9)
    assert cs.missing_skills == [], f"Expected empty, got {cs.missing_skills}"


def test_reasoning_is_generated(jd, strong_candidate):
    """The reasoning generator should produce a non-empty string."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(strong_candidate, semantic_sim=0.92)
    cs.rank = 1
    reasoning = generate_reasoning(cs, strong_candidate, jd, use_llm=False, llm_client=None)
    assert isinstance(reasoning, str)
    assert len(reasoning) > 10
    assert strong_candidate["name"] in reasoning


def test_signals_sum_to_weighted_score(jd, strong_candidate):
    """Final score should equal the weighted sum of signals × 10 (within rounding)."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(strong_candidate, semantic_sim=0.92)
    expected = 10 * (0.4 * cs.semantic + 0.2 * cs.role_fit + 0.15 * cs.skills_match
                     + 0.15 * cs.behavioral + 0.1 * cs.career)
    assert abs(cs.score_10 - expected) < 0.5, f"Expected ~{expected:.2f}, got {cs.score_10}"


def test_seniority_band_mismatch_penalized(jd, weak_candidate):
    """A junior candidate for a senior role should have low role_fit (the
    seniority component drops to 0, but title fuzzy match can still contribute)."""
    ranker = MultiSignalRanker(jd)
    cs = ranker.score(weak_candidate, semantic_sim=0.5)
    # Junior (band 2) vs Senior (band 5) = delta 3 → seniority_score = 0.0
    # But role_fit is 50% title fuzzy + 30% seniority + 20% location, so even
    # with seniority = 0, a partial title match can push role_fit above 0.5.
    # We assert it's below 0.7 (clearly weaker than a seniority-aligned candidate
    # which would score ≥ 0.85).
    assert cs.role_fit < 0.7


def test_stale_candidate_penalized(jd):
    """A candidate inactive for >365 days should have low behavioral signal."""
    ranker = MultiSignalRanker(jd)
    stale_cand = {
        "id": "c3", "name": "Stale", "current_title": "Senior Backend Engineer",
        "current_company": "Old Co", "skills": ["go", "postgresql", "kafka", "kubernetes", "aws"],
        "last_active_days_ago": 500, "response_rate": 20,
        "promotions_last_5y": 0, "current_tenure_years": 8, "title_progressed": False,
    }
    cs = ranker.score(stale_cand, semantic_sim=0.85)
    assert cs.behavioral < 0.5
