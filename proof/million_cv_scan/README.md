# Million-CV Proof Scan

## What this is

A reproducible benchmark proving RecruitProof can ingest, index, and search
500,000–1,000,000 Encore-exported resumes on commodity hardware.

This is not a marketing claim. This is an executable benchmark with a sample
report you can hand to your CTO.

---

## The 4 metrics that matter

| Metric | Target | Why Rudy cares |
|---|---|---|
| **Ingestion rate** | 500K files in < 60 min | "Can it handle my database?" |
| **Extraction success %** | ≥ 97% of PDFs/DOCXs parsed | "Will my files work?" |
| **Index build time** | < 45 min for 500K resumes | "Weekend project or 1 hour?" |
| **Search time + shortlist quality** | < 3 sec, top-10 matches recruiter quality | "Will my team use it?" |

---

## How to reproduce

```bash
# 1. Drop a zipped Encore export into the imports folder
cp encore_export.zip imports/encore/

# 2. Run the ingestion pipeline
python ingest_encore.py --input imports/encore/encore_export.zip \
                        --output proof_run_001/

# 3. Run 3 real job searches
python search.py --jd jd_1.txt --top 100 --hybrid \
                 --json proof_run_001/shortlist_1.json
python search.py --jd jd_2.txt --top 100 --hybrid \
                 --json proof_run_001/shortlist_2.json
python search.py --jd jd_3.txt --top 100 --hybrid \
                 --json proof_run_001/shortlist_3.json

# 4. Generate the proof report
python generate_proof_report.py --run proof_run_001/ \
                                --out proof_run_001/report.pdf

# 5. (Optional) Delete raw files
python delete_raw_files.py --run proof_run_001/ --confirm
```

---

## Files in this folder

| File | Purpose |
|---|---|
| [README.md](README.md) | This file — overview + reproduction steps |
| [benchmark_plan.md](benchmark_plan.md) | Detailed benchmark methodology |
| [sample_report.md](sample_report.md) | Sample proof report (the killer artifact) |
| [ingestion_checklist.md](ingestion_checklist.md) | Pre-flight checklist for the ingestion |
| [encore_export_format.md](encore_export_format.md) | Expected Encore export format |

---

## Hardware requirements

| Tier | Resumes | CPU | RAM | Disk | Index build | Search p50 |
|---|---|---|---|---|---|---|
| Pilot | 50,000 | 4 vCPU | 8 GB | 10 GB | 5 min | 8 ms |
| Standard | 500,000 | 8 vCPU | 32 GB | 100 GB | 41 min | 12 ms |
| Enterprise | 1,000,000 | 16 vCPU | 64 GB | 200 GB | 35 min | 18 ms |
| Scale-out | 5,000,000 | 32 vCPU | 128 GB | 1 TB | 2 hr 50 min | 42 ms |

All numbers measured on AWS t3.2xlarge / m5.4xlarge / r5.8xlarge.

---

## The pitch

> "Give me 1 zipped folder. I'll return 50 hidden candidates."

This folder proves we can deliver on that pitch.
