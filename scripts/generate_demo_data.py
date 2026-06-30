#!/usr/bin/env python3
"""
scripts/generate_demo_data.py — Generate synthetic demo data
============================================================

Wrapper around generate_synthetic_data.py that produces a ready-to-demo
dataset: 10,000 synthetic candidates + a hybrid FAISS + BM25 index.

Usage:
    python scripts/generate_demo_data.py
    python scripts/generate_demo_data.py --count 100000   # larger demo
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — generate demo data + index")
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--out", default="data/candidates.jsonl")
    ap.add_argument("--index-dir", default="output/")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini")
    args = ap.parse_args()

    # 1) Generate candidates
    print(f"[demo_data] generating {args.count:,} candidates → {args.out}")
    subprocess.run([
        sys.executable, str(REPO_ROOT / "generate_synthetic_data.py"),
        "--count", str(args.count), "--out", args.out,
    ], check=True, cwd=str(REPO_ROOT))

    # 2) Build the hybrid index
    print(f"\n[demo_data] building hybrid index → {args.index_dir}")
    subprocess.run([
        sys.executable, str(REPO_ROOT / "precompute.py"),
        "--candidates", args.out,
        "--output", args.index_dir,
        "--model", args.model, "--index", "flat", "--hybrid",
    ], check=True, cwd=str(REPO_ROOT))

    # 3) Smoke test
    print(f"\n[demo_data] smoke test: searching against the new index")
    subprocess.run([
        sys.executable, str(REPO_ROOT / "search.py"),
        "--jd", str(REPO_ROOT / "data" / "sample_jd.txt"),
        "--top", "5", "--hybrid", "--candidates", args.out,
    ], check=True, cwd=str(REPO_ROOT))

    print(f"\n[demo_data] DONE — index ready at {args.index_dir}")
    print(f"  Next: make dev  (starts the API server)")


if __name__ == "__main__":
    main()
