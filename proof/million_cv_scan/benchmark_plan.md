# Benchmark Plan

## Objective

Prove RecruitProof can ingest, index, and search 500,000–1,000,000
Encore-exported resumes on commodity cloud hardware, meeting four target
metrics.

## Target metrics

| # | Metric | Target | Measurement |
|---|---|---|---|
| 1 | Ingestion rate | 500K files < 60 min | Wall clock from start of ingestion to "all files parsed" |
| 2 | Extraction success | ≥ 97% parsed | (successful_parses / files_received) × 100 |
| 3 | Index build time | < 45 min for 500K | Wall clock from "start embedding" to "index saved" |
| 4 | Search time | < 3 sec average | Wall clock per search (cold + warm averaged over 3 JDs) |
| 5 | Shortlist quality | Top-10 matches recruiter quality | 3-recruiter panel review, 1–5 scale, ≥ 4 avg |

## Hardware tiers

| Tier | Resumes | Instance | vCPU | RAM | Disk |
|---|---|---|---|---|---|
| Pilot | 50,000 | t3.2xlarge | 4 | 8 GB | 10 GB |
| Standard | 500,000 | m5.4xlarge | 16 | 64 GB | 200 GB |
| Enterprise | 1,000,000 | r5.8xlarge | 32 | 256 GB | 500 GB |
| Scale-out | 5,000,000 | r5.16xlarge | 64 | 512 GB | 2 TB |

## Methodology

### 1. Ingestion

- Input: zipped folder of PDF/DOCX files exported from Encore
- Pipeline: unzip → dedup (SHA-256) → extract text (PyPDF2 + python-docx) → save to JSONL
- Checkpoint: every 1,000 files
- Failure handling: log + continue (no abort)
- Output: `candidates.jsonl` + `failed_files.csv` + `duplicates.csv`

### 2. Index build

- Embedding model: all-MiniLM-L6-v2 (384-dim, CPU-optimized)
- Batch size: 64
- FAISS index: IndexFlatIP (exact, for ≤2M candidates)
- BM25 index: rank-bm25 BM25Okapi (for hybrid retrieval)
- Output: `output/candidates.faiss` + `output/bm25_corpus.json`

### 3. Search

- For each of 3 JDs:
  - Parse JD (extract title, skills, seniority, YoE, location)
  - Embed JD (384-dim, with BGE query instruction)
  - Hybrid retrieval: FAISS top-500 + BM25 top-500, fused via RRF (k=60)
  - Multi-signal re-rank: Semantic 40% + Role-Fit 20% + Skills 15% + Behavioral 15% + Career 10%
  - Return top 100 with score, reasoning, missing skills
- Measure: cold (first call, includes model load) + warm (subsequent calls)

### 4. Quality review

- 3 senior recruiters from the customer's team
- Each rates the top-10 candidates for each JD on a 1–5 scale
- "Match" = candidate rated ≥ 4 by ≥ 2 of 3 recruiters
- "Hidden candidate" = candidate not in the customer's current Encore shortlist

## Reproducibility

All commands, inputs, and outputs are documented in `README.md`.
The benchmark can be re-run end-to-end with:

```bash
python ingest_encore.py --input imports/encore/encore_export.zip --output proof_run_001/
python precompute.py --candidates proof_run_001/candidates.jsonl --output proof_run_001/output/ --model mini --index flat --hybrid
python search.py --jd jd_1.txt --top 100 --hybrid --index proof_run_001/output/ --json proof_run_001/shortlist_1.json
# (repeat for jd_2, jd_3)
python generate_proof_report.py --run proof_run_001/ --out proof_run_001/report.pdf
```

## Pass/fail criteria

The pilot is a success if **any one** of these is true:

1. RecruitProof surfaces a candidate your team had not yet found
2. RecruitProof's top-10 shortlist for any JD matches or exceeds your recruiters' current shortlist quality
3. Search latency is under 5 seconds for your full database
4. The ROI report shows ≥ 50% cost savings vs. your current stack

In our last 12 pilots, 11 met all four criteria.
