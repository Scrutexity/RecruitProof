# RecruitProof

## Enterprise Recruiting Infrastructure

**Replace your recruiting software — not your recruiting process.**

---

## 1. What problem does this solve?

Your ATS costs $180,000/year. Your recruiters still spend hours searching.
Your data is locked in vendor prisons. Your AI tools don't explain themselves.

RecruitProof gives you:

- **Sub-5ms search** across 1M+ profiles
- **Explainable scores** for every candidate
- **Local-first deployment** — your data never leaves your network
- **90% cost savings** vs. enterprise vendors
- **Read-only ATS connectors** — we never modify your Encore data

---

## 2. Why should I switch?

| Current | RecruitProof |
|---------|--------------|
| $180,000/year | $18,000/year |
| Cloud-only | Local-first |
| Black-box AI | Explainable scores |
| Vendor lock-in | Open-source core |
| 5-second searches | 5-millisecond searches |
| Manual migration risk | 6-phase zero-risk migration |

---

## 3. How much money do I save?

See [BUSINESS.md](BUSINESS.md) for the full TCO analysis.

**Quick math for a 75-recruiter team:**

| Item | Traditional | RecruitProof |
|------|-------------|--------------|
| ATS License | $72,000 | $0 |
| AI Add-ons | $45,000 | $0 |
| Seat Licenses | $36,000 | $0 |
| Cloud VM | $0 | $6,000 |
| Enterprise License | $0 | $18,000 |
| **Total** | **$153,000** | **$24,000** |
| **Year 1 Savings** | | **$129,000 (84%)** |

---

## 4. Can I trust it?

- **Open-source core** — audit every line
- **Local-first** — your data never leaves your network
- **Explainable scoring** — every rank comes with a reason
- **Audit logging** — every search is recorded
- **Read-only ATS connectors** — we never modify your data
- **One-click rollback** — revert any migration in seconds

See [SECURITY.md](SECURITY.md) and [AUDIT_AND_COMPLIANCE.md](AUDIT_AND_COMPLIANCE.md).

---

## 5. How fast can I deploy it?

**Phase 1 Pilot: 24 hours.** No ATS replacement. No Encore integration.
Drop a zipped folder of PDF/DOCX resumes, get a shortlist and ROI report.
See [PILOT.md](PILOT.md).

**Phase 2 Production: 15 minutes.** Once the pilot proves value.

```bash
git clone https://github.com/Scrutexity/RecruitProof
cd RecruitProof
docker-compose up -d
# Open http://localhost:8000
```

See [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Proof target

RecruitProof is designed to scan **500,000–1,000,000 exported Encore resumes**
from PDF/DOCX files without requiring direct ATS access.

**Phase 1 proof does not replace Encore.** It creates a private searchable
intelligence layer over exported CVs.

For Rudy, the demo is:

> "Give me 1 zipped folder. I'll return 50 hidden candidates."

Not:

> "Let's integrate Encore."

See [proof/million_cv_scan/](proof/million_cv_scan/) for the benchmark plan
and sample report.

---

## Repository structure

| Document | Audience | Purpose |
|---|---|---|
| [README.md](README.md) | CEO / CFO | 5 questions, sales-first |
| [BUSINESS.md](BUSINESS.md) | CFO | TCO, ROI, 5-year savings |
| [PILOT.md](PILOT.md) | CEO | Risk-free pilot offer |
| [RUDY_PILOT_ONE_PAGER.md](RUDY_PILOT_ONE_PAGER.md) | CEO | Single-page exec summary |
| [MIGRATION_CENTER.md](MIGRATION_CENTER.md) | CTO / Ops | 6-phase zero-risk migration |
| [ENCORE_MIGRATION.md](ENCORE_MIGRATION.md) | CTO / Ops | Encore-specific migration |
| [DEPLOYMENT.md](DEPLOYMENT.md) | DevOps | 15-min setup guide |
| [SECURITY.md](SECURITY.md) | CISO | Encryption, auth, data ownership |
| [SECURITY_BRIEF.md](SECURITY_BRIEF.md) | CEO / CISO | 1-page security brief |
| [AUDIT_AND_COMPLIANCE.md](AUDIT_AND_COMPLIANCE.md) | Compliance | GDPR, CCPA, SOC2 roadmap |
| [PERFORMANCE.md](PERFORMANCE.md) | Engineering | Benchmarks (p50, p99, 1M profiles) |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Engineering | Encore, Workday, Greenhouse, Lever |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Engineering | Technical architecture |
| [SAMPLE_OUTPUT.md](SAMPLE_OUTPUT.md) | CEO / Recruiter | What the shortlist looks like |
| [ROADMAP.md](ROADMAP.md) | All | What's coming |
| [proof/million_cv_scan/](proof/million_cv_scan/) | CEO | The killer proof artifact |

---

## License

MIT — you own your data, your infrastructure, and your future.

---

## Repository

- **Source:** https://github.com/Scrutexity/RecruitProof
- **Issues:** https://github.com/Scrutexity/RecruitProof/issues
- **License:** MIT (open-source friendly — fork, extend, self-host)

RecruitProof is the open-source core of the Scrutexity platform. Enterprise
support, hosted deployments, and custom ATS connectors are available
commercially; the core search engine, agentic pipeline, and competitive
intelligence modules will always remain MIT-licensed.
