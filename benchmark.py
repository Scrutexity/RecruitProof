"""
benchmark.py — RecruitProof Standalone Benchmark
================================================

Runs N searches against the pre-built index and reports p50/p75/p95/p99
latency. Compares against the hardware spec from PERFORMANCE.md.

Differs from `search.py --benchmark N`:
  - Standalone script (can be run from cron / CI)
  - Compares against documented targets
  - Outputs both JSON (machine) + human-readable report
  - Includes memory + CPU snapshot

Usage:
    python benchmark.py --jd data/sample_jd.txt --runs 50
    python benchmark.py --jd jd.txt --runs 100 --json benchmark.json
    python benchmark.py --jd-dir data/jds/ --runs 20  # benchmark across multiple JDs
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent))

from embedder import ResumeEmbedder
from faiss_index import FAISSIndex
from jd_parser import parse_jd
from ranker import MultiSignalRanker

try:
    from hybrid_retrieval import BM25Index, HybridRetriever
    _HAS_HYBRID = True
except ImportError:
    _HAS_HYBRID = False


# Performance targets from PERFORMANCE.md (500K candidates, m5.4xlarge)
TARGETS = {
    "faiss_ms_p50": 20,
    "faiss_ms_p99": 100,
    "rank_ms_p50": 100,
    "rank_ms_p99": 200,
    "total_ms_p50": 150,
    "total_ms_p99": 500,
}


def run_benchmark(jd_text: str, index_dir: str, candidates_path: Optional[str],
                  model_key: str, n_runs: int, hybrid: bool = True) -> Dict:
    """Run the benchmark and return a stats dict."""
    print(f"[bench] loading index from {index_dir}", file=sys.stderr)
    t0 = time.time()
    index = FAISSIndex.load(index_dir)
    bm25 = None
    if hybrid and _HAS_HYBRID and (Path(index_dir) / "bm25_corpus.json").exists():
        bm25 = BM25Index.load(index_dir)
    embedder = ResumeEmbedder(model_key=model_key)
    # Warm the model
    _ = embedder.encode_one("warmup", is_query=True)
    jd = parse_jd(jd_text)
    jd_vec = embedder.encode_one(jd_text, is_query=True)
    ranker = MultiSignalRanker(jd)

    # Load candidate lookup (only for the candidates we'll touch)
    # For benchmarking we use stubs to isolate the search+rank timing
    def stub_candidate(cid):
        return {"id": cid, "name": cid, "skills": [], "years_experience": 0,
                "current_title": "", "current_company": ""}

    print(f"[bench] index: {len(index.candidate_ids):,} candidates, "
          f"hybrid={bm25 is not None}, load+warm took {time.time()-t0:.1f}s", file=sys.stderr)
    print(f"[bench] running {n_runs} iterations", file=sys.stderr)

    fetch_k = 100  # standard top-100 retrieval

    timings = []
    for i in range(n_runs):
        # Dense retrieval
        t_faiss = time.time()
        if hybrid and bm25 is not None:
            retriever = HybridRetriever(index, bm25, embedder=embedder)
            fused, _ = retriever.search(jd_text, top_k=fetch_k)
            # Recover dense sims
            sims, idxs = index.search(jd_vec, top_k=fetch_k)
            sim_by_id = {index.candidate_ids[i]: float(s) for s, i in zip(sims, idxs) if i >= 0}
            fetched = [(cid, sim_by_id.get(cid, 0.0)) for cid, _, _ in fused]
        else:
            sims, idxs = index.search(jd_vec, top_k=fetch_k)
            fetched = [(index.candidate_ids[i], float(s)) for s, i in zip(sims, idxs) if i >= 0]
        t_faiss = (time.time() - t_faiss) * 1000

        # Re-rank
        t_rank = time.time()
        scored = []
        for cid, sim in fetched:
            cs = ranker.score(stub_candidate(cid), sim)
            scored.append(cs)
        scored.sort(key=lambda c: (-c.score_10, -c.semantic))
        t_rank = (time.time() - t_rank) * 1000

        timings.append({
            "run": i + 1, "faiss_ms": t_faiss, "rank_ms": t_rank,
            "total_ms": t_faiss + t_rank,
        })
        if (i + 1) % 10 == 0:
            print(f"  run {i+1}/{n_runs}: faiss={t_faiss:.1f}ms rank={t_rank:.1f}ms total={t_faiss+t_rank:.1f}ms",
                  file=sys.stderr)

    # Aggregate
    def stats(vals):
        s = sorted(vals)
        n = len(s)
        return {
            "min": round(min(vals), 2),
            "p50": round(s[n // 2], 2) if n else 0,
            "p75": round(s[int(n * 0.75)], 2) if n >= 4 else round(s[-1], 2) if s else 0,
            "p95": round(s[int(n * 0.95)], 2) if n >= 20 else round(s[-1], 2) if s else 0,
            "p99": round(s[int(n * 0.99)], 2) if n >= 100 else round(s[-1], 2) if s else 0,
            "max": round(max(vals), 2),
            "mean": round(statistics.mean(vals), 2),
        }

    faiss_ms = [t["faiss_ms"] for t in timings]
    rank_ms = [t["rank_ms"] for t in timings]
    total_ms = [t["total_ms"] for t in timings]

    # Memory snapshot
    mem_mb = 0
    try:
        import resource
        mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB → MB on Linux
    except Exception:
        pass

    report = {
        "n_runs": n_runs,
        "index_size": len(index.candidate_ids),
        "hybrid": hybrid and bm25 is not None,
        "model": model_key,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "faiss_ms": stats(faiss_ms),
        "rank_ms": stats(rank_ms),
        "total_ms": stats(total_ms),
        "memory_mb": round(mem_mb, 1),
        "targets": TARGETS,
        "passes_targets": {
            "faiss_ms_p50": stats(faiss_ms)["p50"] <= TARGETS["faiss_ms_p50"],
            "faiss_ms_p99": stats(faiss_ms)["p99"] <= TARGETS["faiss_ms_p99"],
            "rank_ms_p50": stats(rank_ms)["p50"] <= TARGETS["rank_ms_p50"],
            "rank_ms_p99": stats(rank_ms)["p99"] <= TARGETS["rank_ms_p99"],
            "total_ms_p50": stats(total_ms)["p50"] <= TARGETS["total_ms_p50"],
            "total_ms_p99": stats(total_ms)["p99"] <= TARGETS["total_ms_p99"],
        },
        "raw": timings,
    }
    return report


def print_report(report: Dict):
    """Human-readable report."""
    print()
    print("=" * 78)
    print(f"  RecruitProof Benchmark — {report['n_runs']} runs, "
          f"{report['index_size']:,} candidates, hybrid={report['hybrid']}")
    print("=" * 78)
    print()
    print(f"  {'Stage':<14}{'min':>10}{'p50':>10}{'p95':>10}{'p99':>10}{'max':>10}{'mean':>10}")
    print("  " + "─" * 64)
    for stage_key, stage_lbl in [("faiss_ms", "FAISS search"), ("rank_ms", "Re-rank"), ("total_ms", "Total")]:
        s = report[stage_key]
        target_p50 = report["targets"].get(f"{stage_key}_p50")
        target_p99 = report["targets"].get(f"{stage_key}_p99")
        p50_marker = " ✓" if target_p50 and s["p50"] <= target_p50 else " ✗"
        print(f"  {stage_lbl:<14}{s['min']:>10.1f}{s['p50']:>10.1f}{s['p95']:>10.1f}"
              f"{s['p99']:>10.1f}{s['max']:>10.1f}{s['mean']:>10.1f}{p50_marker}")
    print()
    print(f"  Memory: {report['memory_mb']} MB")
    print()
    all_pass = all(report["passes_targets"].values())
    verdict = "✓ ALL TARGETS MET" if all_pass else "✗ SOME TARGETS MISSED"
    print(f"  Verdict: {verdict}")
    print()


def main():
    ap = argparse.ArgumentParser(description="RecruitProof — standalone benchmark")
    ap.add_argument("--jd", help="JD text or path to a .txt file")
    ap.add_argument("--jd-dir", help="Directory of JD .txt files to benchmark (run on each)")
    ap.add_argument("--index", default="output", help="Index directory (default: output/)")
    ap.add_argument("--candidates", default=None, help="candidates.jsonl/.csv (optional)")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini")
    ap.add_argument("--runs", type=int, default=20, help="Iterations per JD (default: 20)")
    ap.add_argument("--hybrid", action="store_true", default=True)
    ap.add_argument("--no-hybrid", dest="hybrid", action="store_false")
    ap.add_argument("--json", default=None, help="Write JSON report to this path")
    args = ap.parse_args()

    if args.jd_dir:
        # Benchmark across multiple JDs
        jd_dir = Path(args.jd_dir)
        jd_files = sorted(jd_dir.glob("*.txt"))
        if not jd_files:
            print(f"[bench] no .txt files in {args.jd_dir}", file=sys.stderr)
            sys.exit(2)
        all_reports = []
        for jd_file in jd_files:
            print(f"\n[bench] === {jd_file.name} ===", file=sys.stderr)
            with open(jd_file) as f:
                jd_text = f.read()
            r = run_benchmark(jd_text, args.index, args.candidates, args.model, args.runs, args.hybrid)
            r["jd_file"] = jd_file.name
            all_reports.append(r)
            print_report(r)
        if args.json:
            with open(args.json, "w") as f:
                json.dump({"reports": all_reports}, f, indent=2)
            print(f"[bench] JSON written to {args.json}", file=sys.stderr)
    else:
        if not args.jd:
            ap.error("--jd or --jd-dir required")
        if os.path.exists(args.jd):
            with open(args.jd) as f:
                jd_text = f.read()
        else:
            jd_text = args.jd
        report = run_benchmark(jd_text, args.index, args.candidates, args.model, args.runs, args.hybrid)
        print_report(report)
        if args.json:
            with open(args.json, "w") as f:
                json.dump(report, f, indent=2)
            print(f"[bench] JSON written to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
