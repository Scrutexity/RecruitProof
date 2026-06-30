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
import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

from delete_raw_files import generate_deletion_receipt
from generate_shortlist_pdf import create_shortlist_pdf


# Default timeout per pipeline step (seconds). Prevents hangs on malformed files.
STEP_TIMEOUT = 600


class AuditLog:
    """Hash-chained audit log. Every entry includes the SHA-256 of the previous
    entry, making the log tamper-evident: editing any row breaks the chain."""

    def __init__(self, path: Path):
        self.path = path
        self.prev_hash = None
        self._init_chain()

    def _init_chain(self):
        if self.path.exists():
            # Resume from last entry's hash
            lines = self.path.read_text().strip().split("\n")
            if lines and lines[-1].strip():
                try:
                    self.prev_hash = lines[-1].split("|")[2].strip()
                except IndexError:
                    self.prev_hash = None
            else:
                self.prev_hash = None

    def write(self, msg: str) -> str:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        chain_input = (self.prev_hash or "") + msg
        chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()[:16]
        entry = "[{}] {} | {}".format(ts, msg, chain_hash)
        with open(self.path, "a") as f:
            f.write(entry + "\n")
        self.prev_hash = chain_hash
        return entry


def _stream_subprocess(cmd, log, step_label, timeout=STEP_TIMEOUT):
    """Run a subprocess, streaming stdout/stderr to the audit log in real time."""
    log.write("{}: starting".format(step_label))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        last_line = ""
        for line in proc.stdout:
            stripped = line.rstrip("\n")
            if stripped:
                log.write("  {}: {}".format(step_label, stripped))
                last_line = stripped
        proc.wait(timeout=timeout)
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        log.write("{}: completed (exit 0)".format(step_label))
        return last_line
    except subprocess.TimeoutExpired:
        proc.kill()
        log.write("{}: TIMEOUT after {}s — killed".format(step_label, timeout))
        raise


def run_pilot(input_zip: Path, jd_file: Path, output_dir: Path, auto_delete: bool = False):
    output_dir.mkdir(parents=True, exist_ok=True)

    audit = AuditLog(output_dir / "audit.chain.log")
    plain_log = output_dir / "pilot.log"

    def log(msg):
        entry = audit.write(msg)
        with open(plain_log, "a") as f:
            f.write(entry + "\n")
        print(entry)

    try:
        # ── Step 1: Ingest Encore ZIP ──────────────────────────────
        log("Step 1/4: Ingesting Encore ZIP...")
        ingest_dir = output_dir / "ingested"
        ingest_dir.mkdir(parents=True, exist_ok=True)

        _stream_subprocess(
            [sys.executable, "ingest_encore.py",
             "--input", str(input_zip),
             "--output", str(ingest_dir)],
            audit, "ingest",
        )
        candidates_jsonl = ingest_dir / "candidates.jsonl"
        if not candidates_jsonl.exists():
            log("ERROR: candidates.jsonl not found at {}".format(candidates_jsonl))
            sys.exit(1)

        # Verify we got actual candidates, not an empty ingest
        line_count = 0
        with open(candidates_jsonl) as f:
            for _ in f:
                line_count += 1
                if line_count > 1:
                    break
        if line_count == 0:
            log("ERROR: candidates.jsonl is empty — no usable resumes extracted from ZIP")
            sys.exit(1)

        log("  ✓ Ingestion complete — {} candidates".format(
            sum(1 for _ in open(candidates_jsonl))))

        # ── Step 2: Build hybrid index (FAISS + BM25) ──────────────
        log("Step 2/4: Building search index...")
        index_dir = output_dir / "index"

        _stream_subprocess(
            [sys.executable, "precompute.py",
             "--candidates", str(candidates_jsonl),
             "--output", str(index_dir),
             "--model", "mini",
             "--index", "flat",
             "--hybrid"],
            audit, "index",
        )
        if not (index_dir / "candidates.faiss").exists():
            log("ERROR: candidates.faiss not found at {}".format(index_dir))
            sys.exit(1)
        log("  ✓ Index built at {}".format(index_dir))

        # ── Step 3: Rank candidates against JD ─────────────────────
        log("Step 3/4: Ranking candidates against job description...")
        search_out = output_dir / "search_results.json"

        _stream_subprocess(
            [sys.executable, "search.py",
             "--jd", str(jd_file),
             "--top", "50",
             "--index", str(index_dir),
             "--json", str(search_out),
             "--hybrid"],
            audit, "search",
        )
        jd_text = jd_file.read_text(encoding="utf-8")
        if not search_out.exists():
            log("ERROR: search results not found at {}".format(search_out))
            sys.exit(1)

        import json
        with open(search_out) as f:
            results = json.load(f)
        result_count = len(results) if isinstance(results, list) else len(results.get("results", []))
        log("  ✓ Search complete — {} candidates ranked → {}".format(result_count, search_out))

        # ── Step 4: Generate shortlist PDF ─────────────────────────
        log("Step 4/4: Generating recruiter-ready shortlist PDF...")
        pdf_path = output_dir / "shortlist.pdf"
        create_shortlist_pdf(search_out, jd_text, pdf_path)
        log("  ✓ Shortlist PDF → {}".format(pdf_path))

        # ── Optional: Delete ALL derived data + receipt ────────────
        receipt_path = None
        if auto_delete:
            log("Auto-delete: wiping raw files, index, and search results...")

            # 1. Delete raw ingested resume files (hash-chain receipt)
            receipt_path = output_dir / "deletion_receipt.json"
            generate_deletion_receipt(ingest_dir, receipt_path)

            # 2. Delete derived index files (contain embedded PII)
            if index_dir.exists():
                shutil.rmtree(index_dir)

            # 3. Delete structured search results (contain names, companies, skills)
            if search_out.exists():
                search_out.unlink()

            log("  ✓ All data deleted. Raw receipt → {} | Index & search results wiped".format(
                receipt_path))

        log("✅ Pilot completed successfully.")
        audit.write("PILOT COMPLETE | auto_delete={} | output_dir={}".format(
            auto_delete, output_dir))
        return pdf_path, receipt_path

    except subprocess.CalledProcessError as e:
        log("❌ Command failed (exit {}): {}".format(e.returncode, " ".join(str(a) for a in e.cmd)))
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log("❌ Step timed out — killed. Check input files for corruption.")
        sys.exit(1)
    except Exception as e:
        log("❌ Unexpected error: {}".format(e))
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
                        help="Delete all data after processing (raw + index + results)")
    args = parser.parse_args()

    print("=" * 56)
    print("  RecruitProof Pilot — One-Click Executor")
    print("=" * 56)
    print("  ZIP:       {}".format(args.input_zip))
    print("  JD:        {}".format(args.jd_file))
    print("  Output:    {}".format(args.output_dir))
    print("  Auto-delete: {}".format(args.auto_delete))
    print("=" * 56)

    pdf, receipt = run_pilot(args.input_zip, args.jd_file, args.output_dir, args.auto_delete)

    print("\n{}".format("=" * 56))
    print("  \u2705  PILOT COMPLETE")
    print("{}".format("=" * 56))
    print("  \U0001f4c4 Shortlist:        {}".format(pdf))
    if receipt:
        print("  \U0001f9fe Deletion receipt: {}".format(receipt))
    print("  \U0001f4cb Audit log:        {}".format(args.output_dir / "audit.chain.log"))
    print("{}".format("=" * 56))


if __name__ == "__main__":
    main()
