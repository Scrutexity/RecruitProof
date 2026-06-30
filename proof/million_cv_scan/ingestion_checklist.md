# Ingestion Checklist

Pre-flight checklist before running the million-CV proof scan.

## Customer-side (15 minutes)

- [ ] Export resumes from Encore as a zipped folder of PDF/DOCX files
  - [ ] Recommended sample size: 5,000–50,000 for pilot, 500,000+ for full proof
  - [ ] File naming: `firstname_lastname_encoreid.pdf` (not required, but helps dedup)
- [ ] Remove any resumes with explicit "do not contact" flags (Encore field: `no_contact = true`)
- [ ] Confirm you have legal right to share these resumes for evaluation purposes
- [ ] Identify 3 real job descriptions your team is currently sourcing for
- [ ] Note your current ATS annual spend (for the ROI snapshot)

## RecruitProof-side (5 minutes)

- [ ] Provision isolated VPC (Option A) or ship Docker image (Option B)
- [ ] Verify S3 / local storage has enough capacity (1 GB per 10K resumes)
- [ ] Confirm embedding model cached locally (avoids 4-minute download on first run)
- [ ] Pre-warm FAISS + BM25 libraries (one-time, 30 sec)
- [ ] Confirm deletion timer is set (24 hours after delivery)

## During the run (60 minutes for 500K resumes)

- [ ] Monitor ingestion throughput (target: ≥ 150 files/sec)
- [ ] Watch failed-file count (acceptable: < 5% of total)
- [ ] Watch duplicate count (typical: 1–3% of total)
- [ ] Verify no outbound network traffic (local-first audit)
- [ ] Confirm checkpoint is being written every 1,000 files

## Post-run (15 minutes)

- [ ] Review failed_files.csv — decide whether to re-run with OCR for image-only PDFs
- [ ] Review hidden_candidates.csv — confirm at least 1 hidden candidate per JD
- [ ] Send shortlists + ROI snapshot + proof report to customer
- [ ] Start 24-hour deletion timer
- [ ] Generate deletion certificate (DEL-YYYY-MMDD-NNN)

## Customer sign-off

- [ ] Customer reviews shortlists with 3 recruiters (30 min)
- [ ] Customer signs pilot-completion form
- [ ] Decision: proceed to Phase 2 / decline / extend pilot

## Estimated total customer time: 45 minutes
## Estimated total RecruitProof time: 90 minutes
## Total elapsed time: 24 hours (per the PILOT.md commitment)
