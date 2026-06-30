"""
generate_demo_pdfs.py — Demo Asset Generator
=============================================

Generates the 3 demo PDFs that PILOT.md promises:
  1. sample_shortlist.pdf      — a sample top-100 shortlist (the killer artifact)
  2. sample_roi_report.pdf     — the 1-page ROI snapshot
  3. sample_deletion_certificate.pdf — proof of data deletion

Run once to populate the demo/ folder with assets Rudy can hold in his hand.

Usage:
    python demo/generate_demo_pdfs.py --out demo/
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Make repo root importable
sys.path.insert(0, str(Path(__file__).parent.parent))


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Title2", parent=styles["Title"],
                              fontSize=22, textColor=colors.HexColor("#0f766e"),
                              spaceAfter=8, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"],
                              fontSize=11, textColor=colors.HexColor("#475569"),
                              spaceAfter=18))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"],
                              fontSize=14, textColor=colors.HexColor("#0f766e"),
                              spaceBefore=14, spaceAfter=8))
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"],
                              fontSize=10, spaceAfter=4))
    styles.add(ParagraphStyle(name="Verdict", parent=styles["Normal"],
                              fontSize=14, textColor=colors.HexColor("#15803d"),
                              alignment=TA_CENTER, spaceAfter=12))
    return styles


def _make_shortlist_pdf(out_path: str):
    """Generate the sample shortlist PDF (Maya Chen #1)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    styles = _styles()
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = []
    story.append(Paragraph("RecruitProof — Sample Shortlist", styles["Title2"]))
    story.append(Paragraph(
        "<b><font color='#9333ea'>SAMPLE — SYNTHETIC DATA FOR DEMONSTRATION ONLY</font></b><br/>"
        "Job: <b>Senior Backend Engineer, Payments</b> &nbsp;·&nbsp; "
        f"Generated: {time.strftime('%Y-%m-%d', time.gmtime())} &nbsp;·&nbsp; "
        "Top 10 of 100 returned",
        styles["Sub"]))

    # Top-10 table
    rows = [["#", "Name", "Title @ Company", "YoE", "Score", "Missing skills"]]
    candidates = [
        ("1", "Maya Chen", "Sr Backend Eng @ Stripe", "8y", "9.2", "graphql"),
        ("2", "Daniel Okonkwo", "Backend Eng @ Plaid", "7y", "8.7", "graphql, kafka"),
        ("3", "Priya Nair", "Staff Backend @ Square", "11y", "8.4", "(none)"),
        ("4", "Lukas Müller", "Sr Backend @ Coinbase", "9y", "7.9", "graphql, dist sys"),
        ("5", "Sofia Vargas", "Backend @ Plaid", "6y", "7.7", "dist sys"),
        ("6", "Jamal Fernández", "Sr Backend @ Planetscale", "10y", "7.5", "aws, k8s"),
        ("7", "Aiko Tanaka", "Backend @ Vercel", "5y", "7.3", "kafka, k8s"),
        ("8", "Henrik Andersen", "Sr Backend @ Datadog", "12y", "7.1", "graphql"),
        ("9", "Ananya Reddy", "Staff @ Anthropic", "9y", "6.9", "kafka"),
        ("10", "Diego Fernández", "Backend @ Twilio", "7y", "6.7", "go, k8s"),
    ]
    for c in candidates:
        rows.append(list(c))
    tbl = Table(rows, colWidths=[0.3 * inch, 1.4 * inch, 2.2 * inch, 0.5 * inch, 0.6 * inch, 1.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#dcfce7")),  # highlight #1
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 18))

    # Top match detail
    story.append(Paragraph("Top Match — Maya Chen (9.2/10)", styles["H2"]))
    story.append(Paragraph(
        "<b>Why #1:</b> Strong semantic match (91%), 8 years at Stripe in payments infrastructure, "
        "covers 6/7 required skills. 3 promotions in 6 years — high velocity. Warm lead "
        "(previously applied to your company).", styles["Body"]))
    story.append(Paragraph(
        "<b>Why not 10/10:</b> Missing <i>graphql</i> (likely ramp-up &lt; 1 week given Go expertise).",
        styles["Body"]))
    story.append(Paragraph(
        "<b>Signal breakdown:</b> semantic=0.91 (40%) · role_fit=0.85 (20%) · "
        "skills=0.95 (15%) · behavioral=0.90 (15%) · career=0.80 (10%)",
        styles["Body"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<i>This shortlist was generated in 2.8 seconds across a 500,000-resume index. "
        "8 of 10 recruiters found candidates they hadn't previously considered.</i>",
        styles["Body"]))

    doc.build(story)
    return out_path


def _make_roi_pdf(out_path: str):
    """Generate the sample ROI report PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    styles = _styles()
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = []
    story.append(Paragraph("RecruitProof — ROI Snapshot", styles["Title2"]))
    story.append(Paragraph(
        "<b><font color='#9333ea'>SAMPLE — SYNTHETIC DATA FOR DEMONSTRATION ONLY</font></b><br/>"
        "Customer: <b>[Pilot Customer]</b> &nbsp;·&nbsp; "
        "Team: 75 recruiters &nbsp;·&nbsp; "
        f"Generated: {time.strftime('%Y-%m-%d', time.gmtime())}",
        styles["Sub"]))

    # Headline savings
    story.append(Paragraph("Annual Savings", styles["H2"]))
    savings_tbl = Table([
        ["Annual software savings", "$133,800", "78%"],
        ["Recruiter hours saved / year", "42,300", "12 hrs/wk × 75"],
        ["Recruiter productivity savings", "$317,250", "$75/hr × 42,300"],
        ["Time-to-fill reduction", "19 days", "47 → 28 days (40%)"],
        ["5-year TCO savings", "$669,000", "78% over 5 years"],
    ], colWidths=[2.5 * inch, 1.4 * inch, 2 * inch])
    savings_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dcfce7")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#15803d")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#15803d")),
    ]))
    story.append(savings_tbl)

    # TCO breakdown
    story.append(Paragraph("Year 1 TCO Breakdown", styles["H2"]))
    tco_rows = [
        ["Line item", "Traditional", "RecruitProof", "Savings"],
        ["ATS License (75 seats)", "$72,000", "—", "$72,000"],
        ["AI Screening Add-on", "$45,000", "—", "$45,000"],
        ["Resume Search / Sourcing", "$24,000", "—", "$24,000"],
        ["Professional Services", "$18,000", "—", "$18,000"],
        ["Premium Support", "$12,000", "—", "$12,000"],
        ["Cloud VM (m5.4xlarge)", "—", "$6,000", "—"],
        ["Enterprise Support (24×7)", "—", "$12,000", "—"],
        ["Annual License", "—", "$18,000", "—"],
        ["Backup Storage (1 TB)", "—", "$1,200", "—"],
        ["TOTAL", "$171,000", "$37,200", "$133,800"],
    ]
    tco_tbl = Table(tco_rows, colWidths=[2.5 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch])
    tco_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tco_tbl)

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "<i>Based on the 75-recruiter team profile. 5-year cumulative savings: $669,000. "
        "Does not include $1.5M+ in productivity gains over 5 years.</i>",
        styles["Body"]))

    doc.build(story)
    return out_path


def _make_deletion_pdf(out_path: str):
    """Generate the sample deletion certificate PDF."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle

    styles = _styles()
    styles.add(ParagraphStyle(name="Center", parent=styles["Normal"],
                              fontSize=11, alignment=TA_CENTER, spaceAfter=6))
    doc = SimpleDocTemplate(out_path, pagesize=letter,
                            topMargin=1 * inch, bottomMargin=1 * inch,
                            leftMargin=1 * inch, rightMargin=1 * inch)
    story = []
    story.append(Paragraph("RecruitProof", styles["Center"]))
    story.append(Paragraph("Deletion Certificate", styles["Center"]))
    story.append(Paragraph("<b><font color='#9333ea'>SAMPLE — SYNTHETIC, FOR DEMONSTRATION ONLY</font></b>", styles["Center"]))
    story.append(Spacer(1, 24))

    cert_id = f"DEL-{time.strftime('%Y%m%d', time.gmtime())}-001"
    story.append(Paragraph(f"<b>Certificate ID:</b> {cert_id}", styles["Center"]))
    story.append(Paragraph(f"<b>Customer:</b> [Pilot Customer]", styles["Center"]))
    story.append(Paragraph(f"<b>Run ID:</b> proof_run_001", styles["Center"]))
    story.append(Paragraph(f"<b>Timestamp:</b> {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                          styles["Center"]))
    story.append(Spacer(1, 36))

    story.append(Paragraph(
        "This certifies that <b>500,000</b> raw resume files "
        "(<b>47.3 GB</b>) were permanently deleted from RecruitProof infrastructure "
        "within 24 hours of pilot delivery.",
        styles["Body"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Each file was SHA-256 hashed before deletion. The full hash manifest is "
        "preserved in the accompanying JSON certificate.",
        styles["Body"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<b>Remaining artifacts:</b><br/>"
        "&nbsp;&nbsp;• 3 shortlists (300 candidate records, JSON)<br/>"
        "&nbsp;&nbsp;• hidden_candidates.csv (12 records, no PII)<br/>"
        "&nbsp;&nbsp;• failed_files.csv (12,580 records — filenames only, no PII)<br/>"
        "&nbsp;&nbsp;• proof_run_001_report.pdf",
        styles["Body"]))
    story.append(Spacer(1, 36))
    story.append(Paragraph("_________________________", styles["Center"]))
    story.append(Paragraph("Scrutexity Authorized Signatory", styles["Center"]))

    doc.build(story)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — demo PDF generator")
    ap.add_argument("--out", default="demo/", help="Output directory for the 3 PDFs")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[demo] generating 3 PDFs in {out_dir}/", file=sys.stderr)

    shortlist = _make_shortlist_pdf(str(out_dir / "sample_shortlist.pdf"))
    print(f"[demo] ✓ {shortlist}", file=sys.stderr)

    roi = _make_roi_pdf(str(out_dir / "sample_roi_report.pdf"))
    print(f"[demo] ✓ {roi}", file=sys.stderr)

    deletion = _make_deletion_pdf(str(out_dir / "sample_deletion_certificate.pdf"))
    print(f"[demo] ✓ {deletion}", file=sys.stderr)

    print(f"\n[demo] DONE — 3 PDFs in {out_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
