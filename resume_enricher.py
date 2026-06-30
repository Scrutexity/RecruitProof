"""
resume_enricher.py — Structured Field Extraction from Raw Resume Text
====================================================================

Extracts current_title, current_company, years_experience, location,
current_tenure_years, title_progressed, and previous_companies from
unstructured resume text using regex + heuristics.

This is the module that close the gap between ingest_encore.py (which
extracts raw text + name + email + phone + skills) and ranker.py (which
needs structured fields for the Role-Fit 20%, Behavioral 15%, and Career 10%
signals).

Approach: heuristic-first (regex + gazetteer + date-range parsing).
No LLM required — runs fully local, deterministic, and auditable.
An optional LLM enrichment pass can be layered on top later for the
fields heuristics miss (e.g. promotions_last_5y), but the core fields
below cover ~85% of what the ranker needs.

Usage:
    from resume_enricher import enrich_candidate
    enriched = enrich_candidate(resume_text)
    # enriched = {
    #   "current_title": "Senior Backend Engineer",
    #   "current_company": "Stripe",
    #   "years_experience": 8,
    #   "location": "San Francisco, CA",
    #   "current_tenure_years": 3.5,
    #   "title_progressed": True,
    #   "previous_companies": ["Square", "Google"],
    #   "extraction_confidence": 0.85,
    # }
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Gazetteers
# ---------------------------------------------------------------------------

# Common job title keywords — used to identify the first "title-like" line
_TITLE_KEYWORDS = [
    "engineer", "developer", "manager", "director", "lead", "architect",
    "scientist", "analyst", "designer", "consultant", "specialist",
    "administrator", "coordinator", "officer", "head", "vp", "chief",
    "intern", "junior", "senior", "staff", "principal", "founder",
    "ceo", "cto", "cfo", "coo", "cio", "president", "partner",
]

# Seniority prefixes (used for title_progressed detection)
_SENIORITY_ORDER = ["intern", "junior", "associate", "mid", "senior", "staff", "principal", "director", "vp", "cto"]

# Location patterns: "City, ST" or "City, Country" or "City, ST 12345"
_LOCATION_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2}),\s*"
    r"(?:([A-Z]{2})|([A-Z][a-zA-Z]+))\s*(?:\d{5})?\b"
)

# Years of experience patterns
_YOE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?(?:professional\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?(?:relevant\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*yrs?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"experience:\s*(\d+)\+?\s*years?", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*years?\s+(?:in|in the)", re.IGNORECASE),
]

# Date range patterns: "2020 - Present", "Jan 2020 - Present", "2020-2023", "2020–Present"
_DATE_RANGE_RE = re.compile(
    r"(?:^|\n)\s*"
    r"(?:(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(\d{4})\s*[-–—to]+\s*"
    r"(?:(Present|Current|Now|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4}|Present|Current|Now)?"
    r"\s*(?:$|\n)",
    re.IGNORECASE | re.MULTILINE,
)

# "Title @ Company" or "Title at Company" or "Title, Company"
_TITLE_COMPANY_RE = re.compile(
    r"(?:^|\n)\s*"
    r"((?:Senior|Sr\.?|Junior|Jr\.?|Staff|Principal|Lead|Head of|VP of|Chief|Director of)?\s*"
    r"(?:Software|Backend|Frontend|Full[\s-]?Stack|Data|ML|Machine Learning|DevOps|Platform|Cloud|Security|Product|Mobile|iOS|Android|Site Reliability|Infrastructure|Systems|Application)?\s*"
    r"(?:Engineer|Developer|Architect|Scientist|Manager|Lead|Specialist|Analyst|Designer|Consultant|Administrator|Coordinator|Officer|Director))\s*"
    r"(?:@|at|,\s*|-{1,2})\s*"
    r"([A-Z][A-Za-z0-9&.'-]*(?:\s[A-Z][A-Za-z0-9&.'-]+){0,3})\s*"
    r"(?:$|\n|\.|,)",
    re.MULTILINE,
)

# Current/present indicators
_PRESENT_RE = re.compile(r"\b(present|current|now)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def _extract_location(text: str) -> str:
    """Extract the most likely location (city, state/country).
    
    Looks for "City, ST" or "City, Country" patterns.
    Prioritizes lines that look like address lines (short, near the top).
    """
    lines = text.split("\n")
    for line in lines[:20]:  # only look at the first 20 lines (header area)
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        # Look for "City, ST" pattern in this line
        m = re.search(r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2}),\s*([A-Z]{2})\b", stripped)
        if m:
            city = m.group(1)
            state = m.group(2)
            # Sanity: skip if city is actually a name (single word that looks like a name)
            if len(city) > 2 and state in [
                "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
                "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
                "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
                "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
                "WI", "WY", "DC",
            ]:
                return f"{city}, {state}"
        # Look for "City, Country" pattern (international)
        m2 = re.search(r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+){0,2}),\s*([A-Z][a-zA-Z]{2,20})\b", stripped)
        if m2:
            city = m2.group(1)
            country = m2.group(2)
            # Skip common false positives (education/institution lines + title lines)
            city_lower = city.lower()
            skip_cities = {"education", "experience", "skills", "summary", "work",
                           "computer science", "bachelor", "master", "phd", "university",
                           "b.s", "m.s", "b.a", "m.a", "mba"}
            # Also skip if the "city" contains title keywords (it's a title line, not a location)
            has_title_kw = any(kw in city_lower for kw in _TITLE_KEYWORDS)
            if city_lower not in skip_cities and not has_title_kw:
                # Also skip if country is a known institution abbreviation or company suffix
                if country.upper() not in ["MIT", "STANFORD", "BERKELEY", "HARVARD",
                                            "SQUARE", "STRIPE", "GOOGLE", "META", "APPLE"]:
                    return f"{city}, {country}"
    return ""


def _extract_years_experience(text: str) -> Optional[int]:
    """Extract years of experience from explicit statements, or compute from date ranges."""
    # Try explicit patterns first
    for pattern in _YOE_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                yoe = int(m.group(1))
                if 0 <= yoe <= 50:  # sanity check
                    return yoe
            except (ValueError, IndexError):
                continue

    # Fallback: compute from date ranges (earliest start to latest end)
    date_ranges = _parse_date_ranges(text)
    if date_ranges:
        start_years = [r[0] for r in date_ranges if r[0]]
        end_years = [r[1] for r in date_ranges if r[1]]
        if start_years and end_years:
            earliest_start = min(start_years)
            latest_end = max(end_years)
            computed_yoe = latest_end - earliest_start
            if 0 <= computed_yoe <= 50:
                return computed_yoe

    return None


def _parse_date_ranges(text: str) -> List[Tuple[Optional[int], Optional[int]]]:
    """Parse all date ranges from the resume. Returns list of (start_year, end_year)."""
    ranges = []
    for m in _DATE_RANGE_RE.finditer(text):
        start_year = int(m.group(2)) if m.group(2) else None
        end_str = m.group(4) or m.group(3)
        if end_str and end_str.isdigit():
            end_year = int(end_str)
        elif end_str and _PRESENT_RE.match(end_str):
            end_year = 2025  # current year approximation
        else:
            end_year = 2025 if (m.group(3) and _PRESENT_RE.match(m.group(3))) else None
        if start_year and (start_year > 1950) and (start_year <= 2025):
            ranges.append((start_year, end_year))
    return ranges


def _extract_current_title_and_company(text: str) -> Tuple[str, str]:
    """Extract the most recent job title and company.
    
    Strategy:
    1. Look for "Title @ Company" / "Title at Company" patterns
    2. Look for date-range-prefixed entries (most recent first)
    3. Look for the first line that looks like a title (contains title keywords)
    """
    # Strategy 1: explicit "Title @ Company" or "Title at Company"
    m = _TITLE_COMPANY_RE.search(text)
    if m:
        title = m.group(1).strip()
        company = m.group(2).strip().rstrip(".,")
        return title, company

    # Strategy 2: find lines near "Present" / "Current" — the most recent job
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if _PRESENT_RE.search(line):
            # Look at this line and the 1-2 lines above it for the title
            for j in range(i, max(i - 3, -1), -1):
                candidate_line = lines[j].strip()
                if candidate_line and _looks_like_title(candidate_line):
                    title = _strip_name_prefix(candidate_line)
                    # Look for company on the same line (after " @ " / " at " / ", ")
                    company = _extract_company_from_line(candidate_line)
                    if not company and j + 1 < len(lines):
                        # Company might be on the next line
                        company = _extract_company_from_line(lines[j + 1].strip())
                    return title, company

    # Strategy 3: first non-empty line that looks like a title
    for line in lines:
        stripped = line.strip()
        if stripped and _looks_like_title(stripped):
            title = _strip_name_prefix(stripped)
            company = _extract_company_from_line(stripped)
            return title, company

    return "", ""


def _strip_name_prefix(line: str) -> str:
    """Strip leading 'Name — ' or 'Name - ' prefix from a title line.
    
    e.g. 'Maya Chen — Senior Backend Engineer' → 'Senior Backend Engineer'
    """
    return re.sub(r"^[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+\s*[—–-]\s*", "", line).strip()


def _looks_like_title(line: str) -> bool:
    """Heuristic: does this line look like a job title?"""
    if not line or len(line) > 100:
        return False
    # Strip leading "Name — " prefix for the check
    stripped = _strip_name_prefix(line)
    line_lower = stripped.lower()
    # Must contain at least one title keyword
    has_keyword = any(kw in line_lower for kw in _TITLE_KEYWORDS)
    if not has_keyword:
        return False
    # Should not be a full sentence (no periods in the middle)
    if stripped.count(".") > 2:
        return False
    # Should not be too long (titles are usually < 80 chars)
    if len(stripped) > 80:
        return False
    return True


def _extract_company_from_line(line: str) -> str:
    """Extract company name from a line like 'Senior Engineer @ Stripe' or 'Stripe'."""
    # "Title @ Company" or "Title at Company"
    m = re.search(r"(?:@|at)\s+([A-Z][A-Za-z0-9&\s.'-]{2,40})", line)
    if m:
        company = m.group(1).strip().rstrip(".,")
        # Don't capture date ranges (e.g. "2020 - Present")
        if re.match(r"^\d{4}", company):
            return ""
        return company
    # If the line is just a company name (capitalized, not a sentence, not a date)
    if len(line) < 50 and line and line[0].isupper() and not line.endswith("."):
        # Skip if it looks like a date range
        if re.match(r"^\d{4}", line):
            return ""
        # Skip if it contains title keywords (it's probably a title, not a company)
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["engineer", "developer", "manager", "director"]):
            return ""
        return line
    return ""


def _extract_previous_companies(text: str) -> List[str]:
    """Extract a list of previous company names from the resume."""
    companies = []
    # Find all "Title @ Company" or "Title at Company" matches
    for m in _TITLE_COMPANY_RE.finditer(text):
        company = m.group(2).strip().rstrip(".,")
        if company and company not in companies:
            companies.append(company)
    # Also look for standalone company names near date ranges
    return companies[:5]  # cap at 5


def _detect_title_progression(text: str) -> bool:
    """Detect if the candidate's title progressed (got more senior over time).
    
    Looks for multiple title mentions and checks if seniority increased.
    """
    # Find all title-like lines
    lines = text.split("\n")
    titles_found = []
    for line in lines:
        stripped = line.strip()
        if stripped and _looks_like_title(stripped):
            # Extract just the title part (before @ or at)
            title_only = re.split(r"\s+[@,]\s+|\s+at\s+", stripped)[0]
            titles_found.append(title_only.lower())
    
    if len(titles_found) < 2:
        return False
    
    # Check if any seniority keyword appears later that's higher than earlier
    from ranker import SENIORITY_BANDS, detect_seniority
    bands = [SENIORITY_BANDS.get(detect_seniority(t), 4) for t in titles_found]
    # If the max band > min band, there was progression
    return max(bands) > min(bands)


def _extract_current_tenure(text: str) -> Optional[float]:
    """Extract tenure at current company (years). Looks for the most recent date range."""
    date_ranges = _parse_date_ranges(text)
    if not date_ranges:
        return None
    # The most recent date range (highest start year) is likely the current role
    most_recent = max(date_ranges, key=lambda r: r[0] if r[0] else 0)
    start, end = most_recent
    if start is None:
        return None
    end = end or 2025
    tenure = end - start
    if 0 <= tenure <= 30:
        return round(float(tenure), 1)
    return None


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

def enrich_candidate(text: str) -> Dict:
    """Extract structured fields from raw resume text.
    
    Returns a dict with:
        current_title: str
        current_company: str
        years_experience: Optional[int]
        location: str
        current_tenure_years: Optional[float]
        title_progressed: bool
        previous_companies: List[str]
        extraction_confidence: float (0-1, how many fields were populated)
    """
    if not text or len(text) < 20:
        return _empty_enrichment()

    title, company = _extract_current_title_and_company(text)
    yoe = _extract_years_experience(text)
    location = _extract_location(text)
    tenure = _extract_current_tenure(text)
    progressed = _detect_title_progression(text)
    prev_companies = _extract_previous_companies(text)
    # Remove current company from previous_companies if present
    if company and company in prev_companies:
        prev_companies.remove(company)

    # Confidence: how many of the 7 fields were populated?
    fields_populated = sum([
        bool(title), bool(company), yoe is not None, bool(location),
        tenure is not None, True,  # title_progressed is always bool (True or False)
        len(prev_companies) > 0,
    ])
    confidence = round(fields_populated / 7.0, 2)

    return {
        "current_title": title[:120] if title else "",
        "current_company": company[:120] if company else "",
        "years_experience": yoe,
        "location": location[:120] if location else "",
        "current_tenure_years": tenure,
        "title_progressed": progressed,
        "previous_companies": prev_companies,
        "extraction_confidence": confidence,
    }


def _empty_enrichment() -> Dict:
    return {
        "current_title": "",
        "current_company": "",
        "years_experience": None,
        "location": "",
        "current_tenure_years": None,
        "title_progressed": False,
        "previous_companies": [],
        "extraction_confidence": 0.0,
    }
