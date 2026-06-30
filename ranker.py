"""
ranker.py — Multi-Signal Ranking Layer
=====================================

The single most important file in the system. Cosine similarity alone is not
enough to rank 1M candidates — keyword-stuffed resumes win. Instead we layer
five orthogonal signals, steal the redrob-ranker weighting, and rescale
everything to a 0-10 score so the recruiter sees a familiar rubric.

Signals (each in [0, 1]):
  1. Semantic   40%  — cosine sim between JD embedding and resume embedding
  2. Role-Fit   20%  — title match (fuzzy) + seniority band + location + YoE
  3. Skills     15%  — proficiency-weighted fuzzy overlap with JD skills
  4. Behavioral 15%  — recency of activity, response rate, engagement warmth
  5. Career     10%  — trajectory velocity, stability, promotion cadence

Final score  = 10 * (0.4·sem + 0.2·role + 0.15·skill + 0.15·behav + 0.10·career)

This module also derives:
  * `missing_skills` — JD skills the candidate does NOT have (explains "why
    not 10/10").
  * `signals` — a dict of the raw 0-1 signal scores (for transparency).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional

# ---- Signal weights (redrob-ranker DNA) ----------------------------------
WEIGHTS = {
    "semantic":   0.40,
    "role_fit":   0.20,
    "skills":     0.15,
    "behavioral": 0.15,
    "career":     0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6, "weights must sum to 1.0"

# ---- Seniority band map (Role-Fit signal) -------------------------------
# We map titles to a seniority ordinal so a "Senior" JD doesn't get matched
# to a "Junior" candidate even if their embedding is close.
SENIORITY_BANDS = {
    "intern": 1, "junior": 2, "associate": 3, "mid": 4,
    "senior": 5, "staff": 6, "principal": 7, "director": 8, "vp": 9, "cto": 10,
}

SENIORITY_KEYWORDS = [
    ("intern", "intern"), ("junior", "junior"), ("jr", "junior"),
    ("associate", "associate"), ("mid", "mid"), ("ii", "mid"),
    ("senior", "senior"), ("sr", "senior"), ("iii", "senior"),
    ("staff", "staff"), ("principal", "principal"),
    ("director", "director"), ("head", "director"),
    ("vp", "vp"), ("vice president", "vp"),
    ("cto", "cto"), ("chief", "cto"),
]


def detect_seniority(title: str) -> str:
    if not title:
        return "mid"
    t = title.lower()
    for kw, band in SENIORITY_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", t):
            return band
    return "mid"


def fuzzy_ratio(a: str, b: str) -> float:
    """difflib-based similarity in [0, 1]. Cheaper than RapidFuzz, no dep."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


@dataclass
class CandidateScore:
    candidate_id: str
    rank: int = 0
    score_10: float = 0.0            # final 0-10 score
    semantic: float = 0.0            # 0-1 per-signal
    role_fit: float = 0.0
    skills_match: float = 0.0
    behavioral: float = 0.0
    career: float = 0.0
    missing_skills: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    signals: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""


# ===========================================================================
# MultiSignalRanker
# ===========================================================================

