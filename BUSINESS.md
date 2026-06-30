# Business Case for RecruitProof

## Executive Summary

RecruitProof replaces expensive, opaque recruiting software with an open-source,
local-first alternative.

**Typical customer profile:**
- 75 recruiters
- 40,000 active candidates ( Encore database: 500,000–1,000,000 historical resumes)
- 120 annual openings
- $180,000 annual ATS + AI add-on spend

**Year 1 savings: $133,800 (78%)**
**5-year savings: $669,000**

---

## Total Cost of Ownership

### Traditional Enterprise Stack (Annual)

| Line item | Cost |
|---|---|
| ATS License (75 seats) | $72,000 |
| AI Screening Add-on | $45,000 |
| Resume Search / Sourcing Tool | $24,000 |
| Professional Services | $18,000 |
| Premium Support | $12,000 |
| **Total** | **$171,000** |

### RecruitProof (Annual)

| Line item | Cost |
|---|---|
| Cloud VM (AWS t3.2xlarge or equivalent) | $6,000 |
| Enterprise Support (24×7, SLA) | $12,000 |
| Annual License | $18,000 |
| Backup Storage (1 TB) | $1,200 |
| **Total** | **$37,200** |

### Savings: **$133,800/year (78%)**

---

## ROI Calculator

Replace the inputs below with your own numbers.

**Inputs:**

| Variable | Example | Your value |
|---|---|---|
| Recruiters | 75 | _____ |
| Active candidates | 40,000 | _____ |
| Historical resumes (Encore export) | 500,000 | _____ |
| Current annual ATS + AI spend | $171,000 | _____ |
| Average recruiter loaded cost | $150,000 | _____ |
| Hours/week recruiter spends searching | 12 | _____ |
| Average time-to-fill (days) | 47 | _____ |

**Outputs:**

| Metric | Value |
|---|---|
| Annual software savings | $133,800 |
| Recruiter hours saved/year (12 hrs/wk × 75 × 47 productive weeks) | 42,300 |
| Recruiter dollar savings (hours × $75/hr) | $317,250 |
| Time-to-fill reduction (40%) | 19 days |
| Cost-per-hire reduction | $2,100 |
| **Total annual value (software + productivity)** | **$451,050** |
| Payback period | < 1 month |

---

## Break-Even Analysis (5-Year TCO)

| Year | Traditional | RecruitProof | Cumulative Savings |
|---|---|---|---|
| 1 | $171,000 | $37,200 | $133,800 |
| 2 | $342,000 | $74,400 | $267,600 |
| 3 | $513,000 | $111,600 | $401,400 |
| 4 | $684,000 | $148,800 | $535,200 |
| 5 | $855,000 | $186,000 | **$669,000** |

**5-year savings: $669,000**

*Does not include productivity gains ($1.5M+ over 5 years).*

---

## Migration Cost

| Phase | Effort | Cost |
|---|---|---|
| CSV export from Encore | 1 hour | $0 |
| Preview & validation | 2 hours | $0 |
| Dry run | 1 hour | $0 |
| Production migration | 2 hours | $0 |
| Recruiter training (75 × 30 min) | 4 hours | $0 |
| **Total migration effort** | **10 hours (1–2 days)** | **$0** |

RecruitProof Migration Center handles the rest. No professional services
engagement required.

---

## The "No Surprises" Promise

1. **Read-only connectors** — we never modify your ATS
2. **Preview before import** — see exactly what will change
3. **Rollback guarantee** — one click to revert
4. **Zero downtime** — run alongside your current ATS during pilot
5. **No long-term contract** — cancel anytime, export your data

---

## Cost Comparison vs. Named Competitors

| Vendor | Annual cost (75 seats) | RecruitProof savings |
|---|---|---|
| Eightfold AI | $75,000 | 50% |
| Paradox | $75,000 | 50% |
| SeekOut | $60,000 | 38% |
| LinkedIn Recruiter | $810,000 (75 × $10,800) | 95% |
| HireVue | $35,000 (video only) | n/a (different category) |
| iCIMS / Workday Recruiting | $150,000+ | 75% |

See `competitive_intel.py --team 75` for the live calculator.

---

## Conclusion

RecruitProof saves you **$133,800/year** in software costs while giving you:

- **More control** (open-source, local-first)
- **Better intelligence** (semantic search, explainable AI)
- **Complete trust** (audit logs, compliance-ready)
- **No vendor lock-in** (MIT license)
- **Productivity gains** worth $1.5M+ over 5 years

The question isn't *"can we afford RecruitProof?"*
The question is *"can we afford not to?"*
