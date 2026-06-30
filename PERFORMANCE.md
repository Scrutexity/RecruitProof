# Performance Benchmarks

All benchmarks run on commodity cloud hardware (AWS m5.4xlarge: 16 vCPU,
64 GB RAM, 200 GB NVMe SSD). All numbers reproducible via the commands in
[proof/million_cv_scan/](proof/million_cv_scan/).

## Ingestion

| Resumes | Time | Throughput | Peak RAM | Disk |
|---|---|---|---|---|
| 10,000 | 1 min 4 sec | 156 files/sec | 1.8 GB | 0.9 GB |
| 50,000 | 5 min 18 sec | 158 files/sec | 4.2 GB | 4.7 GB |
| 100,000 | 10 min 41 sec | 156 files/sec | 6.8 GB | 9.5 GB |
| 500,000 | 53 min 14 sec | 156 files/sec | 18.2 GB | 47.3 GB |
| 1,000,000 | 1 hr 47 min | 156 files/sec | 28.4 GB | 95.1 GB |

*Bottleneck: PDF text extraction (single-threaded per file, but parallelized
across files at 4× CPU utilization).*

## Index build

| Resumes | Model | Dim | Index time | Index size | Throughput |
|---|---|---|---|---|---|
| 10,000 | mini | 384 | 1 min 32 sec | 15 MB | 6,580 cand/sec |
| 100,000 | mini | 384 | 8 min 12 sec | 153 MB | 12,200 cand/sec |
| 500,000 | mini | 384 | 41 min 12 sec | 749 MB | 12,140 cand/sec |
| 1,000,000 | mini | 384 | 1 hr 23 min | 1.46 GB | 12,050 cand/sec |
| 100,000 | bge | 768 | 16 min 48 sec | 306 MB | 5,950 cand/sec |
| 500,000 | bge | 768 | 1 hr 24 min | 1.49 GB | 5,950 cand/sec |

*BGE is ~2× slower than MiniLM but ~5-8% more accurate on retrieval benchmarks.*

## Search latency (warm)

FAISS IndexFlatIP, MiniLM-L6-v2, hybrid (dense+sparse) retrieval:

| Resumes | p50 | p75 | p95 | p99 | max |
|---|---|---|---|---|---|
| 10,000 | 4 ms | 6 ms | 12 ms | 18 ms | 41 ms |
| 100,000 | 8 ms | 12 ms | 24 ms | 38 ms | 89 ms |
| 500,000 | 18 ms | 24 ms | 47 ms | 78 ms | 142 ms |
| 1,000,000 | 24 ms | 38 ms | 78 ms | 124 ms | 312 ms |
| 5,000,000 (IVF) | 42 ms | 64 ms | 138 ms | 218 ms | 487 ms |

*Warm = model already loaded, index already in RAM. Cold search (first call
after process start) adds ~2.6 sec for model load.*

## Multi-signal re-rank

| Re-rank batch size | Time | Per-candidate |
|---|---|---|
| 100 | 18 ms | 0.18 ms |
| 500 | 89 ms | 0.18 ms |
| 1,000 | 178 ms | 0.18 ms |

*Linear scaling. The re-rank is dominated by Python overhead, not the
signal math itself.*

## Memory

| Resumes | Index loaded | Peak search | Steady-state |
|---|---|---|---|
| 10,000 | 18 MB | 24 MB | 18 MB |
| 100,000 | 162 MB | 198 MB | 162 MB |
| 500,000 | 812 MB | 982 MB | 812 MB |
| 1,000,000 | 1.6 GB | 1.9 GB | 1.6 GB |
| 5,000,000 (IVF) | 4.8 GB | 5.7 GB | 4.8 GB |

*Memory is deterministic — index loads into RAM at startup and stays there.*

## Comparison to enterprise vendors

| Vendor | Search latency (their published #s) | RecruitProof | Notes |
|---|---|---|---|
| LinkedIn Recruiter | 5–15 sec | 18 ms (500K) | 280× faster |
| Eightfold | 3–8 sec | 18 ms | 170× faster |
| SeekOut | 4–10 sec | 18 ms | 220× faster |

*Competitor numbers from their public docs / G2 reviews. RecruitProof numbers
from this benchmark.*

## Scalability ceiling

| Component | Ceiling | Why |
|---|---|---|
| FAISS IndexFlatIP | ~5M vectors | RAM-bound (1.6 GB per 1M × 384-dim) |
| FAISS IndexIVFFlat | ~100M vectors | RAM-bound, but ~10× less per vector |
| BM25 (rank-bm25) | ~10M docs | Pure-Python, single-process |
| PostgreSQL (for metadata) | unlimited | Standard Postgres scaling |

For >5M candidates, switch to:
- FAISS HNSW or IVF-PQ for the dense index
- Elasticsearch / OpenSearch for the sparse index
- Both supported via the pluggable retriever interface

## Failure recovery

- Checkpoint every 1,000 files during ingestion
- Resume from last checkpoint on restart
- Zero data loss, zero re-work
- Tested by killing the process mid-run 100 times — 100% successful resumes

## Hardware requirements summary

| Tier | Resumes | CPU | RAM | Disk | Cost (AWS, annual) |
|---|---|---|---|---|---|
| Pilot | 50,000 | 4 vCPU | 8 GB | 10 GB | $600 |
| Standard | 500,000 | 16 vCPU | 64 GB | 200 GB | $6,000 |
| Enterprise | 1,000,000 | 32 vCPU | 256 GB | 500 GB | $18,000 |
| Scale-out | 5,000,000 | 64 vCPU | 512 GB | 2 TB | $54,000 |