class MultiSignalRanker:
    """Re-ranks FAISS-retrieved candidates against a parsed job description.

    The ranker is stateless apart from the parsed JD, so it's safe to call
    from `search.py` per query.
    """

    def __init__(self, jd: Dict):
        """
        jd is a parsed dict with:
          title, required_skills (list[str]), nice_to_have (list[str]),
          seniority (str), min_yoe (int), location (str),
          remote_ok (bool), visa_required (bool)
        """
        self.jd = jd
        self.jd_seniority = detect_seniority(jd.get("title", ""))

    # ---------------------------------------------------------------- public

    def score(
        self,
        candidate: Dict,
        semantic_sim: float,    # cosine sim in [-1, 1]
    ) -> CandidateScore:
        sem = self._semantic_signal(semantic_sim)
        role = self._role_fit_signal(candidate)
        skill, matched, missing = self._skills_signal(candidate)
        behav = self._behavioral_signal(candidate)
        career = self._career_signal(candidate)

        final = 10.0 * (
            WEIGHTS["semantic"]   * sem
            + WEIGHTS["role_fit"] * role
            + WEIGHTS["skills"]   * skill
            + WEIGHTS["behavioral"] * behav
            + WEIGHTS["career"]   * career
        )
        final = max(0.0, min(10.0, final))

        return CandidateScore(
            candidate_id=candidate["id"],
            score_10=round(final, 2),
            semantic=round(sem, 3),
            role_fit=round(role, 3),
            skills_match=round(skill, 3),
            behavioral=round(behav, 3),
            career=round(career, 3),
            missing_skills=missing,
            matched_skills=matched,
            signals={
                "semantic": round(sem, 3),
                "role_fit": round(role, 3),
                "skills": round(skill, 3),
                "behavioral": round(behav, 3),
                "career": round(career, 3),
            },
        )

    # ---------------------------------------------------------------- signals

    @staticmethod
    def _semantic_signal(sim: float) -> float:
        """Cosine in [-1, 1] → [0, 1]."""
        return max(0.0, (sim + 1.0) / 2.0)

    def _role_fit_signal(self, c: Dict) -> float:
        """Title fuzzy match (50%) + seniority band (30%) + location (20%)."""
        # --- title fuzzy
        jd_title = (self.jd.get("title") or "").lower()
        c_title = (c.get("current_title") or c.get("headline") or "").lower()
        title_sim = fuzzy_ratio(jd_title, c_title) if jd_title and c_title else 0.0

        # --- seniority band proximity
        c_band = detect_seniority(c.get("current_title") or "")
        c_band_n = SENIORITY_BANDS.get(c_band, 4)
        jd_band_n = SENIORITY_BANDS.get(self.jd_seniority, 4)
        # 1.0 if exact, 0.5 if ±1 band, 0.0 if >2 bands off
        delta = abs(c_band_n - jd_band_n)
        seniority_score = 1.0 if delta == 0 else (0.7 if delta == 1 else (0.3 if delta == 2 else 0.0))

        # --- location
        jd_loc = (self.jd.get("location") or "").lower()
        c_loc = (c.get("location") or "").lower()
        if self.jd.get("remote_ok") or c.get("open_to_remote"):
            loc_score = 1.0
        elif not jd_loc or not c_loc:
            loc_score = 0.5
        elif jd_loc in c_loc or c_loc in jd_loc:
            loc_score = 1.0
        else:
            loc_score = 0.2

        return 0.5 * title_sim + 0.3 * seniority_score + 0.2 * loc_score

    def _skills_signal(self, c: Dict) -> tuple[float, List[str], List[str]]:
        """Fuzzy skill overlap. Required skills count double; nice-to-haves
        count single. Returns (score 0-1, matched, missing_required)."""
        required = [s.lower() for s in (self.jd.get("required_skills") or [])]
        nice = [s.lower() for s in (self.jd.get("nice_to_have") or [])]
        cand_skills = [s.lower() for s in (c.get("skills") or [])]

        def best_overlap(jd_skill: str) -> float:
            return max((fuzzy_ratio(jd_skill, cs) for cs in cand_skills), default=0.0)

        # Required skills: fuzzy match with 0.75 threshold, weight 2.
        req_match = sum(2.0 for s in required if best_overlap(s) >= 0.75)
        req_total = max(1, len(required) * 2)
        nice_match = sum(1.0 for s in nice if best_overlap(s) >= 0.75)
        nice_total = max(1, len(nice))

        # Weighted combination — required dominates.
        req_frac = req_match / req_total
        nice_frac = nice_match / nice_total if nice else 0.0
        score = 0.75 * req_frac + 0.25 * nice_frac

        matched = [s for s in (self.jd.get("required_skills") or []) + (self.jd.get("nice_to_have") or [])
                   if best_overlap(s.lower()) >= 0.75]
        missing = [s for s in (self.jd.get("required_skills") or [])
                   if best_overlap(s.lower()) < 0.75]
        return score, matched, missing

    def _behavioral_signal(self, c: Dict) -> float:
        """Recency of activity (50%) + response rate (30%) + warmth (20%).

        For candidates without explicit signals, we infer recency from
        `last_active_days_ago` and `response_rate` fields if present, else
        fall back to a neutral 0.5.
        """
        score = 0.0
        # --- recency
        days = c.get("last_active_days_ago")
        if days is None:
            recency = 0.5
        elif days <= 7:
            recency = 1.0
        elif days <= 30:
            recency = 0.8
        elif days <= 90:
            recency = 0.5
        else:
            recency = 0.2
        score += 0.5 * recency

        # --- response rate
        rr = c.get("response_rate")
        if rr is None:
            score += 0.3 * 0.5
        else:
            score += 0.3 * max(0.0, min(1.0, float(rr) / 100.0))

        # --- warmth (prior engagement)
        warm = 0.0
        if c.get("previously_applied"):
            warm += 0.5
        if c.get("referral"):
            warm += 0.5
        score += 0.2 * min(1.0, warm)

        return score

    def _career_signal(self, c: Dict) -> float:
        """Trajectory velocity (40%) + stability (30%) + progression (30%)."""
        yoe = float(c.get("years_experience") or 0)
        # Velocity: promotions per year (capped at 1/yr).
        promos = float(c.get("promotions_last_5y") or 0)
        velocity = min(1.0, promos / max(1.0, min(5.0, yoe)))

        # Stability: tenure at current company (sweet spot 2-5 years).
        tenure = float(c.get("current_tenure_years") or 0)
        if tenure < 0.5:
            stability = 0.4  # job hopper risk
        elif tenure <= 5:
            stability = 1.0
        elif tenure <= 8:
            stability = 0.8
        else:
            stability = 0.6  # stagnant

        # Progression: did their title advance?
        progression = 1.0 if c.get("title_progressed") else 0.5

        return 0.4 * velocity + 0.3 * stability + 0.3 * progression


