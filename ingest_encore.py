"""
ingest_encore.py — Encore Resume Ingestion Pipeline
==================================================

Takes a zipped folder of PDF/DOCX resumes exported from Encore (or any ATS)
and produces a clean candidates.jsonl ready for `precompute.py`.

Pipeline:
    1. Unzip the archive
    2. Walk the extracted tree, classify each file by extension
    3. Extract text via PyPDF2 (PDF) or python-docx (DOCX)
    4. Deduplicate via SHA-256 content hash + (email + name + phone) heuristic
    5. Extract structured metadata (name, email, phone, skills) where possible
    6. Write candidates.jsonl + failed_files.csv + duplicates.csv + ingest_report.json

Usage:
    python ingest_encore.py --input imports/encore/encore_export.zip \\
                            --output runs/proof_run_001/

Output files (in --output dir):
    candidates.jsonl     — one JSON candidate per line (for precompute.py)
    failed_files.csv     — filename, failure_reason
    duplicates.csv       — original_file, duplicate_of, dedup_method
    ingest_report.json   — summary stats (files received, parsed, failed, etc.)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Text extractors
# ---------------------------------------------------------------------------

def _extract_pdf(path: str) -> Tuple[str, float]:
    """Extract text from a PDF. Returns (text, confidence)."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        text_parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
        text = "\n".join(text_parts).strip()
        if not text:
            return "", 0.0  # Likely image-only PDF (needs OCR)
        confidence = min(1.0, len(text) / 500.0)  # rough heuristic
        return text, confidence
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def _extract_docx(path: str) -> Tuple[str, float]:
    """Extract text from a DOCX. Returns (text, confidence)."""
    try:
        import docx
        doc = docx.Document(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text).strip()
        if not text:
            return "", 0.0
        confidence = min(1.0, len(text) / 500.0)
        return text, confidence
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")


