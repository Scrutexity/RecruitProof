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

    # Verify an existing audit log's hash chain:
    python pilot_executor.py --verify-log ./pilot_output/audit.chain.log
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from delete_raw_files import generate_deletion_receipt
from generate_shortlist_pdf import create_shortlist_pdf


STEP_TIMEOUT = 600


class AuditLog:
    """Hash-chained audit log. Each entry includes the SHA-256 of the previous
    entry, making the log tamper-evident: editing any row breaks the chain.

    The genesis entry chains from a fixed seed string so the first entry is
    also verifiable.

    Usage:
        log = AuditLog(Path("audit.chain.log"))
        log.write("pipeline started")
        log.write("step 1 complete")

        # Verify integrity later:
        results = log.verify()
        for line_num, status, detail in results:
            print(f"{line_num}: {status} — {detail}")
    """

    GENESIS_SEED = "RecruitProof Audit Log v1"

    def __init__(self, path: Path):
        self.path = path
        self.prev_hash = None
        self._init_chain()

    def _init_chain(self):
        if self.path.exists():
            lines = self.path.read_text().strip().split("\n")
            if lines and lines[-1].strip():
                try:
                    self.prev_hash = lines[-1].split("|")[1].strip()
                except (IndexError, ValueError):
                    self.prev_hash = None

    def write(self, msg: str) -> str:
        chain_input = (self.prev_hash or self.GENESIS_SEED) + msg
        chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()[:16]
        entry = "{} | {}".format(msg, chain_hash)
        with open(self.path, "a") as f:
            f.write(entry + "\n")
        self.prev_hash = chain_hash
        return entry

    def verify(self) -> list:
        """Walk the log and verify every entry's hash chain.

        Returns list of (line_number, status, detail) tuples where status
        is one of OK, CORRUPT, or TAMPERED. A TAMPERED entry doesn't
        cascade — subsequent entries are checked against the claimed hash
        of the tampered row, not a recomputed one, so one bad entry doesn't
        flag everything after it as also broken.
        """
        results = []
        if not self.path.exists():
            return [(0, "ERROR", "File not found")]
        lines = self.path.read_text().strip().split("\n")
        expected_hash = self.GENESIS_SEED
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.rsplit("|", 1)
            if len(parts) < 2:
                results.append((i, "CORRUPT", "Expected msg | hash format"))
                continue
            msg = parts[0].strip()
            claimed_hash = parts[1].strip()
            chain_input = expected_hash + msg
            computed = hashlib.sha256(chain_input.encode()).hexdigest()[:16]
            if computed == claimed_hash:
                results.append((i, "OK", msg[:80]))
                expected_hash = claimed_hash
            else:
                results.append((i, "TAMPERED",
                    "Expected hash {} but stored hash is {} — entry: {}".format(
                        computed, claimed_hash, msg[:60])))
                expected_hash = claimed_hash
        return results


def _stream_subprocess(cmd, log, step_label, timeout=STEP_TIMEOUT):
    """Run a subprocess, streaming stdout to the audit log in real time."""
    log.write("{}: starting".format(step_label))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for line in proc.stdout:
            stripped = line.rstrip("\n")
            if stripped:
                log.write("  {}: {}".format(step_label, stripped[:200]))
        proc.wait(timeout=timeout)
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
        log.write("{}: completed (exit 0)".format(step_label))
    except subprocess.TimeoutExpired:
        proc.kill()
        log.write("{}: TIMEOUT after {}s — killed".format(step_label, timeout))
        raise


