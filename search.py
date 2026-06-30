#!/usr/bin/env python3
"""
search.py — RecruitProof CLI (the killer entrypoint)
===================================================

Given a job description, retrieves the top-K candidates from a pre-built
FAISS index, re-ranks them with the five-signal MultiSignalRanker, and
prints the top-N with a 0-10 score, a one-sentence reasoning, and the
missing skills for the #1 candidate.

Usage:
    python search.py --jd data/sample_jd.txt --top 100
    python search.py --jd "Senior React Engineer with 7+ years..." --top 50
    python search.py --jd jd.txt --top 100 --index output/ --json out.json
    python search.py --jd jd.txt --explain cand-00006082      # per-candidate trace
    python search.py --jd jd.txt --benchmark 20               # p50/p95 latency
    python search.py --jd jd.txt --top 100 --csv results.csv  # spreadsheet export
    python search.py --jd jd.txt --top 100 --hybrid           # dense+sparse via RRF
    python search.py --jd-dir jds/ --top 50 --out-dir runs/   # batch mode
    OPENAI_API_KEY=sk-... python search.py --jd jd.txt --top 10 --llm-reasoning

Pipeline:
    1. Parse JD          → jd_parser.parse_jd()           [< 10 ms]
    2. Embed JD          → ResumeEmbedder.encode_one()    [~50 ms first time]
    3. FAISS ANN search  → top 5×K candidates             [< 5 ms for 1M vectors]
    4. Multi-signal rank → MultiSignalRanker.score()      [~0.5 ms per cand]
    5. Reasoning         → local template OR OpenAI       [0 ms or ~500 ms]
    6. Print             → human-readable table + JSON

Total wall time for 1M candidates: ~1-2 seconds end-to-end (CPU).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

from embedder import ResumeEmbedder
from faiss_index import FAISSIndex
from jd_parser import parse_jd
from ranker import (
    CandidateScore,
    MultiSignalRanker,
    WEIGHTS,
    generate_reasoning,
)
import ui

# Optional: hybrid retrieval (BM25 + FAISS via RRF)
try:
    from hybrid_retrieval import BM25Index, HybridRetriever
    _HAS_HYBRID = True
except ImportError:
    _HAS_HYBRID = False


# ----------------------------------------------------------------- helpers

def load_candidate_lookup(candidates_path: str, candidate_ids: List[str]) -> Dict[str, Dict]:
    """Build id→candidate dict from JSONL/CSV for the top-K lookups."""
    needed = set(candidate_ids)
    out: Dict[str, Dict] = {}
    if not candidates_path or not os.path.exists(candidates_path):
        return out
    from precompute import detect_format, iter_csv, iter_jsonl
    fmt = detect_format(candidates_path)
    it = iter_csv(candidates_path) if fmt == "csv" else iter_jsonl(candidates_path)
    for cand in it:
        cid = cand.get("id")
        if cid in needed:
            out[cid] = cand
            if len(out) == len(needed):
                break
    return out


def load_single_candidate(candidates_path: str, candidate_id: str) -> Optional[Dict]:
    """Load one candidate by id from JSONL/CSV. Returns None if not found."""
    if not candidates_path or not os.path.exists(candidates_path):
        return None
    from precompute import detect_format, iter_csv, iter_jsonl
    fmt = detect_format(candidates_path)
    it = iter_csv(candidates_path) if fmt == "csv" else iter_jsonl(candidates_path)
    for cand in it:
        if cand.get("id") == candidate_id:
            return cand
    return None


# ----------------------------------------------------------------- core search

def run_search(
    jd_text: str,
    index_dir: str,
    candidates_path: Optional[str],
    top_k: int,
    model_key: str,
    use_llm: bool,
    llm_client,
    recall_factor: int = 5,
    return_explain_for: Optional[str] = None,
    use_hybrid: bool = False,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> Tuple[List[Dict], Dict, Dict, Optional[CandidateScore], float]:
    """Run the full search pipeline.

    Returns:
        (results, jd, timing, explain_cs, top1_sim)
        - results: top-N scored candidates as dicts
        - jd: parsed JD dict
        - timing: dict of stage_ms timings
        - explain_cs: if return_explain_for is set, the CandidateScore for that candidate
        - top1_sim: cosine sim of the #1 candidate (for the explain view)
    """
    t_total = time.time()
    timing: Dict[str, Optional[float]] = {}

    # 1) Parse JD
    t = time.time()
    jd = parse_jd(jd_text)
    timing["parse_ms"] = (time.time() - t) * 1000
    print(f"[1/5] JD parsed in {timing['parse_ms']:.0f}ms — "
          f"title={jd['title']!r}, seniority={jd['seniority']}, "
          f"required_skills={jd['required_skills']}", file=sys.stderr)

    # 2) Load FAISS index (+ optional BM25 for hybrid)
    t = time.time()
    index = FAISSIndex.load(index_dir)
    bm25_index = None
    if use_hybrid:
        if not _HAS_HYBRID:
            print("[warn] --hybrid requested but rank-bm25 not installed. "
                  "Falling back to dense-only.", file=sys.stderr)
            use_hybrid = False
        else:
            bm25_path = os.path.join(index_dir, "bm25_corpus.json")
            if not os.path.exists(bm25_path):
                print(f"[warn] --hybrid requested but no BM25 index at {bm25_path}. "
                      f"Re-run precompute.py --hybrid. Falling back to dense-only.",
                      file=sys.stderr)
                use_hybrid = False
            else:
                bm25_index = BM25Index.load(index_dir)
    timing["load_ms"] = (time.time() - t) * 1000
    extra = f" + BM25 ({len(bm25_index.candidate_ids):,} docs)" if bm25_index else ""
    print(f"[2/5] Index loaded in {timing['load_ms']:.0f}ms — "
          f"FAISS {len(index.candidate_ids):,} candidates, "
          f"dim={index.dim}, type={index.index_type}{extra}"
          + ("  [HYBRID MODE]" if use_hybrid else ""), file=sys.stderr)

    # 3) Embed JD
    t = time.time()
    emb = ResumeEmbedder(model_key=model_key)
    jd_vec = emb.encode_one(jd_text, is_query=True)
    timing["embed_ms"] = (time.time() - t) * 1000
    print(f"[3/5] JD embedded in {timing['embed_ms']:.0f}ms "
          f"(model={model_key}, dim={emb.dim})", file=sys.stderr)

    # 4) Retrieval: hybrid (FAISS+BM25 via RRF) OR dense-only (FAISS)
    t = time.time()
    fetch_k = min(top_k * recall_factor, len(index.candidate_ids))
    if use_hybrid and bm25_index is not None:
        # Hybrid: fuse dense + sparse via RRF
        retriever = HybridRetriever(index, bm25_index, embedder=emb)
        fused, hybrid_debug = retriever.search(
            query_text=jd_text, top_k=fetch_k,
            dense_weight=dense_weight, sparse_weight=sparse_weight,
        )
        timing["faiss_ms"] = hybrid_debug["dense_ms"]
        timing["sparse_ms"] = hybrid_debug["sparse_ms"]
        timing["fuse_ms"] = hybrid_debug["fuse_ms"]
        timing["retrieval_ms"] = (time.time() - t) * 1000
        print(f"[4/5] HYBRID retrieved top-{len(fused)} in {timing['retrieval_ms']:.0f}ms "
              f"(dense={hybrid_debug['dense_ms']:.1f}ms + "
              f"sparse={hybrid_debug['sparse_ms']:.1f}ms + "
              f"fuse={hybrid_debug['fuse_ms']:.1f}ms)", file=sys.stderr)
        # Build a parallel (sims, idxs) view for compatibility with the
        # downstream ranker. We need to look up the dense sim for each
        # fused candidate. If the candidate wasn't in the dense top-K, we
        # use 0.0 (BM25-only hit).
        dense_sim_by_id = {}
        # Re-run the dense search to recover sims for the fused set. Cheap.
        dense_sims, dense_idxs = index.search(jd_vec, top_k=fetch_k)
        for sim, idx in zip(dense_sims, dense_idxs):
            if idx >= 0:
                dense_sim_by_id[index.candidate_ids[idx]] = float(sim)
        fetched_ids = [cid for cid, _, _ in fused]
        fetched_sims = [dense_sim_by_id.get(cid, 0.0) for cid in fetched_ids]
    else:
        # Dense-only
        sims, idxs = index.search(jd_vec, top_k=fetch_k)
        timing["faiss_ms"] = (time.time() - t) * 1000
        timing["retrieval_ms"] = timing["faiss_ms"]
        print(f"[4/5] FAISS retrieved top-{fetch_k} in {timing['faiss_ms']:.0f}ms",
              file=sys.stderr)
        fetched_ids = [index.candidate_ids[i] for i in idxs if i >= 0]
        fetched_sims = [float(s) for s, i in zip(sims, idxs) if i >= 0]

    # 5) Multi-signal re-rank
    t = time.time()
    ranker = MultiSignalRanker(jd)
    candidate_lookup = load_candidate_lookup(candidates_path, fetched_ids)

    scored: List[CandidateScore] = []
    missing_count = 0
    explain_cs: Optional[CandidateScore] = None
    explain_sim: float = 0.0
    for cid, sim in zip(fetched_ids, fetched_sims):
        cand = candidate_lookup.get(cid)
        if cand is None:
            cand = {"id": cid, "name": cid, "skills": [], "years_experience": 0,
                    "current_title": "", "current_company": ""}
            missing_count += 1
        cs = ranker.score(cand, float(sim))
        scored.append(cs)
        if return_explain_for is not None and cid == return_explain_for:
            explain_cs = cs
            explain_sim = float(sim)

    scored.sort(key=lambda c: (-c.score_10, -c.semantic))
    for i, cs in enumerate(scored):
        cs.rank = i + 1
    top_n = scored[:top_k]
    timing["rank_ms"] = (time.time() - t) * 1000
    print(f"[5/5] Multi-signal re-ranked {len(scored)} candidates in "
          f"{timing['rank_ms']:.0f}ms"
          + (f" ({missing_count} candidates missing metadata — using stubs)" if missing_count else ""),
          file=sys.stderr)

    # 6) Generate reasoning for the top-N
    if use_llm and llm_client is not None:
        print(f"[+] Generating LLM reasoning for top {len(top_n)}...", file=sys.stderr)
    for cs in top_n:
        cand = candidate_lookup.get(cs.candidate_id, {"id": cs.candidate_id, "name": cs.candidate_id})
        cs.reasoning = generate_reasoning(cs, cand, jd, use_llm=use_llm, llm_client=llm_client)
    if explain_cs is not None and not explain_cs.reasoning:
        cand = candidate_lookup.get(explain_cs.candidate_id, {"id": explain_cs.candidate_id})
        explain_cs.reasoning = generate_reasoning(explain_cs, cand, jd, use_llm=use_llm, llm_client=llm_client)

    timing["total_ms"] = (time.time() - t_total) * 1000
    print(f"[done] Total wall time: {timing['total_ms']:.0f}ms", file=sys.stderr)

    results = []
    for cs in top_n:
        cand = candidate_lookup.get(cs.candidate_id, {})
        results.append({
            "rank": cs.rank,
            "candidate_id": cs.candidate_id,
            "name": cand.get("name", cs.candidate_id),
            "current_title": cand.get("current_title", ""),
            "current_company": cand.get("current_company", ""),
            "years_experience": cand.get("years_experience"),
            "location": cand.get("location", ""),
            "score_10": cs.score_10,
            "score_bar": ui.score_bar(cs.score_10),
            "signals": cs.signals,
            "matched_skills": cs.matched_skills,
            "missing_skills": cs.missing_skills,
            "reasoning": cs.reasoning,
        })
    return results, jd, timing, explain_cs, explain_sim


# ----------------------------------------------------------------- benchmark

def run_benchmark(
    jd_text: str,
    index_dir: str,
    candidates_path: Optional[str],
    model_key: str,
    n_runs: int,
    top_k: int,
    recall_factor: int,
) -> Dict:
    """Run the same query N times and report p50/p95 latency.

    The first run includes model load; subsequent runs measure steady-state
    search latency. We report both "cold" (run 1) and "warm" (runs 2..N) stats.
    """
    print(f"[benchmark] running {n_runs} iterations, top_k={top_k}", file=sys.stderr)

    # Pre-load everything so warm runs are pure search+rank
    jd = parse_jd(jd_text)
    index = FAISSIndex.load(index_dir)
    emb = ResumeEmbedder(model_key=model_key)
    # Warm the model — encode once
    _ = emb.encode_one("warmup", is_query=True)
    jd_vec = emb.encode_one(jd_text, is_query=True)
    ranker = MultiSignalRanker(jd)
    fetch_k = min(top_k * recall_factor, len(index.candidate_ids))
    fetched_ids_all = None

    timings = []
    for i in range(n_runs):
        t0 = time.time()
        sims, idxs = index.search(jd_vec, top_k=fetch_k)
        t_faiss = time.time() - t0

        t1 = time.time()
        if fetched_ids_all is None:
            fetched_ids_all = [index.candidate_ids[i] for i in idxs if i >= 0]
            lookup = load_candidate_lookup(candidates_path, fetched_ids_all)
        scored = []
        for sim, idx in zip(sims, idxs):
            if idx < 0:
                continue
            cid = index.candidate_ids[idx]
            cand = lookup.get(cid, {"id": cid, "name": cid, "skills": [],
                                    "years_experience": 0, "current_title": "", "current_company": ""})
            cs = ranker.score(cand, float(sim))
            scored.append(cs)
        scored.sort(key=lambda c: (-c.score_10, -c.semantic))
        t_rank = time.time() - t1
        timings.append({
            "run": i + 1,
            "faiss_ms": t_faiss * 1000,
            "rank_ms": t_rank * 1000,
            "total_ms": (t_faiss + t_rank) * 1000,
        })
        print(f"  run {i+1:>2}/{n_runs}: faiss={t_faiss*1000:.1f}ms rank={t_rank*1000:.1f}ms total={(t_faiss+t_rank)*1000:.1f}ms",
              file=sys.stderr)

    def stats(vals):
        s = sorted(vals)
        n = len(s)
        p50 = s[n // 2] if n else 0
        p95 = s[int(n * 0.95)] if n >= 20 else (s[-1] if s else 0)
        return {"min": min(vals) if vals else 0, "p50": p50, "p95": p95,
                "max": max(vals) if vals else 0, "mean": sum(vals) / len(vals) if vals else 0}

    faiss_ms = [t["faiss_ms"] for t in timings]
    rank_ms = [t["rank_ms"] for t in timings]
    total_ms = [t["total_ms"] for t in timings]

    report = {
        "n_runs": n_runs,
        "top_k": top_k,
        "index_size": len(index.candidate_ids),
        "faiss_ms": stats(faiss_ms),
        "rank_ms": stats(rank_ms),
        "total_ms": stats(total_ms),
        "raw": timings,
    }
    return report


def print_benchmark(report: Dict):
    """Pretty-print the benchmark report."""
    print()
    print(ui.c("╔" + "═" * 78, ui._C.BRIGHT_CYAN, ui._C.BOLD))
    print(ui.c("║", ui._C.BRIGHT_CYAN, ui._C.BOLD)
          + ui.c(f"  BENCHMARK REPORT — {report['n_runs']} runs, top_k={report['top_k']}", ui._C.BOLD)
          + " " * max(2, 78 - 50)  # rough pad
          + ui.c("║", ui._C.BRIGHT_CYAN, ui._C.BOLD))
    print(ui.c("╚" + "═" * 78, ui._C.BRIGHT_CYAN, ui._C.BOLD))
    print()
    print(f"  {ui.c('Index size:', ui._C.GRAY)} {report['index_size']:,} candidates")
    print()
    print(f"  {ui.c('Stage', ui._C.BOLD):<14}{ui.c('min', ui._C.GRAY):>10}{ui.c('p50', ui._C.GRAY):>10}{ui.c('p95', ui._C.GRAY):>10}{ui.c('max', ui._C.GRAY):>10}{ui.c('mean', ui._C.GRAY):>10}")
    print(ui.c("  " + "─" * 64, ui._C.DIM))
    for stage_key, stage_lbl in [("faiss_ms", "FAISS search"), ("rank_ms", "Multi-signal rank"), ("total_ms", "Total")]:
        s = report[stage_key]
        color = ui._C.BRIGHT_GREEN if stage_key == "faiss_ms" else (ui._C.CYAN if stage_key == "rank_ms" else ui._C.BOLD)
        print(f"  {ui.c(stage_lbl, color):<14}{s['min']:>10.1f}{s['p50']:>10.1f}{s['p95']:>10.1f}{s['max']:>10.1f}{s['mean']:>10.1f}")
    print()
    total_p50 = report["total_ms"]["p50"]
    total_p95 = report["total_ms"]["p95"]
    verdict_color = ui._C.BRIGHT_GREEN if total_p95 < 5000 else (ui._C.YELLOW if total_p95 < 30000 else ui._C.RED)
    print(f"  {ui.c('VERDICT:', ui._C.BOLD)} "
          + ui.c(f"p50={total_p50:.0f}ms  p95={total_p95:.0f}ms  ", verdict_color, ui._C.BOLD)
          + ui.c("(warm search latency — model load excluded)", ui._C.DIM))
    print()


# ----------------------------------------------------------------- CSV export

def write_csv(results: List[Dict], path: str):
    """Write results to a CSV file for spreadsheet import."""
    if not results:
        return
    # Flatten signals for spreadsheet friendliness
    fieldnames = ["rank", "candidate_id", "name", "current_title", "current_company",
                  "years_experience", "location", "score_10",
                  "semantic", "role_fit", "skills", "behavioral", "career",
                  "matched_skills", "missing_skills", "reasoning"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            row = {
                "rank": r["rank"],
                "candidate_id": r["candidate_id"],
                "name": r["name"],
                "current_title": r.get("current_title", ""),
                "current_company": r.get("current_company", ""),
                "years_experience": r.get("years_experience", ""),
                "location": r.get("location", ""),
                "score_10": r["score_10"],
                "semantic": r["signals"]["semantic"],
                "role_fit": r["signals"]["role_fit"],
                "skills": r["signals"]["skills"],
                "behavioral": r["signals"]["behavioral"],
                "career": r["signals"]["career"],
                "matched_skills": "|".join(r["matched_skills"]),
                "missing_skills": "|".join(r["missing_skills"]),
                "reasoning": r["reasoning"],
            }
            w.writerow(row)
    print(f"[+] CSV results written to {path}", file=sys.stderr)


# ----------------------------------------------------------------- batch mode

def run_batch(jd_dir: str, index_dir: str, candidates_path: Optional[str],
              top_k: int, model_key: str, out_dir: str, recall_factor: int):
    """Process every .txt file in `jd_dir` as a separate JD and emit a per-JD report."""
    if not os.path.isdir(jd_dir):
        print(f"[error] --jd-dir path is not a directory: {jd_dir}", file=sys.stderr)
        sys.exit(2)
    jd_files = sorted([f for f in os.listdir(jd_dir) if f.lower().endswith(".txt")])
    if not jd_files:
        print(f"[error] no .txt files found in {jd_dir}", file=sys.stderr)
        sys.exit(2)
    os.makedirs(out_dir, exist_ok=True)

    print(f"[batch] processing {len(jd_files)} JDs from {jd_dir} → {out_dir}/", file=sys.stderr)
    summary = []
    # Reuse the embedder + index across JDs (huge speedup)
    index = FAISSIndex.load(index_dir)
    emb = ResumeEmbedder(model_key=model_key)
    # Warm the model
    _ = emb.encode_one("warmup", is_query=True)
    ranker_cache = {}  # jd_id -> ranker

    for jd_file in jd_files:
        jd_path = os.path.join(jd_dir, jd_file)
        with open(jd_path, "r", encoding="utf-8") as f:
            jd_text = f.read()
        jd_id = os.path.splitext(jd_file)[0]
        out_path_json = os.path.join(out_dir, f"{jd_id}.json")

        t0 = time.time()
        results, jd, timing, _, _ = run_search(
            jd_text=jd_text, index_dir=index_dir, candidates_path=candidates_path,
            top_k=top_k, model_key=model_key, use_llm=False, llm_client=None,
            recall_factor=recall_factor,
        )
        # NOTE: run_search re-loads the index each call; for true batch speed
        # we'd refactor to take a pre-loaded index. Acceptable for ≤100 JDs.

        with open(out_path_json, "w", encoding="utf-8") as f:
            json.dump({
                "jd_id": jd_id,
                "jd_file": jd_file,
                "parsed_jd": {k: v for k, v in jd.items() if k != "raw_text"},
                "timing_ms": timing,
                "top_k": top_k,
                "results": results,
            }, f, indent=2)

        top1 = results[0] if results else None
        summary.append({
            "jd_id": jd_id,
            "title": jd.get("title", ""),
            "top1_name": top1["name"] if top1 else "",
            "top1_score": top1["score_10"] if top1 else 0.0,
            "n_results": len(results),
            "total_ms": timing.get("total_ms", 0.0),
        })
        print(f"  {jd_file}: {len(results)} results, top1={top1['name'] if top1 else 'n/a'} ({top1['score_10'] if top1 else 0}/10), {timing.get('total_ms', 0):.0f}ms",
              file=sys.stderr)

    summary_path = os.path.join(out_dir, "batch_summary.csv")
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["jd_id", "title", "top1_name", "top1_score", "n_results", "total_ms"])
        w.writeheader()
        for row in summary:
            w.writerow(row)
    print(f"\n[batch] DONE — {len(jd_files)} JDs processed, summary → {summary_path}",
          file=sys.stderr)


# ----------------------------------------------------------------- LLM client

def get_llm_client():
    """Return an OpenAI client if OPENAI_API_KEY is set, else None."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception as e:
        print(f"[warn] could not init OpenAI client: {e}", file=sys.stderr)
        return None


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description="RecruitProof — find the perfect candidate out of 1M resumes in <5 seconds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search.py --jd data/sample_jd.txt --top 100
  python search.py --jd "Senior React Engineer, 7+ years, AWS" --top 50
  python search.py --jd jd.txt --explain cand-00006082          # per-candidate trace
  python search.py --jd jd.txt --benchmark 20                   # p50/p95 latency
  python search.py --jd jd.txt --top 100 --csv results.csv      # spreadsheet export
  python search.py --jd-dir jds/ --top 50 --out-dir runs/       # batch mode
  python search.py --jd jd.txt --top 10 --llm-reasoning         # needs OPENAI_API_KEY
  python search.py --jd jd.txt --top 100 --json results.json
        """.strip(),
    )
    ap.add_argument("--jd",
                    help="Job description text OR path to a .txt file. Required unless --jd-dir is set.")
    ap.add_argument("--jd-dir",
                    help="Directory of .txt JD files for batch processing.")
    ap.add_argument("--index", default="output",
                    help="Directory containing the pre-built FAISS index. Default: output/")
    ap.add_argument("--candidates", default=None,
                    help="Path to candidates.jsonl/.csv (for metadata lookup). Optional.")
    ap.add_argument("--top", type=int, default=100,
                    help="Number of top candidates to return. Default: 100")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini",
                    help="Embedding model used at precompute time. MUST match. Default: mini")
    ap.add_argument("--recall-factor", type=int, default=5,
                    help="FAISS fetches recall_factor*top candidates before re-ranking. Default: 5")
    ap.add_argument("--llm-reasoning", action="store_true",
                    help="Use OpenAI (if OPENAI_API_KEY set) for richer one-sentence reasoning")
    ap.add_argument("--json", default=None,
                    help="Write results as JSON to this path (in addition to stdout table)")
    ap.add_argument("--csv", default=None,
                    help="Write results as CSV to this path (for spreadsheet import)")
    ap.add_argument("--explain", default=None, metavar="CANDIDATE_ID",
                    help="Print a detailed signal-by-signal trace for this candidate (after the normal search)")
    ap.add_argument("--benchmark", type=int, default=None, metavar="N",
                    help="Run the search N times and report p50/p95 latency (warm). Suppresses normal output.")
    ap.add_argument("--out-dir", default="runs",
                    help="Output directory for batch mode (--jd-dir). Default: runs/")
    ap.add_argument("--hybrid", action="store_true",
                    help="Enable hybrid retrieval (FAISS dense + BM25 sparse via RRF). "
                         "Requires precompute.py --hybrid.")
    ap.add_argument("--dense-weight", type=float, default=1.0,
                    help="Weight for the dense (FAISS) contribution in RRF fusion. Default: 1.0")
    ap.add_argument("--sparse-weight", type=float, default=1.0,
                    help="Weight for the sparse (BM25) contribution in RRF fusion. Default: 1.0")
    ap.add_argument("--no-color", action="store_true",
                    help="Disable ANSI color even when stdout is a TTY")
    args = ap.parse_args()

    if args.no_color:
        os.environ["NO_COLOR"] = "1"

    # ---- batch mode ----
    if args.jd_dir:
        run_batch(jd_dir=args.jd_dir, index_dir=args.index,
                  candidates_path=args.candidates, top_k=args.top,
                  model_key=args.model, out_dir=args.out_dir,
                  recall_factor=args.recall_factor)
        return

    if not args.jd:
        ap.error("--jd is required (unless --jd-dir is set)")

    # ---- benchmark mode ----
    if args.benchmark is not None:
        if os.path.exists(args.jd):
            with open(args.jd, "r", encoding="utf-8") as f:
                jd_text = f.read()
        else:
            jd_text = args.jd
        report = run_benchmark(jd_text=jd_text, index_dir=args.index,
                               candidates_path=args.candidates, model_key=args.model,
                               n_runs=args.benchmark, top_k=args.top,
                               recall_factor=args.recall_factor)
        print_benchmark(report)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"[+] benchmark report written to {args.json}", file=sys.stderr)
        return

    # ---- Resolve JD: file path or literal text ----
    if os.path.exists(args.jd):
        with open(args.jd, "r", encoding="utf-8") as f:
            jd_text = f.read()
    else:
        jd_text = args.jd

    # ---- Sanity-check the index exists ----
    if not os.path.exists(os.path.join(args.index, "candidates.faiss")):
        print(f"[error] FAISS index not found at {args.index}/candidates.faiss\n"
              f"        Run: python precompute.py --candidates data/candidates.jsonl "
              f"--output {args.index}", file=sys.stderr)
        sys.exit(2)

    # ---- LLM client (optional) ----
    llm_client = get_llm_client() if args.llm_reasoning else None
    if args.llm_reasoning and llm_client is None:
        print("[warn] --llm-reasoning set but OPENAI_API_KEY not found — "
              "falling back to local template reasoning.", file=sys.stderr)

    # ---- Validate --explain candidate exists (cheap pre-check) ----
    explain_target = args.explain
    if explain_target and args.candidates and os.path.exists(args.candidates):
        cand = load_single_candidate(args.candidates, explain_target)
        if cand is None:
            print(f"[warn] --explain candidate {explain_target} not found in "
                  f"{args.candidates}; will still attempt by id.", file=sys.stderr)

    # ---- Run search ----
    results, jd, timing, explain_cs, explain_sim = run_search(
        jd_text=jd_text,
        index_dir=args.index,
        candidates_path=args.candidates,
        top_k=args.top,
        model_key=args.model,
        use_llm=args.llm_reasoning,
        llm_client=llm_client,
        recall_factor=args.recall_factor,
        return_explain_for=explain_target,
        use_hybrid=args.hybrid,
        dense_weight=args.dense_weight,
        sparse_weight=args.sparse_weight,
    )

    # ---- Print styled results ----
    print(ui.render_results(results, jd, timing, show_signals_for_all=False))

    # ---- Per-candidate explain ----
    if explain_target:
        if explain_cs is None:
            print(f"\n[error] candidate {explain_target} was not in the top-{args.top * args.recall_factor} "
                  f"retrieved by FAISS — try raising --recall-factor or --top.", file=sys.stderr)
        else:
            cand = load_single_candidate(args.candidates or "", explain_target) or {
                "id": explain_target, "name": explain_target
            }
            reasoning = explain_cs.reasoning or generate_reasoning(
                explain_cs, cand, jd, use_llm=False, llm_client=None
            )
            print(ui.render_explain(
                jd=jd, candidate=cand, cs_signals=explain_cs.signals,
                matched=explain_cs.matched_skills, missing=explain_cs.missing_skills,
                reasoning=reasoning, sim=explain_sim, weights=WEIGHTS,
            ))

    # ---- JSON export ----
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({
                "query_jd": jd_text[:500],
                "parsed_jd": {k: v for k, v in jd.items() if k != "raw_text"},
                "timing_ms": timing,
                "top_k": args.top,
                "results": results,
            }, f, indent=2)
        print(f"[+] JSON results written to {args.json}", file=sys.stderr)

    # ---- CSV export ----
    if args.csv:
        write_csv(results, args.csv)


if __name__ == "__main__":
    main()
