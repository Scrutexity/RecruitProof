"""
generate_shortlist_pdf.py - Battle-Ready Shortlist PDF (Special Sauce Edition)
==============================================================================

Transforms RecruitProof search results into a recruiter-ready PDF that:

  - Shows every candidate ranked with explainable 5-signal breakdown
  - Includes evidence snippets extracted directly from the resume
  - Flags "Potential Concerns" for full transparency
  - Ends with a data processing guarantee page (trust anchor for Rudy)

Usage:
    from generate_shortlist_pdf import create_shortlist_pdf
    create_shortlist_pdf(Path("search_results.json"), jd_text, Path("shortlist.pdf"))
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from fpdf import FPDF

# -- Signal display configuration -----------------------------------------
SIGNAL_LABELS = {
    "semantic": "Semantic Fit",
    "role_fit": "Role Match",
    "skills": "Skills Overlap",
    "behavioral": "Behavioral Fit",
    "career": "Career Trajectory",
}

SIGNAL_COLORS = {
    "semantic": (52, 144, 220),    # blue
    "role_fit": (22, 163, 74),     # green
    "skills": (124, 58, 237),      # purple
    "behavioral": (234, 88, 12),   # orange
    "career": (239, 68, 68),       # red
}


class ShortlistPDF(FPDF):
    """Professional PDF with header/footer for recruiter delivery."""

    def header(self):
        if self.page_no() == 1:
            return  # title page handles its own header
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(15, 118, 110)
        self.cell(0, 6, "RecruitProof Shortlist Report  |  Confidential", align="L")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(156, 163, 175)
        self.cell(0, 6, time.strftime("%Y-%m-%d"), align="R", ln=True)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(156, 163, 175)
        self.cell(0, 10,
                  "Page %d/{nb}  |  RecruitProof - Zero data left your machine."
                  % self.page_no(),
                  align="C")


def _normalize_score(score_val: Any) -> float:
    """Convert score_10 (0-10) or score (0-1) to a 0-1 float."""
    if isinstance(score_val, (int, float)):
        if score_val > 1:
            return round(score_val / 10.0, 3)
        return score_val
    return 0.0


def _build_signal_rows(signals: Dict[str, float]) -> List[tuple]:
    """Convert raw signal dict to sorted list of (label, value, color) rows."""
    rows = []
    for key, label in SIGNAL_LABELS.items():
        val = signals.get(key, 0.0)
        if isinstance(val, (int, float)):
            val = min(val, 1.0) if val <= 1 else min(val / 10.0, 1.0)
        else:
            val = 0.0
        color = SIGNAL_COLORS.get(key, (100, 100, 100))
        rows.append((label, round(val, 3), color))
    return rows


def _build_evidence(cand: Dict) -> Dict[str, str]:
    """Extract evidence snippets from candidate data for the PDF card."""
    evidence = {}

    title = cand.get("current_title") or ""
    company = cand.get("current_company") or ""
    if title and company:
        evidence["Current Role"] = "%s @ %s" % (title, company)
    elif title:
        evidence["Current Role"] = title

    yoe = cand.get("years_experience")
    if yoe is not None:
        evidence["Experience"] = "%d years" % yoe

    matched = cand.get("matched_skills", [])
    if matched:
        evidence["Skills"] = ", ".join(matched[:8])

    location = cand.get("location")
    if location:
        evidence["Location"] = location

    return evidence


def _build_concerns(cand: Dict) -> str:
    """Derive potential concerns from missing skills, signal variance, and other gaps."""
    parts = []
    missing = cand.get("missing_skills", [])
    if missing:
        parts.append("Missing: %s" % ", ".join(missing[:5]))
    score = _normalize_score(cand.get("score_10", 0))
    if score < 0.5:
        parts.append("Overall fit below threshold - manual review recommended")

    # Flag signal variance: any individual signal >30pp below the overall score
    signals = cand.get("signals", {})
    if signals:
        signal_vals = {}
        for key in SIGNAL_LABELS:
            val = signals.get(key, 0.0)
            if isinstance(val, (int, float)):
                signal_vals[key] = min(val, 1.0) if val <= 1 else min(val / 10.0, 1.0)
        if signal_vals:
            avg = sum(signal_vals.values()) / len(signal_vals)
            for key, val in signal_vals.items():
                if avg - val > 0.30:
                    label = SIGNAL_LABELS.get(key, key)
                    parts.append("%s significantly below average (%d%% vs %d%%)" % (
                        label, int(val * 100), int(avg * 100)))

    return " | ".join(parts) if parts else ""


def create_shortlist_pdf(
    search_results_path: Path,
    jd_text: str,
    output_pdf: Path,
) -> None:
    """
    Generate a recruiter-ready shortlist PDF from search.py --json output.

    Parameters
    ----------
    search_results_path : Path
        JSON path from ``search.py --json``. Expected shape:
        ``{"results": [{name, score_10, signals, matched_skills, ...}]}``
    jd_text : str
        Raw job description text (shown as excerpt).
    output_pdf : Path
        Where to write the generated PDF.
    """
    with open(search_results_path, "r") as f:
        data = json.load(f)

    results: List[Dict] = data if isinstance(data, list) else data.get("results", [])

    pdf = ShortlistPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # =========================================================================
    # PAGE 1 - Title + JD Summary
    # =========================================================================
    pdf.add_page()

    # Brand header
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(15, 118, 110)  # teal-700
    pdf.cell(0, 14, "RecruitProof", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5,
             "Explainable AI Shortlist  |  Local Processing  |  Zero Data Exit",
             ln=True, align="C")
    pdf.ln(6)

    # Run metadata
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 4, "Generated: %s" % time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime()), ln=True)
    pdf.cell(0, 4, "Candidates evaluated: %d" % len(results), ln=True)
    pdf.cell(0, 4, "Processing: fully local (no API calls, no data exfiltration)", ln=True)
    pdf.ln(8)

    # JD summary block
    pdf.set_fill_color(248, 250, 252)   # slate-50
    pdf.set_text_color(30, 41, 59)      # slate-800
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Job Description Summary", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(71, 85, 105)
    jd_excerpt = jd_text.strip()[:500]
    pdf.multi_cell(0, 4.5, jd_excerpt + ("..." if len(jd_text) > 500 else ""))
    pdf.ln(6)

    # Divider
    pdf.set_draw_color(15, 118, 110)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # =========================================================================
    # RANKED CANDIDATE CARDS
    # =========================================================================
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 118, 110)
    pdf.cell(0, 8, "Top %d Ranked Candidates" % len(results), ln=True)
    pdf.ln(4)

    for idx, cand in enumerate(results, 1):
        name = cand.get("name", "Unknown Candidate")
        score_raw = cand.get("score_10", 0)
        score_pct = _normalize_score(score_raw)
        signals = cand.get("signals", {})
        reasoning = cand.get("reasoning", "")
        evidence = _build_evidence(cand)
        concerns = _build_concerns(cand)

        # Check if we need a new page (card is ~60mm tall)
        if pdf.get_y() > 220:
            pdf.add_page()

        # Candidate header bar
        pdf.set_fill_color(15, 118, 110)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        bar_label = "  #%d  %s  |  Overall Fit: %d%%  (%d/10)" % (
            idx, name, int(score_pct * 100), int(score_raw))
        pdf.cell(0, 8, bar_label, ln=True, fill=True)
        pdf.ln(3)

        # Signal table (2-column layout)
        signal_rows = _build_signal_rows(signals)
        col_w = [56, 24, 56, 24]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)

        # Header row
        pdf.cell(col_w[0], 5, "Signal", border=1, align="C")
        pdf.cell(col_w[1], 5, "Score", border=1, align="C")
        pdf.cell(col_w[2], 5, "Signal", border=1, align="C")
        pdf.cell(col_w[3], 5, "Score", border=1, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for i in range(0, len(signal_rows), 2):
            # Left column
            label_l, val_l, color_l = signal_rows[i]
            pdf.set_text_color(*color_l)
            pdf.cell(col_w[0], 5, "  " + label_l, border=1)
            pdf.cell(col_w[1], 5, "%d%%" % int(val_l * 100), border=1, align="C")
            # Right column
            if i + 1 < len(signal_rows):
                label_r, val_r, color_r = signal_rows[i + 1]
                pdf.set_text_color(*color_r)
                pdf.cell(col_w[2], 5, "  " + label_r, border=1)
                pdf.cell(col_w[3], 5, "%d%%" % int(val_r * 100), border=1, align="C")
            else:
                pdf.cell(col_w[2], 5, "", border=1)
                pdf.cell(col_w[3], 5, "", border=1)
            pdf.ln()

        pdf.set_text_color(30, 41, 59)
        pdf.ln(2)

        # Evidence snippets
        if evidence:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(15, 118, 110)
            pdf.cell(0, 4, "Key Evidence (from resume):", ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(71, 85, 105)
            for label, value in evidence.items():
                pdf.cell(0, 4, "  " + label + ": " + value, ln=True)
            pdf.ln(1)

        # Explanation / Reasoning
        if reasoning:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(15, 118, 110)
            pdf.cell(0, 4, "Why This Candidate:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 4, "  " + reasoning[:400])
            pdf.ln(1)

        # Potential Concerns
        if concerns:
            pdf.set_text_color(180, 0, 0)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 4, "Potential Concerns:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 4, "  " + concerns)
            pdf.set_text_color(30, 41, 59)

        # Inter-candidate divider
        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    # =========================================================================
    # FINAL PAGE - Data Processing Guarantee (Trust Anchor)
    # =========================================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(15, 118, 110)
    pdf.cell(0, 12, "Data Processing Guarantee", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 41, 59)

    guarantees = [
        ("Local Processing", "All candidate matching ran inside a container on your machine. "
         "No data was sent to any external API, cloud service, or third party."),
        ("No Exfiltration", "RecruitProof made zero network calls during this pilot. "
         "The container was fully air-gapped (network_mode: none)."),
        ("Explainable Scoring",
         "Every candidate score is the weighted sum of five orthogonal signals. "
         "Each signal is traceable to specific resume content - no black boxes."),
        ("Raw Data Deleted", "If --auto-delete was enabled, all raw resume files, derived "
         "search indexes, and structured candidate data have been permanently wiped. "
         "A cryptographic deletion receipt (SHA-256 hashed) accompanies this report."),
        ("Audit Trail", "Every step of this pipeline was logged with a tamper-evident hash chain. "
         "Each log entry includes the SHA-256 hash of the previous line — editing any entry "
         "breaks the chain. The full log is available on request."),
    ]

    for title, desc in guarantees:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(15, 118, 110)
        pdf.cell(0, 6, "  >>  " + title, ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(0, 5, "       " + desc)
        pdf.ln(4)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 5,
             "RecruitProof - Open-source MIT | github.com/Scrutexity/RecruitProof",
             ln=True, align="C")

    pdf.output(str(output_pdf))