def run_pilot(input_zip: Path, jd_file: Path, output_dir: Path, auto_delete: bool = False):
    output_dir.mkdir(parents=True, exist_ok=True)

    audit = AuditLog(output_dir / "audit.chain.log")

    def log(msg):
        entry = audit.write(msg)
        print("[{}] {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), entry))

    try:
        # ── Step 1: Ingest ─────────────────────────────────────────
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

        line_count = sum(1 for _ in open(candidates_jsonl))
        if line_count == 0:
            log("ERROR: candidates.jsonl is empty — no usable resumes extracted")
            sys.exit(1)
        log("  ✓ Ingestion complete — {} candidates".format(line_count))

        # ── Step 2: Build index ────────────────────────────────────
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

        # ── Step 3: Search ─────────────────────────────────────────
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

        with open(search_out) as f:
            results = json.load(f)
        result_count = len(results) if isinstance(results, list) else len(results.get("results", []))
        log("  ✓ Search complete — {} candidates ranked → {}".format(result_count, search_out))

        # ── Step 4: PDF ────────────────────────────────────────────
        log("Step 4/4: Generating recruiter-ready shortlist PDF...")
        pdf_path = output_dir / "shortlist.pdf"
        create_shortlist_pdf(search_out, jd_text, pdf_path)
        log("  ✓ Shortlist PDF → {}".format(pdf_path))

        # ── Auto-delete ────────────────────────────────────────────
        receipt_path = None
        if auto_delete:
            log("Auto-delete: wiping raw files, index, and search results...")

            receipt_path = output_dir / "deletion_receipt.json"
            generate_deletion_receipt(ingest_dir, receipt_path)

            if index_dir.exists():
                shutil.rmtree(index_dir)

            if search_out.exists():
                search_out.unlink()

            # audit.chain.log and shortlist.pdf are intentionally preserved
            # as they are the deliverable artifacts (no PII)
            log("  ✓ All transient data deleted. Receipt → {}".format(receipt_path))

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


def cmd_verify(audit_log_path: Path):
    """Run hash-chain verification on an existing audit log."""
    if not audit_log_path.exists():
        print("ERROR: audit log not found: {}".format(audit_log_path))
        sys.exit(1)

    log = AuditLog(audit_log_path)
    results = log.verify()

    tampered = 0
    for line_num, status, detail in results:
        if status == "OK":
            print("  {:>4d}  ✅  {}".format(line_num, detail))
        elif status == "TAMPERED":
            tampered += 1
            print("  {:>4d}  🔴  {}".format(line_num, detail))
        else:
            print("  {:>4d}  ⚠️   {}".format(line_num, detail))

    total = len([r for r in results if r[1] in ("OK", "TAMPERED")])
    print("\n---")
    print("Entries checked: {}  |  Tampered: {}  |  Verified: {}".format(
        total, tampered, total - tampered))
    if tampered:
        print("⚠️  CHAIN BROKEN — {} tampered entries detected.".format(tampered))
        sys.exit(1)
    else:
        print("✅  Hash chain intact. Log is authentic.")


def main():
    parser = argparse.ArgumentParser(
        description="RecruitProof — Rudy Pilot One-Click Executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python pilot_executor.py --input-zip exports/encore.zip \\\n"
            "      --jd-file jd.txt --output-dir ./pilot_output --auto-delete\n"
            "  python pilot_executor.py --verify-log ./pilot_output/audit.chain.log"
        ),
    )
    parser.add_argument("--input-zip", type=Path,
                        help="Path to Encore export ZIP")
    parser.add_argument("--jd-file", type=Path,
                        help="Job description text file")
    parser.add_argument("--output-dir", type=Path, default=Path("./pilot_output"),
                        help="Output directory (default: ./pilot_output)")
    parser.add_argument("--auto-delete", action="store_true",
                        help="Delete all transient data after processing (raw + index + results)")
    parser.add_argument("--verify-log", type=Path, default=None,
                        help="Verify hash chain of an existing audit log, then exit")
    args = parser.parse_args()

    # ── Verify mode (no pilot run) ─────────────────────────────────
    if args.verify_log:
        cmd_verify(args.verify_log)
        return

    # ── Pilot mode ─────────────────────────────────────────────────
    if not args.input_zip or not args.jd_file:
        parser.print_help()
        sys.exit(1)

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
    print("  \U0001f50d Verify:           python pilot_executor.py --verify-log {}".format(
        args.output_dir / "audit.chain.log"))
    print("{}".format("=" * 56))


if __name__ == "__main__":
    main()
