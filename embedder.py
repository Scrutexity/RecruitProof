"""
embedder.py — Embedding Layer
============================

Converts raw resume text (or job descriptions) into dense vector embeddings
that capture semantic meaning, not just keyword overlap.

Two models are supported:
  * BAAI/bge-base-en-v1.5  → 768-dim, higher accuracy (default)
  * all-MiniLM-L6-v2        → 384-dim, ~5× faster on CPU (pass --mini)

The layer is lazy-loaded so the CLI stays snappy when --help is invoked.

Usage:
    from embedder import ResumeEmbedder
    emb = ResumeEmbedder(model_name="BAAI/bge-base-en-v1.5")
    vectors = emb.encode_batch(["resume text...", "another resume..."])
"""
from __future__ import annotations

import os
from typing import Iterable, List, Optional

import numpy as np

# Set HF cache to a local dir so installs don't pollute $HOME.
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(__file__), ".hf_cache"))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # silence noisy HF logs
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# BGE models benefit from prepending a query instruction when encoding queries.
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

MODEL_REGISTRY = {
    "bge": {
        "hf_name": "BAAI/bge-base-en-v1.5",
        "dim": 768,
        "normalize": True,            # BGE → use IndexFlatIP (inner product on normalized = cosine)
        "query_instruction": _BGE_QUERY_INSTRUCTION,
    },
    "mini": {
        "hf_name": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "normalize": True,
        "query_instruction": "",
    },
}


class ResumeEmbedder:
    """Lazy wrapper around sentence-transformers.

    The model is only loaded the first time `encode_batch` is called — this
    keeps `python search.py --help` instant.
    """

    def __init__(self, model_key: str = "bge"):
        if model_key not in MODEL_REGISTRY:
            raise ValueError(
                f"Unknown model_key={model_key!r}. "
                f"Choose one of: {list(MODEL_REGISTRY)}"
            )
        self.model_key = model_key
        self.cfg = MODEL_REGISTRY[model_key]
        self.dim = self.cfg["dim"]
        self._model = None  # lazy

    def _load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install -r requirements.txt"
            ) from e
        # local_files_only=False allows first-time download (~440MB for BGE).
        self._model = SentenceTransformer(
            self.cfg["hf_name"],
            device="cpu",
        )

    def encode_batch(
        self,
        texts: Iterable[str],
        batch_size: int = 64,
        show_progress: bool = False,
        is_query: bool = False,
    ) -> np.ndarray:
        """Encode a batch of texts into a (N, dim) float32 array.

        - `is_query=True` prepends the model's query instruction (BGE trick).
        - Output is L2-normalized so inner product ≈ cosine similarity.
        """
        self._load()
        texts = list(texts)
        if is_query and self.cfg["query_instruction"]:
            texts = [self.cfg["query_instruction"] + t for t in texts]

        # Only show the tqdm bar when stderr is a TTY — keeps logs clean in
        # CI / piped runs.
        import sys as _sys
        progress = show_progress and _sys.stderr.isatty()

        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=progress,
            convert_to_numpy=True,
            normalize_embeddings=self.cfg["normalize"],
        )
        # FAISS wants float32.
        return np.ascontiguousarray(vecs, dtype=np.float32)

    def encode_one(self, text: str, is_query: bool = False) -> np.ndarray:
        """Encode a single text → (dim,) float32 vector."""
        return self.encode_batch([text], is_query=is_query)[0]


def build_resume_text(candidate: dict) -> str:
    """Flatten a candidate dict into a single embedding-friendly string.

    The text is the only thing the embedding model sees, so we deliberately
    front-load the highest-signal fields (title, skills, summary) and let the
    BGE model's training capture semantic role/skill overlap with the JD.
    """
    parts: List[str] = []
    if candidate.get("current_title"):
        parts.append(candidate["current_title"])
    if candidate.get("headline"):
        parts.append(candidate["headline"])
    skills = candidate.get("skills") or []
    if skills:
        parts.append("Skills: " + ", ".join(skills[:20]))
    if candidate.get("summary"):
        parts.append(candidate["summary"])
    if candidate.get("target_title"):
        parts.append("Target: " + candidate["target_title"])
    companies = candidate.get("previous_companies") or []
    if companies:
        parts.append("Previous companies: " + ", ".join(companies[:5]))
    if candidate.get("education"):
        parts.append("Education: " + candidate["education"])
    if candidate.get("certifications"):
        parts.append("Certs: " + ", ".join(candidate["certifications"][:5]))
    return " | ".join(parts) if parts else (candidate.get("name", "") or "")
