#!/usr/bin/env python3
"""
agent_pipeline.py — Agentic Screening Pipeline CLI
=================================================

Entry point for the 4-agent screening pipeline (SourcingAgent → ScreenAgent
→ DeepEvalAgent → ExplainAgent). This is the "agentic AI" mode that the
enterprise market is asking for in 2026.

Usage:
    python agent_pipeline.py --jd data/sample_jd.txt --top 10
    python agent_pipeline.py --jd jd.txt --top 10 --hybrid
    python agent_pipeline.py --jd jd.txt --top 10 --json out.json
    python agent_pipeline.py --jd jd.txt --top 10 --no-talking-points

Local-first by default. If OPENAI_API_KEY is set, uses GPT-4o-mini for the
DeepEval and Explain agents. Otherwise, if a local Ollama server is running
(http://localhost:11434), uses that. Otherwise, falls back to rule-based
reasoning — the pipeline still produces explainable ranked output.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from agents import (
    AgentPipeline,
    get_reasoning_client,
    render_pipeline_result,
)


def main():
    ap = argparse.ArgumentParser(
        description="RecruitProof — Agentic 4-agent screening pipeline (Sourcing → Screen → DeepEval → Explain).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent_pipeline.py --jd data/sample_jd.txt --top 10
  python agent_pipeline.py --jd jd.txt --top 10 --hybrid
  python agent_pipeline.py --jd jd.txt --top 20 --json pipeline_out.json
  OPENAI_API_KEY=sk-... python agent_pipeline.py --jd jd.txt --top 10
        """.strip(),
    )
    ap.add_argument("--jd", required=True,
                    help="Job description text OR path to a .txt file.")
    ap.add_argument("--index", default="output",
                    help="Directory containing the pre-built FAISS index. Default: output/")
    ap.add_argument("--candidates", default=None,
                    help="Path to candidates.jsonl/.csv (for metadata lookup).")
    ap.add_argument("--top", type=int, default=10,
                    help="Number of finalists to return. Default: 10")
    ap.add_argument("--model", choices=["bge", "mini"], default="mini",
                    help="Embedding model used at precompute time. MUST match. Default: mini")
    ap.add_argument("--hybrid", action="store_true",
                    help="Use hybrid retrieval (FAISS dense + BM25 sparse via RRF).")
    ap.add_argument("--no-ollama", action="store_true",
                    help="Don't try to use local Ollama even if it's running.")
    ap.add_argument("--no-talking-points", action="store_true",
                    help="Hide interview talking points in the output.")
    ap.add_argument("--json", default=None,
                    help="Write full pipeline result as JSON to this path.")
    ap.add_argument("--no-color", action="store_true",
                    help="Disable ANSI color even when stdout is a TTY.")
    args = ap.parse_args()

    if args.no_color:
        os.environ["NO_COLOR"] = "1"

    # Resolve JD
    if os.path.exists(args.jd):
        with open(args.jd, "r", encoding="utf-8") as f:
            jd_text = f.read()
    else:
        jd_text = args.jd

    # Sanity-check the index
    if not os.path.exists(os.path.join(args.index, "candidates.faiss")):
        print(f"[error] FAISS index not found at {args.index}/candidates.faiss\n"
              f"        Run: python precompute.py --candidates data/candidates.jsonl "
              f"--output {args.index}", file=sys.stderr)
        sys.exit(2)

    # Reasoning client (OpenAI > Ollama > None)
    llm_bundle = get_reasoning_client(prefer_ollama=not args.no_ollama)
    if llm_bundle:
        print(f"[pipeline] using LLM backend: {llm_bundle['kind']}", file=sys.stderr)
    else:
        print("[pipeline] no LLM backend available — using rule-based reasoning only.",
              file=sys.stderr)

    # Run the pipeline
    pipe = AgentPipeline(
        index_dir=args.index,
        candidates_path=args.candidates,
        model_key=args.model,
        use_hybrid=args.hybrid,
        llm_client_bundle=llm_bundle,
        verbose=True,
    )
    result = pipe.run(jd_text=jd_text, top_k=args.top)

    # Render the styled output
    print(render_pipeline_result(result, show_talking_points=not args.no_talking_points))

    # Optional JSON dump
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({
                "jd": {k: v for k, v in result.jd.items() if k != "raw_text"},
                "timing_ms": result.timing_ms,
                "funnel": {
                    "sourced": result.sourced_count,
                    "screened": result.screened_count,
                    "deep_eval": result.deep_eval_count,
                    "final": len(result.final_results),
                },
                "events": [
                    {"agent": e.agent, "level": e.level, "message": e.message}
                    for e in result.events
                ],
                "results": result.final_results,
            }, f, indent=2)
        print(f"[+] JSON pipeline result written to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
