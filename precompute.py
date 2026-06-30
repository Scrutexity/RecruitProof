"""
precompute.py — Pre-computation Pipeline
=======================================

Reads a JSONL (or CSV) file of candidates, generates embeddings in batches,
and builds a FAISS index. This is the one-time cost — after this runs, every
search.py invocation is sub-5ms.

Usage:
    python precompute.py \\
        --candidates data/candidates.jsonl \\
        --output output/ \\
        --model mini \\
        --index ivf

Output files (in --output dir):
    candidates.faiss     — the FAISS index
    candidate_ids.json   — row index → candidate_id side table
    index_meta.json      — dim, index_type, count, etc.

Benchmark expectations (CPU, 4 cores, MiniLM-L6-v2):
    10K candidates  → ~30 seconds
    100K candidates → ~5 minutes
    1M candidates   → ~30-50 minutes (BGE) / ~15-20 min (MiniLM)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from typing import Iterator, List

import numpy as np
from tqdm import tqdm

from embedder import ResumeEmbedder, build_resume_text
from faiss_index import FAISSIndex

# Optional: hybrid retrieval needs BM25. Import lazily so precompute still
# works for pure-dense use cases if rank-bm25 is not installed.
try:
    from hybrid_retrieval import BM25Index
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False


def _load_all_candidates(path: str, limit: Optional[int] = None) -> List[dict]:
    """Materialize ALL candidates in memory (needed for BM25 corpus build).

    At 1M candidates this is ~2-3GB RAM. Acceptable on a 16GB+ machine; for
    tight memory, switch to streaming BM25 (e.g. build corpus in chunks).
    """
    fmt = detect_format(path)
    it = iter_csv(path) if fmt == "csv" else iter_jsonl(path)
    out: List[dict] = []
    for i, cand in enumerate(it):
        if limit is not None and i >= limit:
            break
        cand.setdefault("id", f"auto-{i:08d}")
        out.append(cand)
    return out


# ----------------------------------------------------------------- data load

def iter_jsonl(path: str) -> Iterator[dict]:
    """Stream JSONL — one JSON candidate per line. Memory-friendly for 1M."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[warn] skipping malformed line: {e}", file=sys.stderr)


def iter_csv(path: str) -> Iterator[dict]:
    """Stream CSV — assumes 'skills' and 'previous_companies' are pipe-separated."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # parse pipe-separated list fields
            for k in ("skills", "previous_companies", "certifications"):
                if k in row and isinstance(row[k], str) and row[k]:
                    row[k] = [s.strip() for s in row[k].split("|") if s.strip()]
            # coerce numerics
            for k in ("years_experience", "last_active_days_ago", "response_rate",
                       "promotions_last_5y", "current_tenure_years"):
                if k in row and row[k]:
                    try:
                        row[k] = float(row[k]) if "." in str(row[k]) else int(row[k])
                    except ValueError:
                        row[k] = None
            for k in ("open_to_remote", "previously_applied", "referral", "title_progressed"):
                if k in row and isinstance(row[k], str):
                    row[k] = row[k].strip().lower() in ("1", "true", "yes", "y")
            yield row


def detect_format(path: str) -> str:
    if path.endswith(".csv"):
        return "csv"
    return "jsonl"


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="RecruitProof — build FAISS (+ optional BM25) index from candidate JSONL/CSV")
    ap.add_argument("--candidates", required=True, help="Path to candidates.jsonl or .csv")
    ap.add_argument("--output", default="output", help="Output dir for the FAISS index")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini",
                    help="Embedding model: bge (768-d, accurate) or mini (384-d, fast). Default: mini")
    ap.add_argument("--index", choices=["flat", "ivf"], default="flat",
                    help="FAISS index type: flat (exact, ≤2M) or ivf (approx, 10M+). Default: flat")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--limit", type=int, default=None,
                    help="Only embed the first N candidates (for testing)")
    ap.add_argument("--hybrid", action="store_true",
                    help="Also build a BM25 sparse index alongside FAISS for hybrid retrieval.")
    args = ap.parse_args()

    if args.hybrid and not _HAS_BM25:
        print("[precompute] --hybrid requires rank-bm25. Run: pip install rank-bm25",
              file=sys.stderr)
        sys.exit(2)

    fmt = detect_format(args.candidates)
    print(f"[precompute] reading candidates from {args.candidates} ({fmt})")
    t0 = time.time()

    # ---- Load all candidates into memory. We need the full dicts anyway
    # for the BM25 corpus build (when --hybrid is set), and materializing
    # the text list is cheap at 1M scale.
    print("[precompute] loading candidates into memory...")
    t_load = time.time()
    candidates_all = _load_all_candidates(args.candidates, limit=args.limit)
    N = len(candidates_all)
    print(f"[precompute] {N:,} candidates loaded in {time.time()-t_load:.1f}s")

    if N == 0:
        print("[precompute] ERROR: no candidates found", file=sys.stderr)
        sys.exit(1)

    candidate_ids = [c["id"] for c in candidates_all]
    texts = [build_resume_text(c) for c in candidates_all]

    # ---- Embedding pass
    print(f"[precompute] loading model: {args.model}")
    emb = ResumeEmbedder(model_key=args.model)
    print(f"[precompute] encoding {N:,} resumes → {emb.dim}-d vectors "
          f"(batch={args.batch_size})...")
    t1 = time.time()
    vectors = emb.encode_batch(texts, batch_size=args.batch_size, show_progress=True)
    print(f"[precompute] embeddings done in {time.time()-t1:.1f}s "
          f"({N/(time.time()-t1):,.0f} candidates/sec)")

    # ---- Index build
    print(f"[precompute] building FAISS index ({args.index})...")
    t2 = time.time()
    if args.index == "flat":
        index = FAISSIndex.build_flat(vectors, candidate_ids)
    else:
        index = FAISSIndex.build_ivf(vectors, candidate_ids)
    print(f"[precompute] index built in {time.time()-t2:.1f}s "
          f"({index.index_type}, nlist={index.nlist})")

    # ---- (Optional) BM25 sparse index for hybrid retrieval
    if args.hybrid:
        print("[precompute] building BM25 sparse index...")
        t_bm25 = time.time()
        bm25 = BM25Index.build(candidates_all)
        bm25.save(args.output)
        print(f"[precompute] BM25 index built in {time.time()-t_bm25:.1f}s "
              f"(avg doc len={bm25.avg_doc_len:.1f} tokens)")

    # ---- Persist
    print(f"[precompute] saving to {args.output}/")
    index.save(args.output)
    print(f"[precompute] DONE. Total time: {time.time()-t0:.1f}s")
    hybrid_hint = " --hybrid" if args.hybrid else ""
    print(f"[precompute] Search is now ready: "
          f"python search.py --jd <file> --index {args.output} --top 100{hybrid_hint}")


if __name__ == "__main__":
    main()
