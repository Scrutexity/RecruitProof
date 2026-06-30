# Integrations

## Read-only by default

All RecruitProof integrations are **read-only by default**. We never modify
your source systems without explicit per-action approval.

## Encore

| Capability | Status | Notes |
|---|---|---|
| Resume export (PDF/DOCX zip) | ✅ Production | Primary ingestion path for pilots |
| Field-level export (CSV) | ✅ Production | Enriches index with structured metadata |
| Read-only API connector | 🔄 Phase 2 | Scheduled for Q3 2026 |
| Write-back (status sync) | 🚫 Not planned | We don't modify Encore |

**Pilot path (zero integration):**
1. Export resumes from Encore as a zipped folder
2. Drop the zip into `/imports/encore/`
3. RecruitProof handles the rest

**Production path (read-only API):**
1. Provide Encore API credentials (read-only scope)
2. RecruitProof syncs every 24 hours
3. New resumes in Encore appear in RecruitProof within 24 hours
4. Encore is never modified

## Workday

| Capability | Status | Notes |
|---|---|---|
| Resume export (PDF/DOCX) | ✅ Production | Same pipeline as Encore |
| Read-only API connector | 🔄 Phase 2 | Workday SOAP API (notorious complexity) |
| Form autofill (apply mode) | 🚫 Not planned | Out of scope — we're a search platform |

## Greenhouse

| Capability | Status | Notes |
|---|---|---|
| Resume export | ✅ Production | Via Harvest API |
| Read-only API connector | ✅ Production | Greenhouse Harvest API (REST, well-documented) |
| Job sync (Greenhouse → RecruitProof) | ✅ Production | Pulls active jobs every hour |
| Application sync (RecruitProof → Greenhouse) | 🚫 Not planned | Use Greenhouse's own UI for applying |

## Lever

| Capability | Status | Notes |
|---|---|---|
| Resume export | ✅ Production | Via Lever API |
| Read-only API connector | ✅ Production | Lever REST API |
| Job sync | ✅ Production | Pulls posted jobs every hour |

## Ashby

| Capability | Status | Notes |
|---|---|---|
| Resume export | ✅ Production | Via Ashby API |
| Read-only API connector | ✅ Production | Ashby GraphQL API |
| Job sync | ✅ Production | Pulls active jobs every hour |

## SmartRecruiters

| Capability | Status | Notes |
|---|---|---|
| Resume export | ✅ Production | Via SR API |
| Read-only API connector | 🔄 Phase 2 | Scheduled Q4 2026 |

## LinkedIn Recruiter

| Capability | Status | Notes |
|---|---|---|
| Resume export | ❌ Not supported | LinkedIn TOS prohibits bulk export |
| API connector | ❌ Not supported | LinkedIn TOS prohibits automated scraping |
| Manual import (single resume) | ✅ Production | Paste a LinkedIn URL, we'll fetch the public profile |

*We respect LinkedIn's TOS. If you have a LinkedIn Recruiter license, you can
manually export individual profiles and RecruitProof will index them.*

## Slack

| Capability | Status | Notes |
|---|---|---|
| Daily shortlist digest | ✅ Production | Posts top 5 new candidates per JD to a Slack channel |
| New hidden-candidate alert | ✅ Production | When RecruitProof finds a candidate not in your Encore shortlist |
| Manual search via slash command | 🔄 Phase 2 | `/recruitproof search senior backend engineer` |

## Microsoft Teams

| Capability | Status | Notes |
|---|---|---|
| Daily shortlist digest | 🔄 Phase 2 | Same as Slack |
| Manual search | 🔄 Phase 2 | |

## Email

| Capability | Status | Notes |
|---|---|---|
| Daily digest | ✅ Production | Plain-text email with top 5 candidates per JD |
| Outreach generation | ✅ Production | Per-candidate outreach email draft |

## API (for custom integrations)

RecruitProof exposes a REST API (read-only by default):

```
GET  /api/v1/search?q=<jd>&top=100
GET  /api/v1/candidates/<id>
GET  /api/v1/candidates/<id>/explain
GET  /api/v1/shortlists
POST /api/v1/shortlists  (create a shortlist from a search)
GET  /api/v1/audit?from=...&to=...
GET  /api/v1/health
```

API key auth, rate-limited to 100 req/sec per key. OpenAPI spec at
`/api/v1/openapi.json`.

## Custom integrations

Need an integration we don't list? Email integrations@scrutexity.com.
We add new ATS integrations in 2–4 weeks for enterprise customers.
