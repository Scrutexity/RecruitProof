"""
agents.py — Agentic Multi-Agent Screening Pipeline
=================================================

The #1 enterprise ask in 2026 is agentic AI for recruitment. This module
implements a 4-agent screening pipeline that orchestrates the existing
search + scoring primitives through a transparent, explainable workflow.

Agents (each is a stateless callable):
  1. SourcingAgent   — runs hybrid retrieval, returns top-N raw candidates
  2. ScreenAgent     — Stage-1 fast filter: drop obvious non-fits using a
                       cheap heuristic (skill overlap + seniority band +
                       recency). Mirrors serai's two-stage funnel.
  3. DeepEvalAgent   — Stage-2 deep evaluation: re-scores survivors with the
                       full MultiSignalRanker + optional local LLM judgment.
  4. ExplainAgent    — generates a per-candidate explanation + interview
                       talking points. Local-first (template) by default;
                       Ollama or OpenAI if available.

Local-first design (stolen from agentic-resume-screening):
  - All four agents run without any external API call by default.
  - If a local Ollama server is running (http://localhost:11434), the
    DeepEvalAgent and ExplainAgent will use it for richer natural-language
    reasoning. Falls back silently to rule-based reasoning if unavailable.
  - If OPENAI_API_KEY is set, it is preferred over Ollama for the reasoning
    steps (but the pipeline still works without it).

The pipeline is exposed as `AgentPipeline.run(jd_text, top_k)` and prints a
beautiful per-agent event log so recruiters can watch the agents work.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from jd_parser import parse_jd
from ranker import (
    CandidateScore,
    MultiSignalRanker,
    WEIGHTS,
    generate_reasoning,
)
from embedder import ResumeEmbedder
from faiss_index import FAISSIndex

# Optional hybrid retrieval
try:
    from hybrid_retrieval import BM25Index, HybridRetriever
    _HAS_HYBRID = True
except ImportError:
    _HAS_HYBRID = False

import ui


# ----------------------------------------------------------------- event log

@dataclass
class AgentEvent:
    agent: str          # "SourcingAgent" / "ScreenAgent" / etc.
    level: str          # "info" / "success" / "warn" / "decision"
    message: str
    payload: Optional[Dict] = None
    ts: float = field(default_factory=time.time)


@dataclass
class PipelineResult:
    jd: Dict
    sourced_count: int
    screened_count: int
    deep_eval_count: int
    final_results: List[Dict]
    events: List[AgentEvent] = field(default_factory=list)
    timing_ms: Dict[str, float] = field(default_factory=dict)


# ----------------------------------------------------------------- LLM client

class LocalLLMClient:
    """Thin wrapper around a local Ollama instance (if running).

    Falls back gracefully: if Ollama is not reachable, every method returns
    None and the caller falls back to rule-based reasoning.
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:3b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._available: Optional[bool] = None

    def _check(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self._available = (resp.status == 200)
        except Exception:
            self._available = False
        return self._available

    def generate(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        if not self._check():
            return None
        try:
            import urllib.request
            body = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.2},
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip() or None
        except Exception:
            return None


def get_reasoning_client(prefer_ollama: bool = True):
    """Return the best available reasoning client, or None.

    Priority: OPENAI_API_KEY (if set) > local Ollama (if running) > None.
    """
    # 1) OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            return {"kind": "openai", "client": OpenAI(api_key=os.environ["OPENAI_API_KEY"])}
        except Exception:
            pass
    # 2) Ollama
    if prefer_ollama:
        local = LocalLLMClient()
        if local._check():
            return {"kind": "ollama", "client": local}
    return None


def llm_reason(client_bundle, prompt: str, max_tokens: int = 200) -> Optional[str]:
    """Call the bundled LLM client. Returns None on any failure."""
    if client_bundle is None:
        return None
    kind = client_bundle["kind"]
    client = client_bundle["client"]
    try:
        if kind == "ollama":
            return client.generate(prompt, max_tokens=max_tokens)
        if kind == "openai":
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip() or None
    except Exception:
        return None
    return None


# ----------------------------------------------------------------- Agents

class SourcingAgent:
    """Agent 1: Hybrid retrieval over the full candidate index.

    Returns a list of (candidate_id, dense_sim, sparse_rank, fetched_rank)
    tuples for the top fetch_k candidates.
    """

    name = "SourcingAgent"

    def __init__(self, index: FAISSIndex, bm25_index=None, embedder=None):
        self.index = index
        self.bm25_index = bm25_index
        self.embedder = embedder

    def run(self, jd_text: str, fetch_k: int, use_hybrid: bool,
            dense_weight: float = 1.0, sparse_weight: float = 1.0
            ) -> Tuple[List[Tuple[str, float, Optional[int], int]], Dict]:
        if use_hybrid and self.bm25_index is not None and self.embedder is not None:
            retriever = HybridRetriever(self.index, self.bm25_index, embedder=self.embedder)
            fused, debug = retriever.search(
                query_text=jd_text, top_k=fetch_k,
                dense_weight=dense_weight, sparse_weight=sparse_weight,
            )
            # Recover dense sims for the fused set
            jd_vec = self.embedder.encode_one(jd_text, is_query=True)
            sims, idxs = self.index.search(jd_vec, top_k=fetch_k)
            sim_by_id = {self.index.candidate_ids[i]: float(s)
                         for s, i in zip(sims, idxs) if i >= 0}
            out = []
            for cid, _rrf, fused_rank in fused:
                out.append((cid, sim_by_id.get(cid, 0.0), None, fused_rank))
            return out, debug

        # Dense-only
        if self.embedder is None:
            raise RuntimeError("SourcingAgent needs an embedder")
        jd_vec = self.embedder.encode_one(jd_text, is_query=True)
        sims, idxs = self.index.search(jd_vec, top_k=fetch_k)
        out = []
        for rank, (sim, idx) in enumerate(zip(sims, idxs), start=1):
            if idx < 0:
                continue
            out.append((self.index.candidate_ids[idx], float(sim), None, rank))
        return out, {"dense_ms": 0.0, "total_ms": 0.0}


class ScreenAgent:
    """Agent 2: Stage-1 fast filter.

    Drops obvious non-fits using cheap heuristics:
      - skill overlap below a threshold
      - seniority band off by ≥3
      - last active > 365 days ago (stale)
    The survivors go to DeepEvalAgent.
    """

    name = "ScreenAgent"
    MIN_SKILL_OVERLAP = 1     # at least one required skill must fuzzy-match
    MAX_SENIORITY_DELTA = 2
    MAX_STALE_DAYS = 365

    def __init__(self, jd: Dict):
        self.jd = jd
        from ranker import detect_seniority, SENIORITY_BANDS, fuzzy_ratio
        self._detect = detect_seniority
        self._bands = SENIORITY_BANDS
        self._fuzz = fuzzy_ratio

    def screen(self, candidate: Dict, semantic_sim: float) -> Tuple[bool, str]:
        # 1) Skill overlap
        req = [s.lower() for s in (self.jd.get("required_skills") or [])]
        cand_skills = [s.lower() for s in (candidate.get("skills") or [])]
        overlap = 0
        for s in req:
            if any(self._fuzz(s, cs) >= 0.75 for cs in cand_skills):
                overlap += 1
        if overlap < self.MIN_SKILL_OVERLAP and semantic_sim < 0.6:
            return False, f"only {overlap}/{len(req)} required skills + low semantic sim"

        # 2) Seniority band
        jd_band = self._bands.get(self._detect(self.jd.get("title") or ""), 4)
        c_band = self._bands.get(self._detect(candidate.get("current_title") or ""), 4)
        if abs(jd_band - c_band) > self.MAX_SENIORITY_DELTA:
            return False, f"seniority delta {abs(jd_band-c_band)} (too far from {self.jd.get('seniority')})"

        # 3) Recency
        days = candidate.get("last_active_days_ago")
        if days is not None and days > self.MAX_STALE_DAYS:
            return False, f"stale ({days}d inactive)"

        return True, f"passed: {overlap}/{len(req)} skills, band delta {abs(jd_band-c_band)}"


class DeepEvalAgent:
    """Agent 3: Stage-2 deep evaluation.

    Runs the full MultiSignalRanker on each survivor. Optionally calls a
    local LLM to write a 1-2 sentence qualitative judgment that gets folded
    into the rationale.
    """

    name = "DeepEvalAgent"

    def __init__(self, jd: Dict, llm_client_bundle=None):
        self.ranker = MultiSignalRanker(jd)
        self.jd = jd
        self.llm = llm_client_bundle

    def evaluate(self, candidate: Dict, semantic_sim: float) -> CandidateScore:
        cs = self.ranker.score(candidate, semantic_sim)
        # Optional LLM judgment — folded into the rationale if available
        if self.llm is not None and cs.score_10 >= 6.0:
            prompt = (
                f"You are a senior technical recruiter. In ONE concise sentence (≤25 words), "
                f"explain why this candidate is or is not a strong fit for the role.\n\n"
                f"Role: {self.jd.get('title')} (seniority={self.jd.get('seniority')})\n"
                f"Required skills: {self.jd.get('required_skills')}\n\n"
                f"Candidate: {candidate.get('name')}, "
                f"{candidate.get('years_experience')}y as {candidate.get('current_title')} "
                f"at {candidate.get('current_company')}.\n"
                f"Skills: {(candidate.get('skills') or [])[:8]}\n"
                f"Multi-signal scores (0-1): semantic={cs.semantic}, role_fit={cs.role_fit}, "
                f"skills={cs.skills_match}, behavioral={cs.behavioral}, career={cs.career}\n\n"
                f"One sentence:"
            )
            llm_judgment = llm_reason(self.llm, prompt, max_tokens=80)
            if llm_judgment:
                cs.score_rationale = llm_judgment
        return cs


class ExplainAgent:
    """Agent 4: Generates per-candidate explanation + interview talking points.

    Local-first (template-based) by default. If an LLM client is available,
    uses it to produce richer explanations and 3 tailored interview questions.
    """

    name = "ExplainAgent"

    def __init__(self, jd: Dict, llm_client_bundle=None):
        self.jd = jd
        self.llm = llm_client_bundle

    def explain(self, cs: CandidateScore, candidate: Dict) -> Tuple[str, List[str]]:
        # Reasoning
        reasoning = generate_reasoning(
            cs, candidate, self.jd,
            use_llm=(self.llm is not None and self.llm["kind"] == "openai"),
            llm_client=self.llm["client"] if self.llm and self.llm["kind"] == "openai" else None,
        )
        # If Ollama, override reasoning with LLM output
        if self.llm is not None and self.llm["kind"] == "ollama":
            prompt = (
                f"In ONE concise sentence (≤25 words), explain why {candidate.get('name')} "
                f"is a strong match for the {self.jd.get('title')} role. "
                f"Score: {cs.score_10}/10. Top skills matched: {cs.matched_skills[:3]}."
            )
            llm_out = llm_reason(self.llm, prompt, max_tokens=80)
            if llm_out:
                reasoning = llm_out

        # Interview talking points
        talking_points = self._talking_points(cs, candidate)
        return reasoning, talking_points

    def _talking_points(self, cs: CandidateScore, candidate: Dict) -> List[str]:
        # Local template — always works
        skills = candidate.get("skills") or []
        top_skill = skills[0] if skills else "your strongest skill"
        yoe = candidate.get("years_experience", "?")
        points = [
            f"Walk us through a production {top_skill} system you owned end-to-end.",
            f"In {yoe} years, what's the biggest technical decision you regret?",
        ]
        if cs.missing_skills:
            points.append(f"How would you ramp on {cs.missing_skills[0]} — concrete first 30 days?")
        if cs.behavioral < 0.5:
            points.append("Your recent activity is light — what's your job-search timeline?")
        if cs.career >= 0.7:
            points.append("Tell us about your most recent promotion — what did you change?")
        # Optional LLM enrichment
        if self.llm is not None:
            prompt = (
                f"Generate 2 concise technical interview questions for "
                f"{candidate.get('name')} applying to {self.jd.get('title')}. "
                f"Skills: {skills[:5]}. Missing: {cs.missing_skills[:2]}. "
                f"Return as a JSON array of strings."
            )
            llm_out = llm_reason(self.llm, prompt, max_tokens=200)
            if llm_out:
                try:
                    # Try to parse JSON array from the response
                    import re
                    m = re.search(r"\[.*\]", llm_out, re.DOTALL)
                    if m:
                        extra = json.loads(m.group(0))
                        if isinstance(extra, list) and extra:
                            points = points[:1] + [str(q) for q in extra[:2]]
                except Exception:
                    pass
        return points[:3]


# ----------------------------------------------------------------- Pipeline

class AgentPipeline:
    """Orchestrates the 4-agent screening pipeline.

    Usage:
        pipe = AgentPipeline(index_dir="output", candidates_path="data/candidates.jsonl",
                             model_key="mini", use_hybrid=True)
        result = pipe.run(jd_text="...", top_k=10)
        print(result.final_results)
    """

    def __init__(self, index_dir: str, candidates_path: Optional[str],
                 model_key: str = "mini", use_hybrid: bool = True,
                 llm_client_bundle=None, verbose: bool = True):
        self.index_dir = index_dir
        self.candidates_path = candidates_path
        self.model_key = model_key
        self.use_hybrid = use_hybrid and _HAS_HYBRID
        self.llm = llm_client_bundle
        self.verbose = verbose

        # Lazy-loaded once, reused across runs
        self._index: Optional[FAISSIndex] = None
        self._bm25: Optional[Any] = None
        self._embedder: Optional[ResumeEmbedder] = None

    def _ensure_loaded(self):
        if self._index is None:
            self._index = FAISSIndex.load(self.index_dir)
        if self.use_hybrid and self._bm25 is None:
            bm25_path = os.path.join(self.index_dir, "bm25_corpus.json")
            if os.path.exists(bm25_path):
                self._bm25 = BM25Index.load(self.index_dir)
            else:
                if self.verbose:
                    print("[pipeline] --hybrid requested but no BM25 index; falling back to dense.",
                          file=sys.stderr)
                self.use_hybrid = False
        if self._embedder is None:
            self._embedder = ResumeEmbedder(model_key=self.model_key)

    def _emit(self, events: List[AgentEvent], agent: str, level: str, msg: str, payload=None):
        ev = AgentEvent(agent=agent, level=level, message=msg, payload=payload)
        events.append(ev)
        if self.verbose:
            color = {
                "info": ui._C.GRAY, "success": ui._C.BRIGHT_GREEN,
                "warn": ui._C.YELLOW, "decision": ui._C.CYAN,
            }.get(level, ui._C.GRAY)
            print(f"  {ui.c(f'[{agent}]', color, ui._C.BOLD)} {msg}", file=sys.stderr)

    def _load_candidates(self, ids: List[str]) -> Dict[str, Dict]:
        """Bulk-load candidate metadata for the given ids."""
        if not self.candidates_path or not os.path.exists(self.candidates_path):
            return {}
        from precompute import detect_format, iter_csv, iter_jsonl
        fmt = detect_format(self.candidates_path)
        it = iter_csv(self.candidates_path) if fmt == "csv" else iter_jsonl(self.candidates_path)
        needed = set(ids)
        out = {}
        for cand in it:
            cid = cand.get("id")
            if cid in needed:
                out[cid] = cand
                if len(out) == len(needed):
                    break
        return out

    def run(self, jd_text: str, top_k: int = 10,
            fetch_k: Optional[int] = None) -> PipelineResult:
        self._ensure_loaded()
        events: List[AgentEvent] = []
        timing: Dict[str, float] = {}
        t_total = time.time()

        # ---- Parse JD
        t = time.time()
        jd = parse_jd(jd_text)
        timing["parse_ms"] = (time.time() - t) * 1000
        self._emit(events, "JDParser", "info",
                   f"Parsed JD: title={jd['title']!r}, seniority={jd['seniority']}, "
                   f"{len(jd.get('required_skills') or [])} required skills")

        # ---- Agent 1: Sourcing
        self._emit(events, "SourcingAgent", "info",
                   f"Retrieving candidates (hybrid={self.use_hybrid})...")
        t = time.time()
        if fetch_k is None:
            fetch_k = min(top_k * 5, len(self._index.candidate_ids))
        sourcing = SourcingAgent(self._index, self._bm25, self._embedder)
        sourced, src_debug = sourcing.run(jd_text, fetch_k=fetch_k, use_hybrid=self.use_hybrid)
        timing["sourcing_ms"] = (time.time() - t) * 1000
        self._emit(events, "SourcingAgent", "success",
                   f"Retrieved {len(sourced)} candidates in {timing['sourcing_ms']:.0f}ms")

        # ---- Load candidate metadata
        sourced_ids = [s[0] for s in sourced]
        lookup = self._load_candidates(sourced_ids)

        # ---- Agent 2: Screen
        self._emit(events, "ScreenAgent", "info", "Stage-1 fast filter...")
        t = time.time()
        screener = ScreenAgent(jd)
        survivors = []
        rejected = 0
        for cid, sim, _, _ in sourced:
            cand = lookup.get(cid, {"id": cid, "name": cid, "skills": [],
                                    "current_title": "", "years_experience": 0})
            ok, reason = screener.screen(cand, sim)
            if ok:
                survivors.append((cid, sim, cand))
            else:
                rejected += 1
        timing["screen_ms"] = (time.time() - t) * 1000
        self._emit(events, "ScreenAgent", "decision",
                   f"{len(survivors)} survived, {rejected} rejected "
                   f"({timing['screen_ms']:.0f}ms)")

        # ---- Agent 3: DeepEval
        self._emit(events, "DeepEvalAgent", "info",
                   f"Stage-2 deep evaluation on {len(survivors)} survivors..."
                   + (f" [LLM: {self.llm['kind']}]" if self.llm else " [rule-based]"))
        t = time.time()
        evaluator = DeepEvalAgent(jd, llm_client_bundle=self.llm)
        scored: List[CandidateScore] = []
        for cid, sim, cand in survivors:
            cs = evaluator.evaluate(cand, sim)
            scored.append(cs)
        scored.sort(key=lambda c: (-c.score_10, -c.semantic))
        for i, cs in enumerate(scored):
            cs.rank = i + 1
        top_n = scored[:top_k]
        timing["deep_eval_ms"] = (time.time() - t) * 1000
        self._emit(events, "DeepEvalAgent", "success",
                   f"Top {len(top_n)} selected in {timing['deep_eval_ms']:.0f}ms")

        # ---- Agent 4: Explain
        self._emit(events, "ExplainAgent", "info", "Generating explanations + interview questions...")
        t = time.time()
        explainer = ExplainAgent(jd, llm_client_bundle=self.llm)
        final_results = []
        for cs in top_n:
            cand = lookup.get(cs.candidate_id, {"id": cs.candidate_id, "name": cs.candidate_id})
            reasoning, talking_points = explainer.explain(cs, cand)
            final_results.append({
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
                "reasoning": reasoning,
                "interview_talking_points": talking_points,
                "llm_judgment": cs.score_rationale if self.llm is not None else None,
            })
        timing["explain_ms"] = (time.time() - t) * 1000
        self._emit(events, "ExplainAgent", "success",
                   f"Generated {len(final_results)} explanations in {timing['explain_ms']:.0f}ms")

        timing["total_ms"] = (time.time() - t_total) * 1000
        self._emit(events, "Pipeline", "success",
                   f"Pipeline complete in {timing['total_ms']:.0f}ms — "
                   f"sourced={len(sourced)} → screened={len(survivors)} → "
                   f"deep_eval={len(scored)} → top={len(final_results)}")

        return PipelineResult(
            jd=jd,
            sourced_count=len(sourced),
            screened_count=len(survivors),
            deep_eval_count=len(scored),
            final_results=final_results,
            events=events,
            timing_ms=timing,
        )


def render_pipeline_result(result: PipelineResult, show_talking_points: bool = True) -> str:
    """Pretty-print the agent pipeline result, including the per-agent event log."""
    out: List[str] = []

    # Banner
    out.append(ui.c("╔" + "═" * 78, ui._C.MAGENTA, ui._C.BOLD))
    out.append(ui.c("║", ui._C.MAGENTA, ui._C.BOLD)
              + ui.c("  RecruitProof — Agentic Screening Pipeline (4-Agent)", ui._C.BOLD)
              + " " * 22 + ui.c("║", ui._C.MAGENTA, ui._C.BOLD))
    out.append(ui.c("╚" + "═" * 78, ui._C.MAGENTA, ui._C.BOLD))
    out.append("")

    # JD card
    out.append(ui.render_jd_card(result.jd))
    out.append("")

    # Agent event log
    out.append(ui.c("  Agent Event Log", ui._C.BOLD))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    for ev in result.events:
        color = {
            "info": ui._C.GRAY, "success": ui._C.BRIGHT_GREEN,
            "warn": ui._C.YELLOW, "decision": ui._C.CYAN,
        }.get(ev.level, ui._C.GRAY)
        glyph = {"info": "→", "success": "✓", "warn": "!", "decision": "◆"}.get(ev.level, "·")
        out.append(f"  {ui.c(glyph, color)} {ui.c(ev.agent, ui._C.BOLD):<16} {ev.message}")
    out.append("")

    # Funnel summary
    out.append(ui.c("  Funnel", ui._C.BOLD))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    out.append(f"  Sourced → Screened → DeepEval → Final")
    out.append(f"  {result.sourced_count:>7} → {result.screened_count:>7} → "
               f"{result.deep_eval_count:>7} → {len(result.final_results):>5}")
    out.append("")

    # Timing
    cells = []
    for k, v in result.timing_ms.items():
        if k == "total_ms":
            continue
        cells.append(f"{ui.c(k.replace('_ms','').upper(), ui._C.GRAY)} {v:>5.0f}ms")
    total_str = f"{result.timing_ms['total_ms']:.0f}ms"
    cells.append(f"{ui.c('TOTAL', ui._C.BOLD)} {ui.c(total_str, ui._C.BRIGHT_GREEN, ui._C.BOLD)}")
    out.append("  " + "  ".join(cells))
    out.append("")

    # Result cards
    out.append(ui.c(f"  Top {len(result.final_results)} Finalists (with interview talking points)", ui._C.BOLD))
    out.append(ui.c("  " + "─" * 76, ui._C.DIM))
    out.append("")
    for i, r in enumerate(result.final_results):
        verbose = i < 3
        out.extend(ui.render_result_card(r, verbose_signals=verbose))
        if show_talking_points and verbose:
            for tp in r.get("interview_talking_points", []):
                out.append("         " + ui.c("• ", ui._C.BRIGHT_CYAN) + ui.c(tp, ui._C.DIM))
        if r.get("llm_judgment") and verbose:
            out.append("         " + ui.c("LLM: ", ui._C.YELLOW) + ui.c(r["llm_judgment"], ui._C.DIM))
        out.append("")

    # Footer
    out.append(ui.c("  " + "═" * 76, ui._C.MAGENTA))
    if result.final_results:
        top1 = result.final_results[0]
        out.append("  " + ui.c("TOP FINALIST  ", ui._C.BOLD, ui._C.BRIGHT_GREEN)
                  + ui.c(top1["name"], ui._C.BOLD) + "  "
                  + ui.c(f"{top1['score_10']}/10", ui.score_color(top1["score_10"]), ui._C.BOLD))
        if top1.get("missing_skills"):
            out.append("  " + ui.c("WHY NOT 10/10:  ", ui._C.YELLOW)
                      + ui.c(f"missing {', '.join(top1['missing_skills'])}", ui._C.RED))
        out.append("  " + ui.c("REASONING:       ", ui._C.GRAY) + top1["reasoning"])
    out.append(ui.c("  " + "═" * 76, ui._C.MAGENTA))
    out.append("")
    return "\n".join(out)
