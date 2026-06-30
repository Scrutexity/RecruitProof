# Benchmark Plan

## Goals

Benchmark RecruitProof against a 500k-1M candidate archive using stable, repeatable, buyer-safe measurements.

## Metrics

1. Total files received
2. File type split: PDF, DOCX, other
3. Parse success rate
4. Duplicate rate
5. Index build time
6. Warm search latency
7. End-to-end search latency
8. Top-K explanation generation time
9. Export generation time
10. Hardware profile

## Required benchmark outputs

- `benchmark_summary.json`
- `parser_failures.csv`
- `duplicates.csv`
- `top_candidates.json`
- `roi_summary.md`
- `run_manifest.json`

## Test protocol

Run cold and warm searches. Report FAISS lookup separately from model load, embedding, reranking, and export time. Never represent warm lookup latency as full user-perceived latency.
