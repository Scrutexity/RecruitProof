# Encore Export Format

RecruitProof can start with the smallest safe export that Encore can provide.

## Minimum viable export

| Field | Required | Notes |
|---|---:|---|
| candidate_id | yes | Stable Encore ID |
| resume_file | yes | PDF or DOCX attachment |
| file_type | yes | pdf/doc/docx |
| created_at | yes | Candidate creation timestamp |
| updated_at | no | Useful for stale record analysis |
| email_hash | preferred | Hash before export if PII must stay masked |
| phone_hash | preferred | Hash before export if PII must stay masked |
| source | no | LinkedIn, referral, job board, etc. |
| recruiter_owner | no | Useful for audit trail |
| last_contacted_at | no | Useful for rediscovery prioritization |

## Preferred batch layout

```text
encore_export_001/
  manifest.csv
  resumes/
    cand_000001.pdf
    cand_000002.docx
  checksums.sha256
```

## Proof batch size

Start with 5,000-10,000 CVs for a first proof. Scale to 500k-1M after parser success and privacy checks pass.
