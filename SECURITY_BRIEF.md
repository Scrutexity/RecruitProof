# Security Brief — One-Pager

**For:** Executive review
**Date:** 2026-07-15

---

## 🔒 READ-ONLY BY DESIGN

> **RecruitProof never writes to your ATS.**
>
> All Encore, Workday, Greenhouse, and Lever connectors are **read-only**.
> RecruitProof searches your candidate database, surfaces shortlists, and
> generates reports — but it cannot create, modify, or delete any record in
> your production ATS. There is no "write" code path. Your recruiting
> workflow stays untouched.

This is the #1 concern we hear from CISOs: *"Will an AI bot write back to my
production ATS?"* The answer is no. RecruitProof is a search and intelligence
layer, not an ATS replacement. Encore remains your system of record.

---

## RecruitProof security in 60 seconds

- **Read-only ATS connectors.** We never write to Encore, Workday, Greenhouse, or Lever.
- **Local-first.** Your candidate data never leaves your network. No outbound
  traffic during search, ingestion, or indexing.
- **Encrypted.** AES-256-GCM at rest, TLS 1.3 in transit, customer-managed keys.
- **Auditable.** Every search, view, export, and config change is logged with
  user, timestamp, IP. Logs are hash-chained and tamper-evident.
- **Open-source.** Every line of code that touches candidate data is auditable
  on GitHub. No black boxes.
- **RBAC.** Five roles (Admin, Recruiter, Hiring Manager, Auditor, Read-Only).
  SSO via SAML 2.0 (Okta, Azure AD, Google Workspace). MFA supported.
- **No PHI/PII collected beyond resumes.** We explicitly strip EEO, salary,
  background-check, and medical fields if they appear in your export.

## Pilot-specific guarantees (Option A)

- Your data is processed in an isolated VPC, your data only
- Files are deleted within 24 hours of delivery, deletion certificate provided
- We never train models on your data
- We never share your data with any third party
- We never use your data for any purpose other than generating your shortlist

## Pilot-specific guarantees (Option B)

- We ship a Docker image; you run it on your infrastructure
- We never see your data, your network, or your logs
- You delete the image when done; we have no way to verify (which is the point)

## Compliance status

| Framework | Status |
|---|---|
| GDPR | ✅ Compliant |
| CCPA | ✅ Compliant |
| SOC 2 Type I | 🔄 Q3 2026 |
| SOC 2 Type II | 🔄 Q1 2027 |
| ISO 27001 | 🔄 2027 |

## What to ask your CISO

1. *"Will this write to my ATS?"* — **No. Read-only by design. No write code path exists.**
2. *"Can we deploy this on our infrastructure?"* — Yes (Option B).
3. *"Can our security team audit the code?"* — Yes, MIT-licensed, all on GitHub.
4. *"Where does our data go?"* — Nowhere, if you choose Option B. Isolated VPC, deleted in 24 hours if Option A.
5. *"Who has access?"* — Your admins. We don't even have access in Option B.
6. *"What's your breach history?"* — None. We're new. We've also never had a chance to fail yet, and we've designed the system assuming we will be attacked.

## Contact

- Security questions: security@scrutexity.com
- Vulnerability disclosure: security@scrutexity.com (24-hour response)
- Full security docs: [SECURITY.md](SECURITY.md)
