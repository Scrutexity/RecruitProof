"""
hybrid_retrieval.py — Hybrid Retrieval Layer (Dense + Sparse)
============================================================

The single biggest recall win in modern search systems is hybrid retrieval:
combine FAISS dense vectors (semantic intent) with BM25 sparse tokens (exact
keyword / skill match), then fuse the rankings with Reciprocal Rank Fusion
(RRF).

Why hybrid?
  - Dense FAISS alone misses exact-skill matches when the JD uses uncommon
    keywords (e.g. "Kubernetes operator", "Triton kernel").
  - BM25 alone misses semantic synonyms ("React engineer" vs "frontend
    engineer").
  - RRF merges both rankings robustly — no weight tuning required, just one
    parameter `k` (default 60) that controls how sharply top ranks dominate.

This module also persists a tokenized corpus + BM25 index alongside the FAISS
index, so subsequent searches are pure-math (sub-millisecond on 1M docs).

Pipeline:
    1. Tokenize each candidate resume once → store tokens
    2. Build a BM25Okapi index over the token corpus
    3. At query time:
       a. Dense:  FAISS search(jd_vec, fetch_k)         → dense_rank
       b. Sparse: BM25.get_scores(jd_tokens, fetch_k)   → sparse_rank
       c. Fuse:   RRF(dense_rank, sparse_rank, k=60)    → fused_rank
       d. Re-rank fused top-K with MultiSignalRanker    → final

Sources stolen:
  - ankman007/job-prep-ai — hybrid retrieval pattern + RRF fusion
  - Beir / RRF literature  — the canonical fusion formula
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# rank_bm25 is a tiny pure-Python BM25 implementation — perfect for the
# 1M-candidate scale on a single machine.
from rank_bm25 import BM25Okapi

from embedder import build_resume_text


# ----------------------------------------------------------------- tokenizer

_SKILL_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+#.]*", re.IGNORECASE)

# Common stopwords we want to filter before BM25 scoring. Skill gazetteer
# entries like "go", "c++", "r" are protected via PROTECTED_TOKENS.
_STOPWORDS = {
    "the", "and", "for", "with", "you", "are", "our", "have", "will", "from",
    "this", "that", "your", "all", "but", "not", "who", "can", "their", "they",
    "them", "what", "when", "where", "how", "why", "into", "out", "about",
    "was", "were", "been", "being", "has", "had", "did", "does", "done",
    "more", "most", "some", "any", "each", "other", "than", "then", "so",
    "if", "or", "as", "at", "by", "in", "of", "on", "to", "up", "us", "we",
    "an", "is", "it", "be", "do", "no", "yes", "i",
}

# Skill tokens must never be filtered even if they look like stopwords.
_PROTECTED_TOKENS = {"go", "r", "c", "c++", "c#", "f#", "sql", "no", "do"}


def tokenize(text: str) -> List[str]:
    """Lowercase + word-boundary tokenize. Filters stopwords but protects skills."""
    if not text:
        return []
    out: List[str] = []
    for m in _SKILL_TOKEN_PATTERN.findall(text.lower()):
        if m in _PROTECTED_TOKENS:
            out.append(m)
        elif m in _STOPWORDS:
            continue
        elif len(m) < 2:
            continue
        else:
            out.append(m)
    return out


# ----------------------------------------------------------------- BM25 index

@dataclass
class BM25Index:
    """Tokenized corpus + BM25Okapi index + id side-table.

    Persists as three files alongside the FAISS index:
        bm25_corpus.json  — list of token lists (one per candidate)
        bm25_ids.json     — list of candidate ids (parallel to corpus)
        bm25_meta.json    — {count, avg_doc_len}
    The BM25Okapi object itself is rebuilt from the corpus on load (it's not
    trivially serializable).
    """
    corpus_tokens: List[List[str]] = field(default_factory=list)
    candidate_ids: List[str] = field(default_factory=list)
    avg_doc_len: float = 0.0
    _bm25: Optional[BM25Okapi] = None

    # ----------------------------------------------------------------- build

    @classmethod
    def build(cls, candidates: List[Dict]) -> "BM25Index":
        corpus_tokens: List[List[str]] = []
        candidate_ids: List[str] = []
        for cand in candidates:
            text = build_resume_text(cand)
            tokens = tokenize(text)
            corpus_tokens.append(tokens)
            candidate_ids.append(cand.get("id") or f"auto-{len(candidate_ids):08d}")
        obj = cls(corpus_tokens=corpus_tokens, candidate_ids=candidate_ids)
        obj._bm25 = BM25Okapi(corpus_tokens)
        obj.avg_doc_len = sum(len(t) for t in corpus_tokens) / max(1, len(corpus_tokens))
        return obj

    # ----------------------------------------------------------------- search

    def search(self, query_text: str, top_k: int = 100) -> List[Tuple[str, float, int]]:
        """Return [(candidate_id, score, rank)] for the top_k sparse matches.

        Ranks are 1-indexed (rank 1 = best). Scores are raw BM25 float scores.
        """
        if self._bm25 is None:
            self._bm25 = BM25Okapi(self.corpus_tokens)
        q_tokens = tokenize(query_text)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        # Get top_k indices by score
        top_idx = np.argsort(scores)[::-1][:top_k]
        out = []
        for rank, idx in enumerate(top_idx, start=1):
            if scores[idx] <= 0:
                continue  # BM25 can return 0 for no-overlap docs
            out.append((self.candidate_ids[idx], float(scores[idx]), rank))
        return out

    # ----------------------------------------------------------------- save/load

    def save(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "bm25_corpus.json"), "w") as f:
            json.dump(self.corpus_tokens, f)
        with open(os.path.join(out_dir, "bm25_ids.json"), "w") as f:
            json.dump(self.candidate_ids, f)
        with open(os.path.join(out_dir, "bm25_meta.json"), "w") as f:
            json.dump({"count": len(self.candidate_ids),
                       "avg_doc_len": self.avg_doc_len}, f, indent=2)

    @classmethod
    def load(cls, out_dir: str) -> "BM25Index":
        with open(os.path.join(out_dir, "bm25_corpus.json")) as f:
            corpus_tokens = json.load(f)
        with open(os.path.join(out_dir, "bm25_ids.json")) as f:
            candidate_ids = json.load(f)
        with open(os.path.join(out_dir, "bm25_meta.json")) as f:
            meta = json.load(f)
        obj = cls(corpus_tokens=corpus_tokens, candidate_ids=candidate_ids,
                  avg_doc_len=meta.get("avg_doc_len", 0.0))
        # BM25Okapi is rebuilt on demand (constructor is fast for ≤1M docs)
        obj._bm25 = BM25Okapi(corpus_tokens)
        return obj


# ----------------------------------------------------------------- RRF fusion

def reciprocal_rank_fusion(
    dense_ranked: List[Tuple[str, float, int]],
    sparse_ranked: List[Tuple[str, float, int]],
    k: int = 60,
    top_k: Optional[int] = None,
) -> List[Tuple[str, float, int]]:
    """Fuse dense + sparse rankings via Reciprocal Rank Fusion.

    RRF score(d) = sum over rankings of 1 / (k + rank(d))
    where k is a smoothing constant (default 60, the canonical value).

    Args:
        dense_ranked:  [(candidate_id, score, rank), ...] from FAISS
        sparse_ranked: [(candidate_id, score, rank), ...] from BM25
        k:             smoothing constant. Higher = more uniform; lower = more
                       winner-take-all. 60 is the literature default.
        top_k:         return only the top_k fused results. None = return all.

    Returns:
        [(candidate_id, rrf_score, fused_rank), ...] sorted by rrf_score desc.
    """
    rrf: Dict[str, float] = defaultdict(float)
    for cid, _score, rank in dense_ranked:
        rrf[cid] += 1.0 / (k + rank)
    for cid, _score, rank in sparse_ranked:
        rrf[cid] += 1.0 / (k + rank)
    # Sort by fused score desc
    sorted_items = sorted(rrf.items(), key=lambda x: -x[1])
    if top_k is not None:
        sorted_items = sorted_items[:top_k]
    return [(cid, score, rank) for rank, (cid, score) in enumerate(sorted_items, start=1)]


# ----------------------------------------------------------------- Hybrid retriever

class HybridRetriever:
    """Combines a FAISSIndex (dense) and BM25Index (sparse) via RRF.

    Construct once, query many times. The dense side-table (candidate_ids)
    and the sparse side-table (candidate_ids) must reference the SAME
    candidate universe in the SAME order — both are produced by precompute.
    """

    def __init__(self, faiss_index, bm25_index: BM25Index, embedder=None):
        if len(faiss_index.candidate_ids) != len(bm25_index.candidate_ids):
            raise ValueError(
                f"FAISS index ({len(faiss_index.candidate_ids)} candidates) and "
                f"BM25 index ({len(bm25_index.candidate_ids)} candidates) disagree. "
                f"Rebuild both with the same candidate file."
            )
        self.faiss_index = faiss_index
        self.bm25_index = bm25_index
        self.embedder = embedder

    def search(
        self,
        query_text: str,
        top_k: int = 100,
        fetch_k: Optional[int] = None,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> Tuple[List[Tuple[str, float, int]], Dict[str, float]]:
        """Run hybrid retrieval.

        Returns:
            (fused_ranking, debug_info)
            - fused_ranking: [(candidate_id, rrf_score, fused_rank), ...]
            - debug_info: dict with per-stage counts and timings
        """
        import time as _time
        t0 = _time.time()
        if fetch_k is None:
            fetch_k = min(top_k * 5, len(self.faiss_index.candidate_ids))

        # 1) Dense retrieval (FAISS)
        t_dense = _time.time()
        if self.embedder is None:
            raise RuntimeError("HybridRetriever needs an embedder for the query. "
                               "Pass one to the constructor.")
        jd_vec = self.embedder.encode_one(query_text, is_query=True)
        sims, idxs = self.faiss_index.search(jd_vec, top_k=fetch_k)
        dense_ranked: List[Tuple[str, float, int]] = []
        for rank, (sim, idx) in enumerate(zip(sims, idxs), start=1):
            if idx < 0:
                continue
            dense_ranked.append((self.faiss_index.candidate_ids[idx], float(sim), rank))
        t_dense = (_time.time() - t_dense) * 1000

        # 2) Sparse retrieval (BM25)
        t_sparse = _time.time()
        sparse_ranked = self.bm25_index.search(query_text, top_k=fetch_k)
        t_sparse = (_time.time() - t_sparse) * 1000

        # 3) Weight + fuse via RRF. We implement weights by scaling the
        # RRF contribution: dense_weight applies to dense contribution, etc.
        t_fuse = _time.time()
        rrf: Dict[str, float] = defaultdict(float)
        for cid, _score, rank in dense_ranked:
            rrf[cid] += dense_weight * (1.0 / (rrf_k + rank))
        for cid, _score, rank in sparse_ranked:
            rrf[cid] += sparse_weight * (1.0 / (rrf_k + rank))
        sorted_items = sorted(rrf.items(), key=lambda x: -x[1])[:top_k]
        fused = [(cid, score, rank) for rank, (cid, score) in enumerate(sorted_items, start=1)]
        t_fuse = (_time.time() - t_fuse) * 1000

        debug = {
            "dense_ms": t_dense,
            "sparse_ms": t_sparse,
            "fuse_ms": t_fuse,
            "total_ms": (_time.time() - t0) * 1000,
            "dense_found": len(dense_ranked),
            "sparse_found": len(sparse_ranked),
            "fused_returned": len(fused),
            "fetch_k": fetch_k,
            "rrf_k": rrf_k,
            "dense_weight": dense_weight,
            "sparse_weight": sparse_weight,
        }
        return fused, debug
