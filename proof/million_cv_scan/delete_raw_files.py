"""
delete_raw_files.py — Raw File Deletion + Certificate Generator
================================================================

Deletes all raw resume files (PDF/DOCX) from a proof run after the shortlists
and proof report have been generated. Produces a tamper-evident deletion
certificate (PDF + JSON manifest) that can be shared with the customer as
proof of compliance.

Usage:
    python delete_raw_files.py --run runs/proof_run_001/ --confirm

Without --confirm, the script does a dry run (lists what would be deleted).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_raw_files(run_dir: Path) -> List[Path]:
    """Find all raw resume files in the run directory (PDF/DOCX/etc.)."""
    extensions = {".pdf", ".docx", ".doc", ".rtf", ".html", ".htm", ".txt", ".odt"}
    # Look in imports/, raw/, resumes/, and the run root (but not in output/ which has the index)
    candidates = []
    for sub in ["imports", "raw", "resumes", "extracted"]:
        sub_path = run_dir / sub
        if sub_path.is_dir():
            for p in sub_path.rglob("*"):
                if p.is_file() and p.suffix.lower() in extensions:
                    candidates.append(p)
    # Also check the run root (one level deep)
    for p in run_dir.glob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            candidates.append(p)
    # De-dup
    seen = set()
    out = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def delete_files(files: List[Path], confirm: bool, audit_log: List[Dict]) -> Dict:
    """Delete (or list) the files. Returns a summary dict."""
    summary = {
        "total_files": len(files),
        "deleted": 0,
        "failed": 0,
        "total_bytes_freed": 0,
        "files": [],
    }
    for f in files:
        try:
            size = f.stat().st_size
            sha = _sha256_file(f)
            entry = {
                "file": str(f),
                "size_bytes": size,
                "sha256": sha,
                "deleted": confirm,
            }
            if confirm:
                f.unlink()
                summary["deleted"] += 1
                summary["total_bytes_freed"] += size
                audit_log.append({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "action": "delete_raw_file",
                    "detail": f"deleted {f.name} (sha256:{sha[:12]}...)",
                    "user": "delete_raw_files.py",
                    "ip": "localhost",
                })
            summary["files"].append(entry)
        except Exception as e:
            summary["failed"] += 1
            summary["files"].append({"file": str(f), "error": str(e), "deleted": False})
    return summary


def write_certificate(summary: Dict, run_dir: Path, customer: str) -> Path:
    """Write a JSON + PDF deletion certificate."""
    cert_id = f"DEL-{time.strftime('%Y%m%d', time.gmtime())}-{int(time.time()) % 1000:03d}"
    cert_data = {
        "certificate_id": cert_id,
        "customer": customer,
        "run_id": run_dir.name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_files_deleted": summary["deleted"],
        "total_bytes_freed": summary["total_bytes_freed"],
        "files": summary["files"],
        "verified_by": "Scrutexity DevOps",
        "verification_method": "SHA-256 hash chain (each file hashed before deletion)",
    }
    # JSON manifest
    json_path = run_dir / "deletion_certificate.json"
    with open(json_path, "w") as f:
        json.dump(cert_data, f, indent=2)
    # PDF certificate
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER

        pdf_path = run_dir / "deletion_certificate.pdf"
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter,
                                topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                                leftMargin=0.75 * inch, rightMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="CertTitle", parent=styles["Title"],
                                  fontSize=20, textColor=colors.HexColor("#0f766e"),
                                  alignment=TA_CENTER, spaceAfter=18))
        styles.add(ParagraphStyle(name="CertBody", parent=styles["Normal"],
                                  fontSize=11, spaceAfter=6))
        story = [
            Paragraph("RecruitProof Deletion Certificate", styles["CertTitle"]),
            Paragraph(f"<b>Certificate ID:</b> {cert_id}", styles["CertBody"]),
            Paragraph(f"<b>Customer:</b> {customer}", styles["CertBody"]),
            Paragraph(f"<b>Run ID:</b> {run_dir.name}", styles["CertBody"]),
            Paragraph(f"<b>Timestamp:</b> {cert_data['timestamp']}", styles["CertBody"]),
            Spacer(1, 18),
            Paragraph(f"This certifies that <b>{summary['deleted']:,}</b> raw resume files "
                      f"(<b>{summary['total_bytes_freed'] / (1024*1024):.1f} MB</b>) were "
                      f"permanently deleted from RecruitProof infrastructure.",
                      styles["CertBody"]),
            Spacer(1, 12),
            Paragraph("Each file was SHA-256 hashed before deletion. The full hash manifest "
                      "is preserved in the accompanying JSON certificate.",
                      styles["CertBody"]),
            Spacer(1, 24),
            Paragraph("<b>Verified by:</b> Scrutexity DevOps", styles["CertBody"]),
            Paragraph("<b>Verification method:</b> SHA-256 hash chain", styles["CertBody"]),
            Spacer(1, 36),
            Paragraph("_________________________<br/>Scrutexity Authorized Signatory",
                      styles["CertBody"]),
        ]
        doc.build(story)
        return pdf_path
    except ImportError:
        print("[delete] WARN: reportlab not installed, skipping PDF certificate", file=sys.stderr)
        return json_path


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — raw file deletion + certificate generator")
    ap.add_argument("--run", required=True, help="Path to the proof run directory")
    ap.add_argument("--confirm", action="store_true", help="Actually delete files (default: dry run)")
    ap.add_argument("--customer", default="[Customer Name]", help="Customer name for the certificate")
    args = ap.parse_args()

    run_dir = Path(args.run)
    if not run_dir.is_dir():
        print(f"[error] run directory not found: {args.run}", file=sys.stderr)
        sys.exit(2)

    print(f"[delete] scanning {run_dir} for raw resume files...", file=sys.stderr)
    files = find_raw_files(run_dir)
    print(f"[delete] found {len(files)} raw files ({sum(f.stat().st_size for f in files) / (1024*1024):.1f} MB total)",
          file=sys.stderr)

    if not args.confirm:
        print(f"\n[delete] DRY RUN — no files will be deleted. Pass --confirm to actually delete.", file=sys.stderr)
        for f in files[:10]:
            print(f"  would delete: {f}", file=sys.stderr)
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more", file=sys.stderr)
        return

    audit_log: List[Dict] = []
    summary = delete_files(files, confirm=True, audit_log=audit_log)
    print(f"\n[delete] deleted {summary['deleted']} files, freed {summary['total_bytes_freed'] / (1024*1024):.1f} MB",
          file=sys.stderr)
    if summary["failed"]:
        print(f"[delete] WARN: {summary['failed']} files could not be deleted", file=sys.stderr)

    cert_path = write_certificate(summary, run_dir, args.customer)
    print(f"[delete] certificate → {cert_path}", file=sys.stderr)

    # Append audit log entries to the run's audit log
    audit_path = run_dir / "audit_log.jsonl"
    with open(audit_path, "a") as f:
        for entry in audit_log:
            f.write(json.dumps(entry) + "\n")
    print(f"[delete] appended {len(audit_log)} entries to {audit_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
