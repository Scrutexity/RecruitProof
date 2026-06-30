"""
jd_parser.py — Lightweight Job Description Parser
=================================================

Extracts structured fields from free-form JD text so the MultiSignalRanker
has clean inputs. Uses regex + skill gazetteer — no LLM call required for the
base search (keeps the demo <5s end-to-end).

Extracts:
  * title          (first non-empty line that looks like a job title)
  * seniority      (intern|junior|mid|senior|staff|principal|director|...)
  * required_skills (intersection with SKILL_GAZETTEER)
  * nice_to_have
  * min_yoe        (from "X+ years" patterns)
  * location       (from "Location:" line)
  * remote_ok
  * visa_required
"""
from __future__ import annotations

import re
from typing import Dict, List

# A broad gazetteer. Extend with your domain. Lowercase, single-token entries
# are matched as whole words; multi-word entries use phrase match.
SKILL_GAZETTEER = [
    # languages
    "python", "go", "golang", "rust", "java", "kotlin", "swift", "typescript", "javascript",
    "c++", "c#", "ruby", "php", "scala", "elixir", "clojure",
    # frontend
    "react", "react native", "next.js", "vue", "angular", "svelte", "tailwind css",
    "redux", "graphql", "html", "css", "sass", "storybook",
    # backend
    "node.js", "express", "django", "flask", "fastapi", "spring", "rails", "laravel",
    "gin", "echo", "fiber",
    # data / ml
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "spark",
    "airflow", "dbt", "llms", "rag", "machine learning", "deep learning",
    "nlp", "computer vision", "reinforcement learning", "mlops", "vector databases",
    # infra / cloud
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "ansible",
    "linux", "nginx", "prometheus", "grafana", "elasticsearch", "kafka",
    "redis", "postgresql", "mysql", "mongodb", "cassandra", "clickhouse",
    "microservices", "distributed systems", "ci/cd", "gitops", "argocd",
    # dev practices
    "agile", "scrum", "tdd", "ddd", "open source",
]

NICE_TO_HAVE_PATTERNS = [
    r"\bnice[- ]to[- ]have\b", r"\bbonus\b", r"\bpluses?\b", r"\bpreferred\b",
    r"\bideally\b", r"\bwill be a plus\b",
]

YOE_PATTERNS = [
    r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?experience",
    r"(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:relevant\s+)?experience",
    r"(\d+)\s*\+?\s*yrs?\s+(?:of\s+)?experience",
    r"minimum\s+(?:of\s+)?(\d+)\s*\+?\s*years?",
    r"at least\s+(\d+)\s*\+?\s*years?",
]

SENIORITY_KEYWORDS = {
    "intern": "intern", "junior": "junior", "jr": "junior",
    "associate": "associate", "mid": "mid",
    "senior": "senior", "sr": "senior", "lead": "senior",
    "staff": "staff", "principal": "principal",
    "director": "director", "head of": "director", "vp of": "vp",
    "chief": "cto", "cto": "cto",
}

REMOTE_PATTERNS = [r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", r"\banywhere\b"]
VISA_PATTERNS = [r"\bvisa sponsorship\b", r"\bsponsor(?:ship)?\b", r"\bh1b\b", r"\bopt\b"]


def _find_skills(text: str, gazetteer: List[str]) -> List[str]:
    text_lower = text.lower()
    found = []
    for skill in gazetteer:
        # word-boundary match for single tokens, phrase match for multi-word
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            # Preserve original capitalization from the JD where possible.
            m = re.search(pattern, text_lower)
            if m:
                found.append(skill)
    # de-dup preserving order
    seen = set()
    out = []
    for s in found:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def parse_jd(jd_text: str) -> Dict:
    """Parse free-form JD text into a structured dict.

    Returns keys: title, seniority, required_skills, nice_to_have, min_yoe,
    location, remote_ok, visa_required.
    """
    text = jd_text.strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # --- title: first non-empty line that doesn't start with a label
    title = ""
    for line in lines:
        ll = line.lower()
        if any(ll.startswith(p) for p in ("about", "we are", "we're", "job description",
                                           "responsibilities", "requirements", "what you", "you will",
                                           "location:", "company:", "team:")):
            continue
        # strip trailing punctuation
        title = line.rstrip(":").strip()
        break

    # --- seniority
    seniority = "mid"
    title_lower = (title or "").lower()
    for kw, band in SENIORITY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", title_lower):
            seniority = band
            break

    # --- skills (whole JD)
    all_skills = _find_skills(text, SKILL_GAZETTEER)

    # --- split required vs nice-to-have by section
    nice_section_start = None
    for pat in NICE_TO_HAVE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            nice_section_start = m.start()
            break
    if nice_section_start is not None:
        req_text = text[:nice_section_start]
        nice_text = text[nice_section_start:]
        required_skills = _find_skills(req_text, SKILL_GAZETTEER)
        nice_to_have = _find_skills(nice_text, SKILL_GAZETTEER)
        # nice_to_have that also appear in required shouldn't double-count
        nice_to_have = [s for s in nice_to_have if s not in required_skills]
    else:
        # No nice-to-have section: top-N skills by appearance become required
        required_skills = all_skills[:8]
        nice_to_have = all_skills[8:]

    # --- min YoE
    min_yoe = None
    for pat in YOE_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            min_yoe = int(m.group(1))
            break

    # --- location
    location = ""
    loc_match = re.search(r"location\s*[:\-]\s*([^\n]+)", text, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()

    # --- remote / visa flags
    remote_ok = any(re.search(p, text, re.IGNORECASE) for p in REMOTE_PATTERNS)
    visa_required = any(re.search(p, text, re.IGNORECASE) for p in VISA_PATTERNS)

    return {
        "title": title,
        "seniority": seniority,
        "required_skills": required_skills,
        "nice_to_have": nice_to_have,
        "min_yoe": min_yoe,
        "location": location,
        "remote_ok": remote_ok,
        "visa_required": visa_required,
        "raw_text": text,
    }
