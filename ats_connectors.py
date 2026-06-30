"""
ats_connectors.py — ATS Integration Layer
========================================

The "golden ticket" for enterprise recruitment is a real Workday connector.
This module provides a unified ATSConnector interface plus concrete stubs
for Workday, Greenhouse, Lever, and Ashby — covering the four most common
enterprise form-schema families.

Each connector exposes:
  - form_schema()  → structured field list (so the auto-fill engine knows
                     what fields to fill and how)
  - evasion_profile(for_job)  → which stealth profile to use
  - detect_captcha(html)      → CAPTCHA detection heuristic
  - submit_application(candidate, job)  → simulates a submission and
                     returns an ApplicationResult (no real network call;
                     this is a stub for the demo / local-first mode)

For production use, replace `submit_application` with a real Playwright
or requests-based implementation.
"""
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ----------------------------------------------------------------- dataclasses

@dataclass
class FormField:
    name: str
    label: str
    type: str            # "text" | "email" | "phone" | "textarea" | "select" | "file" | "date"
    required: bool = True
    options: List[str] = field(default_factory=list)
    autofill_from: str = ""  # which candidate field maps to this


@dataclass
class ApplicationResult:
    success: bool
    status: str           # "submitted" | "captcha_pending" | "human_review" | "failed"
    confirmation_id: str = ""
    captcha_encountered: bool = False
    fields_filled: int = 0
    fields_total: int = 0
    error: str = ""
    evasion_profile: str = "balanced"
    fingerprint_hash: str = ""
    elapsed_ms: float = 0.0


# ----------------------------------------------------------------- base class

class ATSConnector:
    """Base class for ATS connectors. Subclasses override the specifics."""

    ats_id: str = "base"
    name: str = "Base ATS"
    form_family: str = "generic"
    captcha_likelihood: float = 0.0   # 0..1 probability per submission
    evasion_difficulty: int = 1       # 1..5

    def form_schema(self) -> List[FormField]:
        raise NotImplementedError

    def evasion_profile(self, stealth_level: int = 2) -> str:
        """Pick an evasion profile based on the connector's difficulty."""
        if self.evasion_difficulty >= 4 or stealth_level == 3:
            return "stealth-v3"
        if self.evasion_difficulty <= 2 and stealth_level == 1:
            return "express"
        return "balanced"

    def detect_captcha(self, html: str) -> bool:
        """Heuristic CAPTCHA detection from raw HTML."""
        if not html:
            return False
        markers = ["captcha", "g-recaptcha", "h-captcha", "cf-challenge",
                   "are you a robot", "press and hold"]
        html_lower = html.lower()
        return any(m in html_lower for m in markers)

    def submit_application(self, candidate: Dict, job: Dict,
                           stealth_level: int = 2,
                           simulate: bool = True) -> ApplicationResult:
        """Submit (or simulate submitting) an application.

        In simulate mode (default, local-first), this returns a deterministic
        ApplicationResult without any network call. In production, set
        simulate=False and override this method to perform real HTTP / browser
        automation.
        """
        t0 = time.time()
        schema = self.form_schema()
        # Determine autofill coverage
        filled = 0
        for f in schema:
            value = self._autofill(f, candidate)
            if value:
                filled += 1

        # Simulate CAPTCHA based on connector likelihood
        rng = random.Random(hash(candidate.get("id", "") + job.get("id", "")))
        captcha = rng.random() < self.captcha_likelihood

        # Simulate result
        if captcha and self.evasion_difficulty >= 4:
            status = "captcha_pending"
            success = False
            error = "CAPTCHA served — human handoff required"
        elif captcha:
            status = "human_review"
            success = False
            error = "CAPTCHA served — slowing cadence, retry queued"
        elif filled < len(schema) * 0.7:
            status = "human_review"
            success = False
            error = f"only {filled}/{len(schema)} fields autofilled — manual review"
        else:
            status = "submitted"
            success = True
            error = ""

        # Synthesize a confirmation id
        fp_input = f"{candidate.get('id','')}-{job.get('id','')}-{self.ats_id}-{time.time()}"
        fp_hash = "0x" + hashlib.sha256(fp_input.encode()).hexdigest()[:8]
        confirm = f"{self.ats_id.upper()}-{fp_hash}-{int(time.time())}"

        return ApplicationResult(
            success=success,
            status=status,
            confirmation_id=confirm if success else "",
            captcha_encountered=captcha,
            fields_filled=filled,
            fields_total=len(schema),
            error=error,
            evasion_profile=self.evasion_profile(stealth_level),
            fingerprint_hash=fp_hash,
            elapsed_ms=(time.time() - t0) * 1000,
        )

    def _autofill(self, field: FormField, candidate: Dict) -> Optional[str]:
        """Resolve a form field's value from candidate data."""
        if not field.autofill_from:
            return None
        # Support dotted paths like "current_company"
        return candidate.get(field.autofill_from)


# ----------------------------------------------------------------- Workday

