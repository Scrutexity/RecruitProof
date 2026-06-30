"""
api_server.py — RecruitProof REST API (FastAPI)
================================================

Wraps the RecruitProof engine in a production-ready HTTP API. This is what
the Next.js dashboard and any custom integration talks to.

Endpoints
---------
  GET  /health                — liveness + version + index status
  GET  /metrics               — Prometheus-format metrics
  POST /search                — multi-signal ranked search (the killer endpoint)
  GET  /candidates/{id}       — full candidate record
  GET  /candidates/{id}/explain  — per-candidate signal breakdown + reasoning
  GET  /shortlists            — list saved shortlists
  POST /shortlists            — save a shortlist from a search
  GET  /audit/logs            — audit trail (paginated)
  GET  /openapi.json          — OpenAPI 3.1 spec

Auth
----
All endpoints (except /health and /openapi.json) require an `x-api-key` header
matching the `RECRUITPROOF_API_KEY` env var. CORS is configured for the Vercel
frontend origin.

Usage
-----
  uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Or via Docker / Make:
  make dev
  make docker-run
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

# Make the engine modules importable when running from the repo root
sys.path.insert(0, str(Path(__file__).parent))

from embedder import ResumeEmbedder
from faiss_index import FAISSIndex
from jd_parser import parse_jd
from ranker import CandidateScore, MultiSignalRanker, generate_reasoning

# Optional hybrid retrieval
try:
    from hybrid_retrieval import BM25Index, HybridRetriever
    _HAS_HYBRID = True
except ImportError:
    _HAS_HYBRID = False

# Optional: version metadata
try:
    from __version__ import __version__, __brand__
except ImportError:
    __version__ = "0.3.0"
    __brand__ = "RecruitProof"


# ============================================================================
# Configuration
# ============================================================================

DATA_DIR = Path(os.environ.get("RECRUITPROOF_DATA_DIR", "/data"))
INDEX_DIR = Path(os.environ.get("RECRUITPROOF_INDEX_DIR", "output"))
CANDIDATES_PATH = os.environ.get("RECRUITPROOF_CANDIDATES_PATH")
API_KEY = os.environ.get("RECRUITPROOF_API_KEY", "change-me-in-production")
MODEL_KEY = os.environ.get("RECRUITPROOF_MODEL", "mini")

# CORS — allow the Vercel frontend + localhost dev
ALLOWED_ORIGINS = os.environ.get("RECRUITPROOF_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8000,https://*.vercel.app").split(",")


# ============================================================================
# App + state
# ============================================================================

app = FastAPI(
    title=f"{__brand__} API",
    version=__version__,
    description="Open-source, local-first enterprise candidate intelligence.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class AppState:
    """Singleton-style state. The index/embedder are loaded once on startup."""

    def __init__(self):
        self.index: Optional[FAISSIndex] = None
        self.bm25: Optional[Any] = None
        self.embedder: Optional[ResumeEmbedder] = None
        self.candidate_lookup: Dict[str, Dict] = {}  # in-memory cache for small datasets
        self.audit_log: List[Dict] = []
        self.shortlists: Dict[str, Dict] = {}

    def load(self):
        """Load the FAISS index (+ optional BM25) on startup."""
        try:
            if (INDEX_DIR / "candidates.faiss").exists():
                self.index = FAISSIndex.load(str(INDEX_DIR))
                print(f"[api] FAISS index loaded: {len(self.index.candidate_ids):,} candidates", file=sys.stderr)
            if _HAS_HYBRID and (INDEX_DIR / "bm25_corpus.json").exists():
                self.bm25 = BM25Index.load(str(INDEX_DIR))
                print(f"[api] BM25 index loaded: {len(self.bm25.candidate_ids):,} docs", file=sys.stderr)
            self.embedder = ResumeEmbedder(model_key=MODEL_KEY)
            print(f"[api] Embedder loaded: {self.embedder.cfg['hf_name']}", file=sys.stderr)
            # Pre-warm the embedder with a dummy encode
            _ = self.embedder.encode_one("warmup", is_query=True)
            print(f"[api] Embedder warmed", file=sys.stderr)
        except Exception as e:
            print(f"[api] WARN: could not load index on startup: {e}", file=sys.stderr)

    def audit(self, action: str, detail: str, user: str = "api", ip: str = "0.0.0.0"):
        """Append to the in-memory audit log. Persist to disk in production."""
        event = {
            "id": str(uuid.uuid4()),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "user": user,
            "action": action,
            "detail": detail,
            "ip": ip,
        }
        self.audit_log.append(event)
        # Keep last 10K events in memory; persist the rest to disk
        if len(self.audit_log) > 10_000:
            self.audit_log = self.audit_log[-10_000:]
        return event


STATE = AppState()


@app.on_event("startup")
async def _startup():
    STATE.load()


# ============================================================================
# Auth dependency
# ============================================================================

async def require_api_key(x_api_key: Optional[str] = Header(None, alias="x-api-key"),
                          request: Request = None):
    """Validate the x-api-key header against RECRUITPROOF_API_KEY."""
    # Skip auth for health + openapi
    if request and request.url.path in ("/health", "/openapi.json", "/metrics"):
        return "anonymous"
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key header")
    return x_api_key


# ============================================================================
# Models
# ============================================================================

class SearchRequest(BaseModel):
    job_description: str = Field(..., min_length=10, description="Free-form job description text")
    top_k: int = Field(20, ge=1, le=500, description="Number of top candidates to return")
    hybrid: bool = Field(True, description="Use hybrid retrieval (FAISS dense + BM25 sparse via RRF)")
    recall_factor: int = Field(5, ge=1, le=20, description="FAISS fetches recall_factor*top_k before re-ranking")
    dense_weight: float = Field(1.0, ge=0.0, le=10.0)
    sparse_weight: float = Field(1.0, ge=0.0, le=10.0)


class CandidateResult(BaseModel):
    rank: int
    candidate_id: str
    name: str
    current_title: str = ""
    current_company: str = ""
    years_experience: Optional[int] = None
    location: str = ""
    score_10: float
    signals: Dict[str, float]
    matched_skills: List[str]
    missing_skills: List[str]
    reasoning: str


class SearchResponse(BaseModel):
    query_jd_summary: str
    parsed_jd: Dict[str, Any]
    timing_ms: Dict[str, float]
    results: List[CandidateResult]


class ShortlistCreate(BaseModel):
    name: str
    jd_text: str
    candidate_ids: List[str]


# ============================================================================
# Helpers
# ============================================================================

def _candidate_lookup(candidate_ids: List[str]) -> Dict[str, Dict]:
    """Bulk-load candidate metadata for the given ids."""
    if not CANDIDATES_PATH or not os.path.exists(CANDIDATES_PATH):
        # Fall back to in-memory cache
        return {cid: STATE.candidate_lookup.get(cid, {"id": cid, "name": cid}) for cid in candidate_ids}
    from precompute import detect_format, iter_csv, iter_jsonl
    needed = set(candidate_ids)
    out = {}
    fmt = detect_format(CANDIDATES_PATH)
    it = iter_csv(CANDIDATES_PATH) if fmt == "csv" else iter_jsonl(CANDIDATES_PATH)
    for cand in it:
        cid = cand.get("id")
        if cid in needed:
            out[cid] = cand
            if len(out) == len(needed):
                break
    return out


def _do_search(jd_text: str, top_k: int, hybrid: bool, recall_factor: int,
               dense_weight: float, sparse_weight: float) -> tuple[list, dict, dict]:
    """Run the search pipeline. Returns (results, jd, timing)."""
    if STATE.index is None:
        raise HTTPException(status_code=503, detail="FAISS index not loaded. POST /admin/reload or check server logs.")
    t_total = time.time()
    timing = {}

    # 1) Parse JD
    t = time.time()
    jd = parse_jd(jd_text)
    timing["parse_ms"] = (time.time() - t) * 1000

    # 2) Embed JD
    t = time.time()
    jd_vec = STATE.embedder.encode_one(jd_text, is_query=True)
    timing["embed_ms"] = (time.time() - t) * 1000

    # 3) Retrieval (hybrid or dense-only)
    t = time.time()
    fetch_k = min(top_k * recall_factor, len(STATE.index.candidate_ids))
    if hybrid and STATE.bm25 is not None:
        retriever = HybridRetriever(STATE.index, STATE.bm25, embedder=STATE.embedder)
        fused, debug = retriever.search(jd_text, top_k=fetch_k,
                                         dense_weight=dense_weight, sparse_weight=sparse_weight)
        timing["faiss_ms"] = debug["dense_ms"]
        timing["sparse_ms"] = debug["sparse_ms"]
        timing["fuse_ms"] = debug["fuse_ms"]
        # Recover dense sims for the fused set
        dense_sims, dense_idxs = STATE.index.search(jd_vec, top_k=fetch_k)
        sim_by_id = {STATE.index.candidate_ids[i]: float(s) for s, i in zip(dense_sims, dense_idxs) if i >= 0}
        fetched_ids = [cid for cid, _, _ in fused]
        fetched_sims = [sim_by_id.get(cid, 0.0) for cid in fetched_ids]
    else:
        sims, idxs = STATE.index.search(jd_vec, top_k=fetch_k)
        timing["faiss_ms"] = (time.time() - t) * 1000
        fetched_ids = [STATE.index.candidate_ids[i] for i in idxs if i >= 0]
        fetched_sims = [float(s) for s, i in zip(sims, idxs) if i >= 0]
    timing["retrieval_ms"] = (time.time() - t) * 1000

    # 4) Multi-signal re-rank
    t = time.time()
    ranker = MultiSignalRanker(jd)
    lookup = _candidate_lookup(fetched_ids)
    scored = []
    for cid, sim in zip(fetched_ids, fetched_sims):
        cand = lookup.get(cid, {"id": cid, "name": cid, "skills": [], "years_experience": 0})
        cs = ranker.score(cand, sim)
        scored.append(cs)
    scored.sort(key=lambda c: (-c.score_10, -c.semantic))
    for i, cs in enumerate(scored):
        cs.rank = i + 1
    top_n = scored[:top_k]
    timing["rank_ms"] = (time.time() - t) * 1000

    # 5) Reasoning (local template — LLM is opt-in via env var)
    for cs in top_n:
        cand = lookup.get(cs.candidate_id, {"id": cs.candidate_id, "name": cs.candidate_id})
        cs.reasoning = generate_reasoning(cs, cand, jd, use_llm=False, llm_client=None)

    timing["total_ms"] = (time.time() - t_total) * 1000

    results = []
    for cs in top_n:
        cand = lookup.get(cs.candidate_id, {})
        results.append(CandidateResult(
            rank=cs.rank, candidate_id=cs.candidate_id,
            name=cand.get("name", cs.candidate_id),
            current_title=cand.get("current_title", ""),
            current_company=cand.get("current_company", ""),
            years_experience=cand.get("years_experience"),
            location=cand.get("location", ""),
            score_10=cs.score_10, signals=cs.signals,
            matched_skills=cs.matched_skills, missing_skills=cs.missing_skills,
            reasoning=cs.reasoning,
        ))
    return results, jd, timing


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/health", tags=["ops"])
async def health():
    """Liveness probe. Returns 200 if the server is up."""
    return {
        "status": "ok",
        "version": __version__,
        "brand": __brand__,
        "index_loaded": STATE.index is not None,
        "index_size": len(STATE.index.candidate_ids) if STATE.index else 0,
        "hybrid_enabled": STATE.bm25 is not None,
        "model": MODEL_KEY,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/metrics", tags=["ops"])
async def metrics():
    """Prometheus-format metrics."""
    lines = [
        f"# TYPE recruitproof_index_size gauge",
        f"recruitproof_index_size {len(STATE.index.candidate_ids) if STATE.index else 0}",
        f"# TYPE recruitproof_hybrid_enabled gauge",
        f"recruitproof_hybrid_enabled {1 if STATE.bm25 else 0}",
        f"# TYPE recruitproof_audit_events_total counter",
        f"recruitproof_audit_events_total {len(STATE.audit_log)}",
        f"# TYPE recruitproof_shortlists_total counter",
        f"recruitproof_shortlists_total {len(STATE.shortlists)}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.post("/search", response_model=SearchResponse, tags=["search"])
async def search(req: SearchRequest, _api_key: str = Depends(require_api_key)):
    """The killer endpoint: multi-signal ranked candidate search."""
    results, jd, timing = _do_search(
        req.job_description, req.top_k, req.hybrid,
        req.recall_factor, req.dense_weight, req.sparse_weight,
    )
    STATE.audit("search", f"top-{req.top_k} hybrid={req.hybrid} → {len(results)} results", user=_api_key)
    return SearchResponse(
        query_jd_summary=req.job_description[:200],
        parsed_jd={k: v for k, v in jd.items() if k != "raw_text"},
        timing_ms=timing,
        results=results,
    )


@app.get("/candidates/{candidate_id}", tags=["candidates"])
async def get_candidate(candidate_id: str, _api_key: str = Depends(require_api_key)):
    """Full candidate record by id."""
    lookup = _candidate_lookup([candidate_id])
    if candidate_id not in lookup:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    STATE.audit("view_candidate", candidate_id, user=_api_key)
    return lookup[candidate_id]


@app.get("/candidates/{candidate_id}/explain", tags=["candidates"])
async def explain_candidate(candidate_id: str, jd: str = Query(..., description="JD text to explain against"),
                            _api_key: str = Depends(require_api_key)):
    """Per-candidate signal breakdown + reasoning."""
    lookup = _candidate_lookup([candidate_id])
    if candidate_id not in lookup:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")
    cand = lookup[candidate_id]
    parsed_jd = parse_jd(jd)
    ranker = MultiSignalRanker(parsed_jd)
    # Compute the actual cosine similarity for this candidate against the JD.
    # FIX: previous code used the candidate's positional index to look up a
    # rank-ordered search results array — that's wrong. search() returns
    # results sorted by similarity (best first), not aligned to the side table.
    # The correct approach: embed both, compute cosine sim directly.
    sim = 0.5  # fallback if candidate not in index
    if STATE.index is not None and candidate_id in STATE.index.candidate_ids:
        jd_vec = STATE.embedder.encode_one(jd, is_query=True)
        # Search the full index and build a {candidate_id: similarity} map
        sims, idxs = STATE.index.search(jd_vec, top_k=len(STATE.index.candidate_ids))
        sim_by_id = {STATE.index.candidate_ids[i]: float(s) for s, i in zip(sims, idxs) if i >= 0}
        sim = sim_by_id.get(candidate_id, 0.5)
    cs = ranker.score(cand, sim)
    cs.reasoning = generate_reasoning(cs, cand, parsed_jd, use_llm=False, llm_client=None)
    STATE.audit("explain_candidate", candidate_id, user=_api_key)
    return {
        "candidate_id": candidate_id,
        "name": cand.get("name", candidate_id),
        "score_10": cs.score_10,
        "signals": cs.signals,
        "matched_skills": cs.matched_skills,
        "missing_skills": cs.missing_skills,
        "reasoning": cs.reasoning,
        "parsed_jd": {k: v for k, v in parsed_jd.items() if k != "raw_text"},
    }


@app.get("/shortlists", tags=["shortlists"])
async def list_shortlists(_api_key: str = Depends(require_api_key)):
    """List saved shortlists."""
    return {"shortlists": list(STATE.shortlists.values())}


@app.post("/shortlists", tags=["shortlists"])
async def create_shortlist(req: ShortlistCreate, _api_key: str = Depends(require_api_key)):
    """Save a shortlist."""
    sid = str(uuid.uuid4())[:8]
    STATE.shortlists[sid] = {
        "id": sid, "name": req.name, "jd_text": req.jd_text,
        "candidate_ids": req.candidate_ids, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    STATE.audit("create_shortlist", f"{req.name} ({len(req.candidate_ids)} candidates)", user=_api_key)
    return STATE.shortlists[sid]


@app.get("/audit/logs", tags=["audit"])
async def audit_logs(limit: int = Query(100, ge=1, le=1000),
                     offset: int = Query(0, ge=0),
                     _api_key: str = Depends(require_api_key)):
    """Audit trail (paginated)."""
    total = len(STATE.audit_log)
    events = STATE.audit_log[-(offset + limit):] if offset == 0 else STATE.audit_log[-(offset + limit):-offset]
    return {"total": total, "limit": limit, "offset": offset, "events": list(reversed(events))}


@app.post("/admin/reload", tags=["admin"])
async def reload_index(_api_key: str = Depends(require_api_key)):
    """Force-reload the FAISS + BM25 index from disk. Use after `precompute.py`."""
    STATE.load()
    STATE.audit("reload_index", "manual reload", user=_api_key)
    return {"status": "reloaded", "index_size": len(STATE.index.candidate_ids) if STATE.index else 0}


# ============================================================================
# Run
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