# ===========================================================================
# Reasoning generator — "why is this candidate #1?"
# ===========================================================================

def generate_reasoning(
    cs: CandidateScore,
    candidate: Dict,
    jd: Dict,
    use_llm: bool = False,
    llm_client=None,
) -> str:
    """Produce a 1-sentence explanation of why this candidate ranks here.

    Local-first by default — pure template reasoning. If `use_llm=True`
    and an `llm_client` (OpenAI) is supplied, calls the LLM for a richer
    one-liner.
    """
    if use_llm and llm_client is not None:
        try:
            return _llm_reasoning(cs, candidate, jd, llm_client)
        except Exception:
            pass  # fall through to local template

    # ---- local template reasoning ----
    name = candidate.get("name", "Candidate")
    yoe = candidate.get("years_experience", "?")
    top_skill = (candidate.get("skills") or ["?"])[0]
    matched = cs.matched_skills[:3]
    matched_str = ", ".join(matched) if matched else "transferable skills"

    reasons = []
    if cs.semantic >= 0.8:
        reasons.append("strong semantic match")
    elif cs.semantic >= 0.6:
        reasons.append("solid semantic alignment")
    if cs.role_fit >= 0.7:
        reasons.append(f"{yoe} years as a {candidate.get('current_title', 'professional')}")
    if cs.skills_match >= 0.7 and matched:
        reasons.append(f"covers {matched_str}")
    if cs.career >= 0.7:
        reasons.append("upward career trajectory")
    if cs.behavioral >= 0.7:
        reasons.append("recently active and engaged")

    if not reasons:
        reasons = ["partial overlap with the role profile"]

    why_top = (
        f"Top pick because of {' and '.join(reasons[:3])}"
        if cs.rank == 1
        else f"Matches on {' and '.join(reasons[:3])}"
    )
    return f"{name} — {cs.score_10}/10 — {why_top}."


def _llm_reasoning(cs: CandidateScore, candidate: Dict, jd: Dict, client) -> str:
    """OpenAI-backed one-sentence reasoning (optional path)."""
    prompt = (
        f"Write ONE sentence (≤30 words) explaining why this candidate is a "
        f"strong match for the job. Be specific.\n\n"
        f"Job: {jd.get('title')} at unknown company. Required skills: "
        f"{jd.get('required_skills')}. Seniority: {jd.get('seniority')}.\n\n"
        f"Candidate: {candidate.get('name')}, {candidate.get('years_experience')} yrs, "
        f"{candidate.get('current_title')} at {candidate.get('current_company')}. "
        f"Skills: {candidate.get('skills')[:8]}.\n\n"
        f"Signal scores (0-1): semantic={cs.semantic}, role_fit={cs.role_fit}, "
        f"skills={cs.skills_match}, behavioral={cs.behavioral}, career={cs.career}.\n"
        f"Matched skills: {cs.matched_skills[:5]}. Missing required skills: {cs.missing_skills[:3]}.\n\n"
        f"One sentence:"
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip().strip('"')