class WorkdayConnector(ATSConnector):
    """Workday is the enterprise 'golden ticket'. Form schema is complex,
    multi-page, frequently CAPTCHA-protected. High evasion difficulty."""

    ats_id = "workday"
    name = "Workday"
    form_family = "workday"
    captcha_likelihood = 0.45
    evasion_difficulty = 4

    def form_schema(self) -> List[FormField]:
        return [
            FormField("first_name", "First Name", "text", required=True, autofill_from="first_name"),
            FormField("last_name", "Last Name", "text", required=True, autofill_from="last_name"),
            FormField("email", "Email", "email", required=True, autofill_from="email"),
            FormField("phone", "Phone", "phone", required=True, autofill_from="phone"),
            FormField("resume", "Resume", "file", required=True, autofill_from="resume_path"),
            FormField("linkedin", "LinkedIn URL", "text", required=False, autofill_from="linkedin"),
            FormField("website", "Personal Website", "text", required=False),
            FormField("why_interested", "Why are you interested?", "textarea", required=True),
            FormField("salary_expectation", "Salary Expectation", "text", required=True),
            FormField("work_auth", "Work Authorization", "select", required=True,
                      options=["US Citizen", "Green Card", "H1B", "OPT", "Other"]),
            FormField("sponsorship", "Need Sponsorship?", "select", required=True,
                      options=["Yes", "No"]),
            FormField("start_date", "Earliest Start Date", "date", required=True),
            FormField("veteran_status", "Veteran Status", "select", required=False,
                      options=["I am not a veteran", "I am a veteran", "Prefer not to say"]),
            FormField("disability", "Disability Status", "select", required=False,
                      options=["Yes", "No", "Prefer not to say"]),
            FormField("gender", "Gender", "select", required=False,
                      options=["Male", "Female", "Non-binary", "Prefer not to say"]),
            FormField("race", "Race/Ethnicity", "select", required=False,
                      options=["Asian", "Black", "Hispanic", "White", "Two or more", "Prefer not to say"]),
            FormField("eeo_consent", "EEO Consent", "select", required=True,
                      options=["I consent", "I do not consent"]),
        ]


# ----------------------------------------------------------------- Greenhouse

class GreenhouseConnector(ATSConnector):
    """Greenhouse — simple form, public JSON API, low evasion difficulty."""

    ats_id = "greenhouse"
    name = "Greenhouse"
    form_family = "greenhouse"
    captcha_likelihood = 0.05
    evasion_difficulty = 1

    def form_schema(self) -> List[FormField]:
        return [
            FormField("first_name", "First Name", "text", required=True, autofill_from="first_name"),
            FormField("last_name", "Last Name", "text", required=True, autofill_from="last_name"),
            FormField("email", "Email", "email", required=True, autofill_from="email"),
            FormField("phone", "Phone", "phone", required=False, autofill_from="phone"),
            FormField("resume", "Resume", "file", required=True, autofill_from="resume_path"),
            FormField("cover_letter", "Cover Letter", "file", required=False),
            FormField("linkedin", "LinkedIn URL", "text", required=False, autofill_from="linkedin"),
            FormField("website", "Website", "text", required=False),
            FormField("how_heard", "How did you hear about us?", "text", required=False),
            FormField("race", "Race/Ethnicity (EEO)", "select", required=False,
                      options=["Asian", "Black", "Hispanic", "White", "Two or more", "Prefer not to say"]),
            FormField("gender", "Gender (EEO)", "select", required=False,
                      options=["Male", "Female", "Non-binary", "Prefer not to say"]),
            FormField("veteran", "Veteran Status (EEO)", "select", required=False,
                      options=["I am not a veteran", "I am a veteran", "Prefer not to say"]),
        ]


# ----------------------------------------------------------------- Lever

class LeverConnector(ATSConnector):
    """Lever — minimal form, public JSON API, low evasion difficulty."""

    ats_id = "lever"
    name = "Lever"
    form_family = "lever"
    captcha_likelihood = 0.05
    evasion_difficulty = 1

    def form_schema(self) -> List[FormField]:
        return [
            FormField("name", "Full Name", "text", required=True, autofill_from="name"),
            FormField("email", "Email", "email", required=True, autofill_from="email"),
            FormField("phone", "Phone", "phone", required=False, autofill_from="phone"),
            FormField("org", "Current Company", "text", required=False, autofill_from="current_company"),
            FormField("resume", "Resume", "file", required=True, autofill_from="resume_path"),
            FormField("links", "Links (LinkedIn, GitHub, etc.)", "textarea", required=False,
                      autofill_from="links"),
        ]


# ----------------------------------------------------------------- Ashby

class AshbyConnector(ATSConnector):
    """Ashby — modern ATS, public JSON API, mid evasion difficulty."""

    ats_id = "ashby"
    name = "Ashby"
    form_family = "ashby"
    captcha_likelihood = 0.10
    evasion_difficulty = 2

    def form_schema(self) -> List[FormField]:
        return [
            FormField("first_name", "First Name", "text", required=True, autofill_from="first_name"),
            FormField("last_name", "Last Name", "text", required=True, autofill_from="last_name"),
            FormField("email", "Email", "email", required=True, autofill_from="email"),
            FormField("phone", "Phone", "phone", required=False, autofill_from="phone"),
            FormField("resume", "Resume", "file", required=True, autofill_from="resume_path"),
            FormField("location", "Location", "text", required=True, autofill_from="location"),
            FormField("current_company", "Current Company", "text", required=False,
                      autofill_from="current_company"),
            FormField("linkedin", "LinkedIn URL", "text", required=False, autofill_from="linkedin"),
            FormField("salary", "Salary Expectations", "text", required=False),
            FormField("notice", "Notice Period", "text", required=False),
            FormField("why", "Why this role?", "textarea", required=True),
            FormField("visa", "Visa Required?", "select", required=True, options=["Yes", "No"]),
        ]


# ----------------------------------------------------------------- Registry

REGISTRY: Dict[str, type] = {
    "workday": WorkdayConnector,
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
}


def get_connector(ats_id: str) -> Optional[ATSConnector]:
    """Instantiate a connector by ATS id."""
    cls = REGISTRY.get(ats_id)
    return cls() if cls else None
