"""
tests/test_jd_parser.py — Unit tests for the JD parser
=====================================================

Tests extraction of title, seniority, required vs. nice-to-have skills,
min YoE, location, and remote/visa flags from free-form JD text.
"""
import pytest
from jd_parser import parse_jd


SAMPLE_JD = """Senior Backend Engineer, Payments

Location: Remote (US)

We're building payment infrastructure. You'll work on distributed systems in Go.

Requirements:
- 7+ years of experience in backend engineering
- Strong Go or equivalent systems language experience
- Deep PostgreSQL experience
- Distributed systems fundamentals
- Kubernetes and AWS experience

Nice to have:
- Kafka or equivalent streaming platform
- Open source contributions

We offer visa sponsorship.
"""


def test_title_extracted():
    jd = parse_jd(SAMPLE_JD)
    assert "Senior Backend Engineer" in jd["title"]


def test_seniority_detected():
    jd = parse_jd(SAMPLE_JD)
    assert jd["seniority"] == "senior"


def test_required_skills_extracted():
    jd = parse_jd(SAMPLE_JD)
    # The "Requirements:" section should yield required skills
    assert "go" in jd["required_skills"]
    assert "postgresql" in jd["required_skills"]
    assert "kubernetes" in jd["required_skills"]
    assert "aws" in jd["required_skills"]
    assert "distributed systems" in jd["required_skills"]


def test_nice_to_have_separated():
    jd = parse_jd(SAMPLE_JD)
    # "Nice to have:" section should be separated from required
    assert "kafka" in jd["nice_to_have"]
    # Kafka should NOT be in required (it's nice-to-have)
    assert "kafka" not in jd["required_skills"]


def test_min_yoe_extracted():
    jd = parse_jd(SAMPLE_JD)
    assert jd["min_yoe"] == 7


def test_location_extracted():
    jd = parse_jd(SAMPLE_JD)
    assert "Remote" in jd["location"]


def test_remote_ok_flag():
    jd = parse_jd(SAMPLE_JD)
    assert jd["remote_ok"] is True


def test_visa_required_flag():
    jd = parse_jd(SAMPLE_JD)
    assert jd["visa_required"] is True


def test_inline_jd_text():
    """The parser should accept inline JD text (not just file paths)."""
    jd = parse_jd("Junior React Engineer with 2 years experience")
    assert "react" in jd["required_skills"] or "react" in jd["nice_to_have"]
    assert jd["seniority"] == "junior"


def test_empty_jd_doesnt_crash():
    """An empty string should return a valid (mostly empty) dict, not crash."""
    jd = parse_jd("")
    assert jd["title"] == ""
    assert jd["required_skills"] == []
