#!/usr/bin/env python3
"""
RecruitProof Pilot Executor for Rudy
=====================================
Single command: Encore ZIP + JD → ranked shortlist PDF + deletion receipt.
Zero data leaves the machine. Fully auditable.

Usage:
    python pilot_executor.py --input-zip exports/encore.zip \\
        --jd-file jd.txt --output-dir ./pilot_output
    python pilot_executor.py --input-zip exports/encore.zip --jd-file jd.txt --auto-delete
"""

import argparse
import sys
import time
from pathlib import Path

from delete_raw_files import generate_deletion_receipt
from generate_shortlist_pdf import create_shortlist_pdf


def run_pilot(input_zip: Path, jd_file: Path, output_dir: Path, auto_delete: bool = False):
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "pilot.log"

    def log(msg):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {msg}"
        with open(log_file, "a") as f:
            f.write(entry + "\n")
        print(entry)

    try:
        # ── Step 1: Ingest Encore ZIP ──────────────────────────────
        log("Step 1/4: Ingesting Encore ZIP...")
        ingest_dir = output_dir / "ingested"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        import subprocess
        subprocess.run(
            [sys.executable, "ingest_encore.py",
             "--input", str(input_zip),
             "--output", str(ingest_dir)],
            check=True, capture_output=True, text=True
        )
        candidates_jsonl = ingest_dir / "candidates.jsonl"
        if not candidates_jsonl.exists():
            log(f"ERROR: candidates.jsonl not found at {candidates_jsonl}")
            sys.exit(1)
        log(f"  ✓ Ingestion complete. Candidates: {candidates_jsonl}")

        # ── Step 2: Build hybrid index (FAISS + BM25) ──────────────
        log("Step 2/4: Building search index (small-batch mode)...")
        index_dir = output_dir / "index"
        subprocess.run(
            [sys.executable, "precompute.py",
             "--candidates", str(candidates_jsonl),
             "--output", str(index_dir),
             "--model", "mini",
             "--index", "flat",
             "--hybrid"],
            check=True, capture_output=True, text=True
        )
        if not (index_dir / "candidates.faiss").exists():
            log(f"ERROR: candidates.faiss not found at {index_dir}")
            sys.exit(1)
        log(f"  ✓ Index built at {index_dir}")

        # ── Step 3: Rank candidates against JD ─────────────────────
        log("Step 3/4: Ranking candidates against job description...")
        jd_text = jd_file.read_text(encoding="utf-8")
        search_out = output_dir / "search_results.json"
        subprocess.run(
            [sys.executable, "search.py",
             "--jd", jd_text,
             "--top", "50",
             "--index", str(index_dir),
             "--json", str(search_out),
             "--hybrid"],
            check=True, capture_output=True, text=True
        )
        if not search_out.exists():
            log(f"ERROR: search results not found at {search_out}")
            sys.exit(1)
        log(f"  ✓ Search complete → {search_out}")

        # ── Step 4: Generate shortlist PDF ─────────────────────────
        log("Step 4/4: Generating recruiter-ready shortlist PDF...")
        pdf_path = output_dir / "shortlist.pdf"
        create_shortlist_pdf(search_out, jd_text, pdf_path)
        log(f"  ✓ Shortlist PDF → {pdf_path}")

        # ── Optional: Delete raw data + receipt ────────────────────
        receipt_path = None
        if auto_delete:
            log("Auto-delete: erasing raw ingested files...")
            receipt_path = output_dir / "deletion_receipt.json"
            generate_deletion_receipt(ingest_dir, receipt_path)
            log(f"  ✓ Raw data deleted. Receipt → {receipt_path}")

        log("✅ Pilot completed successfully.")
        return pdf_path, receipt_path

    except subprocess.CalledProcessError as e:
        log(f"❌ Command failed (exit {e.returncode}): {e.cmd}")
        log(f"   stderr: {e.stderr[-500:]}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="RecruitProof — Rudy Pilot One-Click Executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python pilot_executor.py --input-zip exports/encore.zip \\\n"
            "      --jd-file jd.txt --output-dir ./pilot_output --auto-delete"
        ),
    )
    parser.add_argument("--input-zip", type=Path, required=True,
                        help="Path to Encore export ZIP")
    parser.add_argument("--jd-file", type=Path, required=True,
                        help="Job description text file")
    parser.add_argument("--output-dir", type=Path, default=Path("./pilot_output"),
                        help="Output directory (default: ./pilot_output)")
    parser.add_argument("--auto-delete", action="store_true",
                        help="Delete raw data after processing (produces deletion receipt)")
    args = parser.parse_args()

    print("=" * 56)
    print("  RecruitProof Pilot — One-Click Executor")
    print("=" * 56)
    print(f"  ZIP:       {args.input_zip}")
    print(f"  JD:        {args.jd_file}")
    print(f"  Output:    {args.output_dir}")
    print(f"  Auto-delete: {args.auto_delete}")
    print("=" * 56)

    pdf, receipt = run_pilot(args.input_zip, args.jd_file, args.output_dir, args.auto_delete)

    print(f"\n{'=' * 56}")
    print("  \u2705  PILOT COMPLETE")
    print(f"{'=' * 56}")
    print(f"  📄 Shortlist:        {pdf}")
    if receipt:
        print(f"  🧾 Deletion receipt: {receipt}")
    print(f"  📋 Pilot log:        {args.output_dir / 'pilot.log'}")
    print(f"{'=' * 56}")


if __name__ == "__main__":
    main()
