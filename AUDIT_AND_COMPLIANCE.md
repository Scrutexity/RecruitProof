# Audit & Compliance

## Every action is logged

RecruitProof records every user action in a tamper-evident audit log.
Logs are hash-chained (each log entry includes the SHA-256 of the previous
entry) and signed daily. Logs cannot be modified without detection.

## What is logged

| Event type | Captured fields |
|---|---|
| `search` | user, timestamp, query_hash, top_k, latency_ms, results_count |
| `view_candidate` | user, timestamp, candidate_id_hash, source_page |
| `export_shortlist` | user, timestamp, candidate_id_hashes[], format, file_size |
| `import_run` | user, timestamp, file_count, success_count, failed_count |
| `config_change` | user, timestamp, key, old_value_hash, new_value_hash |
| `login` | user, timestamp, ip, user_agent, mfa_used |
| `role_change` | admin_user, timestamp, target_user, old_role, new_role |
| `rollback` | user, timestamp, target_checkpoint, reason |

## What is NOT logged

- Resume text (never)
- Candidate PII (name, email, phone) — only SHA-256 hashes
- Search query text — only the SHA-256 of the query
- Internal candidate scores (they're reproducible from query + candidate)

## Log retention

| Tier | Retention |
|---|---|
| Standard | 7 years |
| Financial services | 7 years (SOX-aligned) |
| Healthcare | N/A (RecruitProof does not handle PHI) |
| EU customers | Configurable down to 30 days (GDPR right to erasure) |

## Compliance frameworks

### GDPR (architecture-compatible; formal review not yet completed)

- ✅ Right to access: candidates can request a copy of their data via the
  recruiting team (RecruitProof exposes a `GET /candidates/<id>/export` API)
- ✅ Right to erasure: candidates can be hard-deleted (not just soft-deleted)
  via `DELETE /candidates/<id>` — index is rebuilt overnight
- ✅ Data portability: export any candidate to JSON in 1 click
- ✅ No cross-border data transfer (local-first)
- ⚠️ Data Processing Agreement (DPA): not yet drafted. Will be provided before any production deployment.
- ⚠️ Formal GDPR compliance review: not yet completed. The architecture is designed to be GDPR-compatible, but compliance is a legal determination that requires review by your legal team.

### CCPA

- ✅ No data sale (we don't sell anything to anyone)
- ✅ No data sharing (no third-party integrations without explicit customer consent)
- ✅ Right to delete: same as GDPR
- ✅ Right to know: candidates can request what data is held

### SOC 2

- 🔄 Type I audit in progress (Q3 2026)
- 🔄 Type II audit planned (Q1 2027)
- ✅ Trust services criteria addressed:
  - Security (encryption, RBAC, audit logging)
  - Availability (99.9% uptime SLA for hosted; for self-hosted, customer SLA)
  - Processing integrity (every search reproducible from query + index)
  - Confidentiality (AES-256 at rest, TLS 1.3 in transit)
  - Privacy (no data sharing, GDPR/CCPA compliant)

### ISO 27001

- 🔄 Planned for 2027

## Data lineage

Every candidate record in RecruitProof carries a lineage trail:

```json
{
  "candidate_id": "cand-00006082",
  "source": "encore_export",
  "import_run_id": "proof_run_001",
  "import_timestamp": "2026-07-15T09:14:22Z",
  "source_file_hash": "sha256:abc123...",
  "extraction_method": "pypdf2",
  "extraction_confidence": 0.97,
  "last_modified_by": "recruiter@yourcompany.com",
  "last_modified_at": "2026-07-15T14:22:11Z",
  "modification_reason": "manual_skill_addition"
}
```

This trail is preserved across migrations, exports, and imports — so you
can always answer "where did this candidate come from?" and "who touched
this record?".

## Penetration testing

- Annual third-party pentest of hosted platform (reports under NDA)
- Customers may pentest their own deployment without notifying Scrutexity
- Bug bounty program planned for 2027

## Audit log access

Auditors have read-only access to:

- All audit logs (full 7-year history)
- All user accounts and role assignments
- All configuration changes (with before/after hashes)
- All import/export operations
- All login attempts (successful and failed)

Auditors do NOT have access to:

- Resume text (would defeat the purpose of hash-logging)
- Candidate scores (reproducible from query + candidate, no need to log)
- Internal embeddings (regenerable from resume text)

## Compliance reporting

RecruitProof generates compliance reports on demand:

- `GET /reports/audit?from=2026-01-01&to=2026-06-30` → CSV of all audit events
- `GET /reports/data_lineage?candidate_id=cand-00006082` → JSON lineage trail
- `GET /reports/gdpr_access?candidate_id=cand-00006082` → JSON of all data held
- `GET /reports/soc2?quarter=2026Q2` → SOC2-aligned quarterly report (PDF)

## Customer responsibilities

RecruitProof provides the tooling. Your team is responsible for:

- Configuring RBAC roles correctly
- Reviewing audit logs periodically (we provide alerts on suspicious activity)
- Managing SSO / MFA enrollment
- Running quarterly restore tests
- Signing the DPA before going live
