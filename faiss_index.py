"""
faiss_index.py — Indexing Layer
==============================

Wraps FAISS to provide a 1M-vector index with sub-5ms search on CPU.

Two index types are supported (user picks at precompute time):
  * IndexFlatIP        — exact brute-force inner product. ~5ms for 1M×768 on
                         a modern CPU. Zero tuning. Use for ≤2M vectors.
  * IndexIVFFlat       — approximate but ~10× faster at 10M+ scale. Requires
                         `nlist` (clusters) training. Set `nprobe` at search
                         to trade recall for speed.

Both indices store L2-normalized vectors, so inner product = cosine sim in
[−1, 1]. We rescale to [0, 1] for the semantic-score component of the
multi-signal ranker.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

import faiss
import numpy as np


@dataclass
class FAISSIndex:
    """A trained FAISS index + the candidate_id side-table.

    FAISS returns integer row indices; we keep a parallel JSON list to map
    row → candidate_id (and the original metadata, if desired).
    """

    index: faiss.Index
    candidate_ids: List[str] = field(default_factory=list)
    dim: int = 0
    index_type: str = "flat"     # "flat" | "ivf"
    nlist: int = 0               # only meaningful for IVF
    nprobe: int = 8              # only meaningful for IVF (search-time knob)

    # ------------------------------------------------------------------ build

    @classmethod
    def build_flat(cls, vectors: np.ndarray, candidate_ids: List[str]) -> "FAISSIndex":
        """Build an exact IndexFlatIP from a (N, dim) float32 array."""
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
        vectors = np.ascontiguousarray(vectors)
        dim = vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(vectors)
        return cls(index=index, candidate_ids=list(candidate_ids), dim=dim, index_type="flat")

    @classmethod
    def build_ivf(
        cls,
        vectors: np.ndarray,
        candidate_ids: List[str],
        nlist: Optional[int] = None,
    ) -> "FAISSIndex":
        """Build an IVF index. Requires a training pass over `vectors`.

        `nlist` defaults to sqrt(N), the FAISS rule-of-thumb.
        """
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
        vectors = np.ascontiguousarray(vectors)
        N, dim = vectors.shape
        if nlist is None:
            nlist = max(1, int(np.sqrt(N)))
        nlist = min(nlist, max(1, N // 39))  # FAISS wants ≥39 pts/cluster
        quantizer = faiss.IndexFlatIP(dim)
        index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(vectors)
        index.add(vectors)
        index.nprobe = 8
        return cls(
            index=index,
            candidate_ids=list(candidate_ids),
            dim=dim,
            index_type="ivf",
            nlist=nlist,
            nprobe=8,
        )

    # ----------------------------------------------------------------- search

    def search(self, query_vec: np.ndarray, top_k: int = 100) -> tuple[np.ndarray, np.ndarray]:
        """Return (scores, indices) of the top_k nearest neighbors.

        scores are inner-product similarities (cosine if vectors normalized).
        indices are row indices into candidate_ids.
        """
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        if query_vec.dtype != np.float32:
            query_vec = query_vec.astype(np.float32)
        query_vec = np.ascontiguousarray(query_vec)
        scores, indices = self.index.search(query_vec, top_k)
        return scores[0], indices[0]

    # ----------------------------------------------------------------- save/load

    def save(self, out_dir: str) -> None:
        """Persist the FAISS index + side-table to `out_dir`."""
        os.makedirs(out_dir, exist_ok=True)
        faiss.write_index(self.index, os.path.join(out_dir, "candidates.faiss"))
        meta = {
            "dim": self.dim,
            "index_type": self.index_type,
            "nlist": self.nlist,
            "nprobe": self.nprobe,
            "count": len(self.candidate_ids),
        }
        with open(os.path.join(out_dir, "index_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        with open(os.path.join(out_dir, "candidate_ids.json"), "w") as f:
            json.dump(self.candidate_ids, f)

    @classmethod
    def load(cls, out_dir: str) -> "FAISSIndex":
        """Load a previously persisted index."""
        index = faiss.read_index(os.path.join(out_dir, "candidates.faiss"))
        with open(os.path.join(out_dir, "index_meta.json")) as f:
            meta = json.load(f)
        with open(os.path.join(out_dir, "candidate_ids.json")) as f:
            candidate_ids = json.load(f)
        obj = cls(
            index=index,
            candidate_ids=candidate_ids,
            dim=meta["dim"],
            index_type=meta["index_type"],
            nlist=meta.get("nlist", 0),
            nprobe=meta.get("nprobe", 8),
        )
        # restore nprobe for IVF
        if obj.index_type == "ivf":
            try:
                obj.index.nprobe = obj.nprobe
            except Exception:
                pass
        return obj
