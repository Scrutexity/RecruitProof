# Architecture

## High-level

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRE-COMPUTATION (Run Once)                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ 1M Resumes   │───▶│  Embedder    │───▶│  FAISS Index     │   │
│  │ (JSONL/CSV)  │    │ (bge/MiniLM) │    │ (1M × 384/768 d) │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│                      ┌──────────────┐                            │
│                      │  BM25 Index  │  (for hybrid retrieval)    │
│                      └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SEARCH (<3 sec on CPU)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Parse JD          → jd_parser.parse_jd()             │   │
│  │  2. Embed JD          → ResumeEmbedder.encode_one()       │   │
│  │  3. Hybrid retrieval  → FAISS top-K + BM25 top-K → RRF    │   │
│  │  4. Multi-signal rank → MultiSignalRanker.score()         │   │
│  │     • Semantic   40%  (cosine sim)                        │   │
│  │     • Role-Fit   20%  (title+seniority+location+YoE)     │   │
│  │     • Skills     15%  (proficiency-weighted fuzzy match) │   │
│  │     • Behavioral 15%  (recency+response+warmth)          │   │
│  │     • Career     10%  (velocity+stability+progression)   │   │
│  │  5. Reasoning         → local template OR OpenAI          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Modules

| Module | Responsibility |
|---|---|
| `embedder.py` | Resume/JD → vector embeddings (BGE or MiniLM) |
| `faiss_index.py` | FAISS IndexFlatIP / IndexIVFFlat wrapper |
| `hybrid_retrieval.py` | BM25 sparse + RRF fusion with FAISS dense |
| `jd_parser.py` | Free-form JD → structured fields |
| `ranker.py` | 5-signal MultiSignalRanker |
| `agents.py` | 4-agent screening pipeline |
| `agent_pipeline.py` | Agentic mode CLI |
| `ats_connectors.py` | Workday/Greenhouse/Lever/Ashby connectors |
| `competitive_intel.py` | Pricing + savings calculator |
| `ui.py` | ANSI-color terminal UI |
| `precompute.py` | JSONL/CSV → embeddings → FAISS+BM25 index |
| `search.py` | Main CLI entrypoint |
| `generate_synthetic_data.py` | Synthetic candidate generator |

## Data flow

```
Encore export (zip)
    │
    ▼
ingest_encore.py
    │ (PDF/DOCX → text, dedup, extract metadata)
    ▼
candidates.jsonl
    │
    ▼
precompute.py --hybrid
    │
    ├──▶ output/candidates.faiss  (dense index)
    ├──▶ output/bm25_corpus.json  (sparse index)
    └──▶ output/candidate_ids.json (side table)
                │
                ▼
            search.py --hybrid --jd <file> --top 100
                │
                ▼
            shortlist.json + executive report
```

## Agentic pipeline

```
JD input
    │
    ▼
SourcingAgent  ──▶  HybridRetriever  ──▶  top-N candidates
    │
    ▼
ScreenAgent  ──▶  Stage-1 fast filter (skills + seniority + recency)
    │
    ▼
DeepEvalAgent  ──▶  MultiSignalRanker + optional LLM judgment
    │
    ▼
ExplainAgent  ──▶  reasoning + interview talking points
    │
    ▼
Final ranked shortlist
```

## Why local-first

- Privacy: candidate data never leaves your network
- Cost: no per-query API fees
- Speed: no network latency
- Compliance: GDPR / CCPA / SOC2 friendly
- Auditability: every line of code is open-source

## Why hybrid retrieval

- Dense (FAISS) alone misses exact-skill matches for uncommon keywords
- Sparse (BM25) alone misses semantic synonyms
- RRF fusion combines both with zero weight-tuning
- Measured: 40% top-10 recall improvement vs. dense-only

## Why multi-signal ranking

- Cosine similarity alone rewards keyword-stuffed resumes
- The 5-signal rubric (Sem 40 + Role 20 + Skill 15 + Behav 15 + Career 10)
  models what recruiters actually care about
- Every signal is explainable — recruiters can see why a candidate ranked #N

## Why FAISS over alternatives

- Free, open-source, battle-tested (Meta production)
- IndexFlatIP: exact, sub-5ms for 1M vectors
- IndexIVFFlat: approximate, sub-1ms for 100M vectors
- Scales linearly with RAM
- No operational overhead (no cluster, no shards)

For >5M candidates, swap to HNSW or IVF-PQ via the pluggable retriever
interface.

## Why BM25 over Elasticsearch

- For ≤10M docs, rank-bm25 is sufficient and ~100× lighter to operate
- No cluster, no JVM, no shards
- Index is a single JSON file — backup is `cp`
- For >10M docs, swap to Elasticsearch via the pluggable retriever interface

## Pluggability

Every component is swappable:

| Component | Default | Alternative |
|---|---|---|
| Embedder | sentence-transformers | OpenAI embeddings API |
| Dense index | FAISS IndexFlatIP | FAISS IVF / HNSW / Milvus |
| Sparse index | rank-bm25 | Elasticsearch / OpenSearch |
| LLM (reasoning) | local template | OpenAI / Ollama / Anthropic |
| Metadata store | JSONL | PostgreSQL / DuckDB |
| Auth | local bcrypt | SAML 2.0 SSO |
| Deployment | Docker | Kubernetes / bare metal |

## Performance characteristics

See [PERFORMANCE.md](PERFORMANCE.md) for the full benchmark report.

| Operation | Latency (500K candidates) |
|---|---|
| Cold search (first call) | 2.8 sec |
| Warm search (subsequent) | 18 ms p50 |
| Index build | 41 min |
| Ingestion | 156 files/sec |

## Security architecture

See [SECURITY.md](SECURITY.md).

- AES-256-GCM at rest
- TLS 1.3 in transit
- RBAC (5 roles)
- Hash-chained audit logs
- No outbound traffic during search
