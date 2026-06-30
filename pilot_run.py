#!/usr/bin/env python3
"""
pilot_run.py — One-ZIP Proof Runner
====================================

The single command that turns an Encore ZIP export + a job description into
a complete evidence packet. This is the Rudy pilot deliverable generator.

Usage:
    python pilot_run.py \\
        --zip imports/encore_export.zip \\
        --jd data/jds/senior_backend.txt \\
        --out runs/pilot_001 \\
        --top 50 \\
        --delete-raw \\
        --label "Encore Sample Pilot"

Output (in --out directory):
    run_manifest.json          — top-level metadata + hashes
    ingest_report.json         — files received/parsed/failed/duplicates
    failed_files.csv           — per-file failure reasons
    duplicates.csv             — detected duplicate pairs
    candidates.jsonl           — all parsed candidates (for precompute.py)
    shortlist_top50.csv        — ranked shortlist (spreadsheet-importable)
    shortlist_top50.pdf        — ranked shortlist (executive PDF)
    candidate_explanations.json — per-candidate 5-signal breakdown + reasoning
    proof_report.pdf           — the 4-metric proof report
    deletion_receipt.pdf       — proof that raw files were deleted
    deletion_receipt.json      — SHA-256 hash manifest of deleted files
    audit_ledger.jsonl         — hash-chained audit log of every action
    evidence_packet.zip        — all of the above, zipped for delivery

Pipeline:
    1. ingest_encore.py        — ZIP → candidates.jsonl + failed_files.csv
    2. precompute.py --hybrid  — candidates.jsonl → FAISS + BM25 index
    3. search.py --hybrid      — JD → ranked shortlist with explanations
    4. generate_proof_report.py — run metadata → proof_report.pdf
    5. delete_raw_files.py     — delete raw files → deletion_receipt.pdf
    6. audit_ledger.py         — hash-chain all events → audit_ledger.jsonl
    7. zip evidence packet     — everything → evidence_packet.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


# Add repo root to path
REPO_ROOT = Path(__file__).parent
sys.path.insert(0, str(REPO_ROOT))


def _run(cmd: List[str], label: str, ledger: List[Dict]) -> subprocess.CompletedProcess:
    """Run a subprocess, log to ledger, return the result."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  {label}", file=sys.stderr)
    print(f"  cmd: {' '.join(cmd[:4])}...", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    elapsed = time.time() - t0
    # Log to audit ledger
    ledger.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": label.lower().replace(" ", "_"),
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "stdout_lines": len(result.stdout.splitlines()),
        "stderr_lines": len(result.stderr.splitlines()),
    })
    if result.returncode != 0:
        print(f"  ⚠ {label} returned exit code {result.returncode}", file=sys.stderr)
        print(f"  stderr (last 5 lines):", file=sys.stderr)
        for line in result.stderr.strip().splitlines()[-5:]:
            print(f"    {line}", file=sys.stderr)
    else:
        print(f"  ✓ {label} completed in {elapsed:.1f}s", file=sys.stderr)
    return result


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_shortlist_pdf(run_dir: Path, shortlist_json: str, out_pdf: str, label: str) -> None:
    """Build a shortlist PDF from search results JSON using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_LEFT

    with open(shortlist_json) as f:
        data = json.load(f)

    results = data.get("results", [])
    parsed_jd = data.get("parsed_jd", {})

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", parent=styles["Title"],
                              fontSize=22, textColor=colors.HexColor("#0f766e"), spaceAfter=6))
    styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"],
                              fontSize=11, textColor=colors.HexColor("#475569"), spaceAfter=18))
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"],
                              fontSize=10, spaceAfter=4))
    styles.add(ParagraphStyle(name="Reason", parent=styles["Normal"],
                              fontSize=9, textColor=colors.HexColor("#64748b"), spaceAfter=8))

    doc = SimpleDocTemplate(out_pdf, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = []

    story.append(Paragraph("RecruitProof — Shortlist", styles["H1"]))
    story.append(Paragraph(
        f"<b><font color='#9333ea'>PILOT OUTPUT — {label}</font></b><br/>"
        f"Role: <b>{parsed_jd.get('title', 'N/A')}</b> &nbsp;·&nbsp; "
        f"Generated: {time.strftime('%Y-%m-%d', time.gmtime())} &nbsp;·&nbsp; "
        f"Top {len(results)} candidates",
        styles["Sub"]))

    # Table
    rows = [["#", "Name", "Title @ Company", "YoE", "Score", "Missing skills"]]
    for r in results:
        name = r.get("name", "?")
        title = (r.get("current_title") or "")[:25]
        company = (r.get("current_company") or "")[:15]
        yoe = r.get("years_experience")
        yoe_str = f"{yoe}y" if yoe is not None else "?"
        score = r.get("score_10", 0)
        missing = ", ".join(r.get("missing_skills", [])[:3]) or "—"
        rows.append([str(r.get("rank", "")), name[:20], f"{title} @ {company}",
                     yoe_str, f"{score}", missing[:30]])

    tbl = Table(rows, colWidths=[0.3*inch, 1.3*inch, 2.2*inch, 0.5*inch, 0.6*inch, 1.8*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#dcfce7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 18))

    # Top 3 details
    story.append(Paragraph("Top 3 Details", styles["H1"]))
    for r in results[:3]:
        story.append(Paragraph(
            f"<b>#{r.get('rank')} {r.get('name', '?')} — {r.get('score_10', 0)}/10</b>",
            styles["Body"]))
        sig = r.get("signals", {})
        story.append(Paragraph(
            f"Semantic={sig.get('semantic', 0):.2f} · Role-Fit={sig.get('role_fit', 0):.2f} · "
            f"Skills={sig.get('skills', 0):.2f} · Behavioral={sig.get('behavioral', 0):.2f} · "
            f"Career={sig.get('career', 0):.2f}",
            styles["Body"]))
        matched = ", ".join(r.get("matched_skills", [])[:5]) or "—"
        missing = ", ".join(r.get("missing_skills", [])) or "(none — full coverage)"
        story.append(Paragraph(f"✓ Matched: {matched}", styles["Body"]))
        story.append(Paragraph(f"✗ Missing: {missing}", styles["Body"]))
        story.append(Paragraph(f"→ {r.get('reasoning', '')}", styles["Reason"]))

    doc.build(story)
    print(f"  ✓ Shortlist PDF → {out_pdf}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description="RecruitProof — One-ZIP Proof Runner. Turns an Encore ZIP + JD into a complete evidence packet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python pilot_run.py --zip imports/export.zip --jd data/jds/senior_backend.txt --out runs/pilot_001 --top 50 --delete-raw
        """.strip(),
    )
    ap.add_argument("--zip", required=True, help="Path to the Encore export ZIP")
    ap.add_argument("--jd", required=True, help="Path to the job description .txt file")
    ap.add_argument("--out", required=True, help="Output directory for the evidence packet")
    ap.add_argument("--top", type=int, default=50, help="Number of top candidates (default: 50)")
    ap.add_argument("--delete-raw", action="store_true", help="Delete raw resume files after processing")
    ap.add_argument("--label", default="Pilot Run", help="Label for the report header")
    ap.add_argument("--customer", default="[Customer]", help="Customer name for reports")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini", help="Embedding model (default: mini)")
    args = ap.parse_args()

    run_dir = Path(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name

    ledger: List[Dict] = []
    t_start = time.time()

    print(f"\n{'#'*60}", file=sys.stderr)
    print(f"  RecruitProof Pilot Run", file=sys.stderr)
    print(f"  Run ID: {run_id}", file=sys.stderr)
    print(f"  ZIP: {args.zip}", file=sys.stderr)
    print(f"  JD: {args.jd}", file=sys.stderr)
    print(f"  Output: {run_dir}", file=sys.stderr)
    print(f"  Top-K: {args.top}", file=sys.stderr)
    print(f"  Delete raw: {args.delete_raw}", file=sys.stderr)
    print(f"{'#'*60}", file=sys.stderr)

    # Step 1: Ingest
    ingest_result = _run([
        sys.executable, "ingest_encore.py",
        "--input", args.zip,
        "--output", str(run_dir),
    ], "Step 1: Ingest Encore ZIP", ledger)

    candidates_jsonl = run_dir / "candidates.jsonl"
    if not candidates_jsonl.exists():
        print(f"\n❌ FATAL: Ingest did not produce candidates.jsonl. Pipeline stopped.", file=sys.stderr)
        _write_manifest(run_dir, ledger, t_start, args, status="failed", error="ingest_failed")
        sys.exit(1)

    # Step 2: Build hybrid index
    index_dir = run_dir / "index"
    precompute_result = _run([
        sys.executable, "precompute.py",
        "--candidates", str(candidates_jsonl),
        "--output", str(index_dir),
        "--model", args.model,
        "--index", "flat",
        "--hybrid",
    ], "Step 2: Build FAISS + BM25 hybrid index", ledger)

    if not (index_dir / "candidates.faiss").exists():
        print(f"\n❌ FATAL: Precompute did not produce candidates.faiss. Pipeline stopped.", file=sys.stderr)
        _write_manifest(run_dir, ledger, t_start, args, status="failed", error="precompute_failed")
        sys.exit(1)

    # Step 3: Search
    shortlist_json = run_dir / f"shortlist_top{args.top}.json"
    shortlist_csv = run_dir / f"shortlist_top{args.top}.csv"
    search_result = _run([
        sys.executable, "search.py",
        "--jd", args.jd,
        "--top", str(args.top),
        "--hybrid",
        "--index", str(index_dir),
        "--candidates", str(candidates_jsonl),
        "--json", str(shortlist_json),
        "--csv", str(shortlist_csv),
    ], f"Step 3: Search top-{args.top} candidates", ledger)

    if not shortlist_json.exists():
        print(f"\n❌ FATAL: Search did not produce shortlist JSON. Pipeline stopped.", file=sys.stderr)
        _write_manifest(run_dir, ledger, t_start, args, status="failed", error="search_failed")
        sys.exit(1)

    # Step 4: Build shortlist PDF
    print(f"\n  Step 4: Build shortlist PDF...", file=sys.stderr)
    shortlist_pdf = run_dir / f"shortlist_top{args.top}.pdf"
    try:
        _build_shortlist_pdf(run_dir, str(shortlist_json), str(shortlist_pdf), args.label)
        ledger.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "action": "build_shortlist_pdf", "returncode": 0, "elapsed_seconds": 0.1})
    except Exception as e:
        print(f"  ⚠ Shortlist PDF failed: {e}", file=sys.stderr)
        ledger.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "action": "build_shortlist_pdf", "returncode": 1, "error": str(e)})

    # Step 5: Generate proof report
    proof_report = run_dir / "proof_report.pdf"
    _run([
        sys.executable, "proof/million_cv_scan/generate_proof_report.py",
        "--run", str(run_dir),
        "--out", str(proof_report),
        "--customer", args.customer,
    ], "Step 5: Generate proof report PDF", ledger)

    # Step 6: Delete raw files (if requested)
    deletion_receipt_pdf = run_dir / "deletion_receipt.pdf"
    deletion_receipt_json = run_dir / "deletion_receipt.json"
    if args.delete_raw:
        _run([
            sys.executable, "proof/million_cv_scan/delete_raw_files.py",
            "--run", str(run_dir),
            "--confirm",
            "--customer", args.customer,
        ], "Step 6: Delete raw resume files + generate deletion receipt", ledger)

    # Step 7: Write audit ledger using the hash-chained AuditLedger class
    from audit_ledger import AuditLedger
    audit_path = run_dir / "audit_ledger.jsonl"
    ledger_obj = AuditLedger(str(audit_path))
    for entry in ledger:
        ledger_obj.append(
            action=entry.get("action", "unknown"),
            details=entry,
            actor="pilot_run.py",
            run_id=run_id,
        )
    print(f"\n  ✓ Audit ledger → {audit_path} ({len(ledger)} events, hash-chained)", file=sys.stderr)

    # Step 8: Write run manifest
    manifest = _write_manifest(run_dir, ledger, t_start, args, status="complete")

    # Step 9: Zip evidence packet
    evidence_zip = run_dir / "evidence_packet.zip"
    print(f"\n  Step 9: Assembling evidence packet → {evidence_zip}", file=sys.stderr)
    with zipfile.ZipFile(evidence_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in run_dir.iterdir():
            if p.name == "evidence_packet.zip" or p.is_dir():
                continue
            zf.write(p, p.name)
    print(f"  ✓ Evidence packet → {evidence_zip} ({evidence_zip.stat().st_size / 1024:.0f} KB)", file=sys.stderr)

    # Summary
    elapsed = time.time() - t_start
    print(f"\n{'#'*60}", file=sys.stderr)
    print(f"  PILOT RUN COMPLETE", file=sys.stderr)
    print(f"  Run ID: {run_id}", file=sys.stderr)
    print(f"  Total time: {elapsed:.1f}s", file=sys.stderr)
    print(f"  Output: {run_dir}", file=sys.stderr)
    print(f"  Evidence packet: {evidence_zip}", file=sys.stderr)
    print(f"{'#'*60}", file=sys.stderr)


def _write_manifest(run_dir: Path, ledger: List[Dict], t_start: float,
                    args: argparse.Namespace, status: str, error: str = "") -> Dict:
    """Write run_manifest.json with hashes of all output files."""
    manifest = {
        "run_id": run_dir.name,
        "status": status,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": round(time.time() - t_start, 2),
        "input_zip": args.zip,
        "input_jd": args.jd,
        "top_k": args.top,
        "delete_raw": args.delete_raw,
        "label": args.label,
        "customer": args.customer,
        "model": args.model,
        "files": {},
        "audit_events": len(ledger),
    }
    if error:
        manifest["error"] = error

    # Hash all output files
    for p in run_dir.iterdir():
        if p.is_file() and p.name != "run_manifest.json":
            manifest["files"][p.name] = {
                "size_bytes": p.stat().st_size,
                "sha256": _sha256_file(str(p)),
            }

    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✓ Run manifest → {manifest_path}", file=sys.stderr)
    return manifest


if __name__ == "__main__":
    main()
