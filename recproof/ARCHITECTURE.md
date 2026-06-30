# Architecture

```text
Encore Export
  → File Manifest
  → Parser Workers
  → Normalized Candidate JSONL
  → Dedupe Engine
  → Embedding Pipeline
  → FAISS + BM25 Index
  → Multi-Signal Ranker
  → Candidate Intelligence UI
  → Audit Log + Proof Report
```

## Components

- Parser: PDF/DOCX text extraction
- Normalizer: candidate identity and skill fields
- Dedupe: exact and fuzzy duplicate clustering
- Index: FAISS vector search and optional BM25
- Ranker: semantic, role-fit, skills, behavioral, career velocity
- UI: executive proof dashboard and recruiter workflow