def _extract_txt(path: str) -> Tuple[str, float]:
    """Read a plain-text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        return text, 1.0 if text else 0.0
    except Exception as e:
        raise RuntimeError(f"TXT read failed: {e}")


def _extract_rtf(path: str) -> Tuple[str, float]:
    """Extract text from RTF (very crude — strips RTF control words)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        # Strip RTF control words
        text = re.sub(r"\\[a-z]+-?\d+ ?", " ", raw)
        text = re.sub(r"[{}\\]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text, 0.9 if text else 0.0
    except Exception as e:
        raise RuntimeError(f"RTF extraction failed: {e}")


def _extract_html(path: str) -> Tuple[str, float]:
    """Extract text from HTML (strip tags)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text, 0.95 if text else 0.0
    except Exception as e:
        raise RuntimeError(f"HTML extraction failed: {e}")


EXTRACTORS = {
    ".pdf":  _extract_pdf,
    ".docx": _extract_docx,
    ".doc":  _extract_docx,  # python-docx can read some legacy .doc
    ".txt":  _extract_txt,
    ".rtf":  _extract_rtf,
    ".html": _extract_html,
    ".htm":  _extract_html,
}


# ---------------------------------------------------------------------------
# Metadata extraction (heuristic)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3,4}[\s.-]?\d{4}")
# Skills gazetteer — same as jd_parser
_SKILL_GAZETTEER = [
    "python", "go", "rust", "java", "kotlin", "swift", "typescript", "javascript",
    "react", "react native", "next.js", "vue", "angular", "svelte", "tailwind css",
    "node.js", "express", "django", "flask", "fastapi", "spring", "rails",
    "pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "spark",
    "airflow", "dbt", "llms", "rag", "machine learning", "deep learning",
    "nlp", "computer vision", "mlops", "vector databases",
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "ansible",
    "linux", "nginx", "prometheus", "grafana", "elasticsearch", "kafka",
    "redis", "postgresql", "mysql", "mongodb", "cassandra", "clickhouse",
    "microservices", "distributed systems", "ci/cd", "gitops", "argocd",
]
_NAME_LINE_RE = re.compile(r"^([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,3})\s*$", re.MULTILINE)


def extract_metadata(text: str, filename: str) -> Dict:
    """Extract structured metadata from raw resume text."""
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    # Skills
    text_lower = text.lower()
    skills = []
    for s in _SKILL_GAZETTEER:
        if re.search(r"\b" + re.escape(s) + r"\b", text_lower):
            skills.append(s)
    # Name: try the first non-empty line, or filename
    name_match = _NAME_LINE_RE.search(text)
    name = name_match.group(1) if name_match else Path(filename).stem.replace("_", " ").replace("-", " ").title()
    # Email → likely name
    if emails and not name_match:
        local = emails[0].split("@")[0]
        if "." in local or "_" in local:
            name = re.sub(r"[._]", " ", local).title()
    return {
        "name": name[:120],
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "skills": skills[:20],
        "extraction_confidence": 0.0,  # filled in by caller
    }


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def dedup_key(meta: Dict) -> str:
    """Build a dedup key from email + name + phone (whichever are present)."""
    parts = []
    if meta.get("email"):
        parts.append(f"email:{meta['email'].lower()}")
    if meta.get("phone"):
        # Normalize: digits only
        phone_digits = re.sub(r"\D", "", meta["phone"])[-10:]
        if phone_digits:
            parts.append(f"phone:{phone_digits}")
    if meta.get("name"):
        parts.append(f"name:{meta['name'].lower().strip()}")
    return "|".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest(zip_path: str, output_dir: str, limit: Optional[int] = None) -> Dict:
    """Run the full ingestion pipeline. Returns a stats dict."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    stats = {
        "zip_path": zip_path,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_received": 0,
        "files_parsed": 0,
        "files_failed": 0,
        "duplicates_detected": 0,
        "throughput_per_sec": 0.0,
        "extraction_rate": 0.0,
        "failed_breakdown": {},
    }
    t0 = time.time()

    # 1) Open the zip
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Zip not found: {zip_path}")
    print(f"[ingest] opening {zip_path}", file=sys.stderr)

    candidates: List[Dict] = []
    failed: List[Dict] = []
    duplicates: List[Dict] = []
    seen_content_hashes: Dict[str, str] = {}  # hash → first-seen candidate_id
    seen_dedup_keys: Dict[str, str] = {}      # key → first-seen candidate_id

    with zipfile.ZipFile(zip_path, "r") as zf:
        member_paths = [m for m in zf.namelist() if not m.endswith("/")]
        stats["files_received"] = len(member_paths)
        print(f"[ingest] {len(member_paths)} files in archive", file=sys.stderr)

        for i, member in enumerate(member_paths):
            if limit and i >= limit:
                break
            ext = Path(member).suffix.lower()
            if ext not in EXTRACTORS:
                failed.append({"file": member, "reason": f"unsupported extension: {ext}"})
                stats["files_failed"] += 1
                stats["failed_breakdown"][f"unsupported_{ext or 'no_ext'}"] = stats["failed_breakdown"].get(f"unsupported_{ext or 'no_ext'}", 0) + 1
                continue

            # Read the file content from the zip
            try:
                with zf.open(member) as f:
                    content = f.read()
                # Write to a temp file so the extractor can open it by path
                tmp_path = f"/tmp/rp_ingest_{i}{ext}"
                with open(tmp_path, "wb") as tf:
                    tf.write(content)
            except Exception as e:
                failed.append({"file": member, "reason": f"read failed: {e}"})
                stats["files_failed"] += 1
                stats["failed_breakdown"]["read_failed"] = stats["failed_breakdown"].get("read_failed", 0) + 1
                continue

            # Extract text
            try:
                text, confidence = EXTRACTORS[ext](tmp_path)
                os.unlink(tmp_path)
                if not text or len(text) < 50:
                    raise RuntimeError("empty or too-short text")
            except Exception as e:
                reason = str(e)
                if "image-only" in reason.lower() or "empty" in reason.lower():
                    cat = "image_only_pdf" if ext == ".pdf" else "empty_text"
                else:
                    cat = "extraction_error"
                failed.append({"file": member, "reason": reason})
                stats["files_failed"] += 1
                stats["failed_breakdown"][cat] = stats["failed_breakdown"].get(cat, 0) + 1
                continue

            # Dedup: content hash first (catches re-uploads of same file)
            chash = content_hash(text)
            if chash in seen_content_hashes:
                duplicates.append({"file": member, "duplicate_of": seen_content_hashes[chash], "method": "content_hash"})
                stats["duplicates_detected"] += 1
                continue

            # Extract metadata
            meta = extract_metadata(text, member)
            meta["extraction_confidence"] = round(confidence, 2)

            # Enrich: extract structured fields (title, company, YoE, location, etc.)
            # from the raw resume text. This closes the gap between raw text
            # extraction and the structured fields the ranker needs.
            try:
                from resume_enricher import enrich_candidate
                enriched = enrich_candidate(text)
            except Exception as enrich_err:
                # If enrichment fails, fall back to empty fields (don't kill the ingest)
                enriched = {
                    "current_title": "", "current_company": "", "years_experience": None,
                    "location": "", "current_tenure_years": None, "title_progressed": False,
                    "previous_companies": [], "extraction_confidence": 0.0,
                }
                # Log but continue
                pass

            # Dedup: email + name + phone
            dkey = dedup_key(meta)
            if dkey and dkey in seen_dedup_keys:
                duplicates.append({"file": member, "duplicate_of": seen_dedup_keys[dkey], "method": "metadata_key"})
                stats["duplicates_detected"] += 1
                continue

            # Build the candidate record
            cid = f"cand-{stats['files_parsed']:08d}"
            candidate = {
                "id": cid,
                "name": meta["name"],
                "email": meta["email"],
                "phone": meta["phone"],
                "current_title": enriched["current_title"],
                "current_company": enriched["current_company"],
                "location": enriched["location"],
                "years_experience": enriched["years_experience"],
                "current_tenure_years": enriched["current_tenure_years"],
                "title_progressed": enriched["title_progressed"],
                "previous_companies": enriched["previous_companies"],
                "skills": meta["skills"],
                "summary": text[:2000],  # truncate to keep JSONL manageable
                "resume_text": text,
                "source_file": member,
                "source_hash": chash,
                "extraction_method": ext.lstrip("."),
                "extraction_confidence": max(meta["extraction_confidence"], enriched["extraction_confidence"]),
                "enrichment_confidence": enriched["extraction_confidence"],
                "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            candidates.append(candidate)
            seen_content_hashes[chash] = cid
            if dkey:
                seen_dedup_keys[dkey] = cid
            stats["files_parsed"] += 1

            if (stats["files_parsed"]) % 1000 == 0:
                elapsed = time.time() - t0
                rate = stats["files_parsed"] / elapsed if elapsed > 0 else 0
                print(f"[ingest] {stats['files_parsed']:,} parsed ({rate:.0f}/sec), "
                      f"{stats['files_failed']:,} failed, {stats['duplicates_detected']:,} dupes",
                      file=sys.stderr)

    # 2) Write candidates.jsonl
    jsonl_path = output / "candidates.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in candidates:
            # Don't write the full resume_text into the JSONL (keep file small)
            c_out = {k: v for k, v in c.items() if k != "resume_text"}
            f.write(json.dumps(c_out) + "\n")
    print(f"[ingest] wrote {len(candidates):,} candidates to {jsonl_path}", file=sys.stderr)

    # 3) Write failed_files.csv
    failed_path = output / "failed_files.csv"
    with open(failed_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "reason"])
        w.writeheader()
        for row in failed:
            w.writerow(row)
    print(f"[ingest] wrote {len(failed):,} failed files to {failed_path}", file=sys.stderr)

    # 4) Write duplicates.csv
    dupes_path = output / "duplicates.csv"
    with open(dupes_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "duplicate_of", "method"])
        w.writeheader()
        for row in duplicates:
            w.writerow(row)
    print(f"[ingest] wrote {len(duplicates):,} duplicates to {dupes_path}", file=sys.stderr)

    # 5) Finalize stats + write ingest_report.json
    elapsed = time.time() - t0
    stats["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    stats["elapsed_seconds"] = round(elapsed, 2)
    stats["throughput_per_sec"] = round(stats["files_parsed"] / elapsed, 1) if elapsed > 0 else 0.0
    stats["extraction_rate"] = round(stats["files_parsed"] / max(1, stats["files_parsed"] + stats["files_failed"]) * 100, 2)
    stats["output_dir"] = str(output)
    report_path = output / "ingest_report.json"
    with open(report_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"[ingest] report → {report_path}", file=sys.stderr)

    print(f"\n[ingest] DONE in {elapsed:.1f}s", file=sys.stderr)
    print(f"  Files received:     {stats['files_received']:,}", file=sys.stderr)
    print(f"  Files parsed:       {stats['files_parsed']:,} ({stats['extraction_rate']}%)", file=sys.stderr)
    print(f"  Files failed:       {stats['files_failed']:,}", file=sys.stderr)
    print(f"  Duplicates:         {stats['duplicates_detected']:,}", file=sys.stderr)
    print(f"  Throughput:         {stats['throughput_per_sec']} files/sec", file=sys.stderr)
    return stats


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — Encore resume ingestion pipeline")
    ap.add_argument("--input", required=True, help="Path to the zipped Encore export (.zip)")
    ap.add_argument("--output", default="runs/proof_run_001/", help="Output directory for candidates.jsonl + reports")
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N files (for testing)")
    args = ap.parse_args()
    stats = ingest(args.input, args.output, limit=args.limit)
    # Exit code: 0 if extraction rate ≥ 90%, else 1
    sys.exit(0 if stats["extraction_rate"] >= 90 else 1)


if __name__ == "__main__":
    main()
