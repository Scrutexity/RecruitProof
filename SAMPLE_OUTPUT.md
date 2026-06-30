# Sample Output

## What a RecruitProof shortlist looks like

This is the actual output format your recruiters receive when they run a
search in RecruitProof. Below is a sample for a Senior Backend Engineer, Payments role.

---

### Top 10 candidates

```
═══════════════════════════════════════════════════════════════════════════════
  RecruitProof — Enterprise Candidate Intelligence
═══════════════════════════════════════════════════════════════════════════════

┌─ PARSED JOB DESCRIPTION ────────────────────────────────────────────────────
│ Title:      Senior Backend Engineer, Payments
│ Seniority:  senior
│ Required:   go, graphql, aws, kubernetes, kafka, postgresql, distributed systems
│ Nice-to-have: open source
│ Constraints: loc: Remote (US)  remote-ok  visa-sponsor
└─────────────────────────────────────────────────────────────────────────────

  PARSE  4ms  FAISS  18ms  RANK 89ms  TOTAL 2.8 sec

  Top 10 Candidates
  ────────────────────────────────────────────────────────────────────────────

 ①  ━━━━━━━━━━  9.2/10  Maya Chen              Senior Backend Engineer
         @ Stripe  ·  8y  ·  Remote (US)
         SEM 0.91  ROL 0.85  SKL 0.95  BEH 0.90  CAR 0.80
         ✓ go, postgresql, kafka, kubernetes, aws, distributed systems
         ✗ graphql
         → Top pick: strong semantic match, 8 years at Stripe in payments, covers 6/7 required skills.

 ②  ━━━━━━━━━░  8.7/10  Daniel Okonkwo          Backend Engineer
         @ Plaid  ·  7y  ·  New York, NY
         ✓ go, postgresql, kubernetes, aws, distributed systems
         ✗ graphql, kafka
         → Strong backend + payments domain experience (Plaid). Missing kafka — ramp in 30 days.

 ③  ━━━━━━━━━░  8.4/10  Priya Nair              Staff Backend Engineer
         @ Square  ·  11y  ·  Remote (US)
         ✓ go, postgresql, kafka, kubernetes, aws, distributed systems, graphql
         ✗ (none — full coverage)
         → Full skills coverage, 11 years, staff-level. Slightly senior for the role.

  4  ━━━━━━━━░░  7.9/10  Lukas Müller            Senior Backend Engineer
         @ Coinbase  ·  9y  ·  Remote (US)
         ✓ go, postgresql, kafka, kubernetes, aws
         ✗ graphql, distributed systems
         → Strong payments background (Coinbase). Missing graphql — assess in screen.

  5  ━━━━━━━━░░  7.7/10  Sofia Vargas            Backend Engineer
         @ Plaid  ·  6y  ·  Remote (US)
         ✓ go, postgresql, kafka, kubernetes, aws, graphql
         ✗ distributed systems
         → 6 years at Plaid, full skills except distributed systems. Fast-tracked candidate.

  ...

═══════════════════════════════════════════════════════════════════════════════
  TOP MATCH: Maya Chen — 9.2/10
  WHY NOT 10/10: missing graphql (likely ramp-up < 1 week given Go expertise)
  REASONING: Maya Chen — 9.2/10 — Top pick: strong semantic match, 8 years at
             Stripe in payments, covers 6/7 required skills.
═══════════════════════════════════════════════════════════════════════════════
```

---

### Candidate Intelligence Page (Maya Chen)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║  CANDIDATE INTELLIGENCE — Maya Chen                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  Candidate: Maya Chen  (cand-00006082)
  Title:     Senior Backend Engineer @ Stripe
  YoE:       8  Location: Remote (US)

  JD target:  Senior Backend Engineer, Payments  (senior)

  Signal breakdown
  ────────────────────────────────────────────────────────────────────────────
  Signal           Value  Bar                     Weight    Contribution
  ────────────────────────────────────────────────────────────────────────────
  SEM              0.913  ━━━━━━━━━━━━━━━━━━━──      40%          3.65/10
  ROL              0.852  ━━━━━━━━━━━━━━━━━───      20%          1.70/10
  SKL              0.950  ━━━━━━━━━━━━━━━━━━━      15%          1.43/10
  BEH              0.902  ━━━━━━━━━━━━━━━━━──      15%          1.35/10
  CAR              0.800  ━━━━━━━━━━━━━━━━━──      10%          0.80/10
  ────────────────────────────────────────────────────────────────────────────
  FINAL                                                          9.20/10

  Skills analysis
  ────────────────────────────────────────────────────────────────────────────
  ✓ Matched:  go, postgresql, kafka, kubernetes, aws, distributed systems
  ✗ Missing:  graphql

  Career progression
  ────────────────────────────────────────────────────────────────────────────
  2018  Backend Engineer @ Square
  2020  Senior Backend Engineer @ Stripe       (promotion)
  2022  Tech Lead, Payments @ Stripe           (promotion)
  2024  Senior Staff Engineer @ Stripe         (promotion)
  → 3 promotions in 6 years — high velocity

  Availability indicators
  ────────────────────────────────────────────────────────────────────────────
  • Last active: 3 days ago
  • Response rate: 87% (high)
  • Open to remote: yes
  • Previously applied to your company: yes (warm lead)
  • LinkedIn signal: profile updated 2 weeks ago (actively looking)

  Similar candidates (also in your database)
  ────────────────────────────────────────────────────────────────────────────
  • Daniel Okonkwo (8.7/10) — Plaid, payments, similar skill set
  • Lukas Müller (7.9/10) — Coinbase, payments, slightly less senior
  • Aiko Yamamoto (7.4/10) — Square, payments, missing kubernetes

  Suggested outreach
  ────────────────────────────────────────────────────────────────────────────
  Subject: Senior Backend Engineer, Payments — your Stripe experience caught our eye

  Hi Maya,

  Your 8 years at Stripe building payments infrastructure — particularly your
  work on idempotency and fraud detection — aligns directly with what we're
  building. We're looking for a senior backend engineer to own our payments
  platform; you'd be a natural fit.

  Would you be open to a 30-minute conversation this week?

  Best,
  [Recruiter name]
```

---

### Export formats

Every shortlist can be exported as:

| Format | Use case |
|---|---|
| CSV | Spreadsheet import (Excel, Google Sheets) |
| JSON | API integration |
| PDF | Executive review, printable |
| Encore import CSV | Re-import into Encore as a shortlist |

---

### What your CEO sees

The Executive Dashboard shows:

- Total candidates searched: 1,247,832
- Time to first shortlist: 2.8 seconds
- Hidden candidates surfaced: 47 (12 rated ≥ 4 by recruiters)
- Estimated cost savings: $133,800/year
- Recruiter hours saved this quarter: 1,247

That's what makes the CEO approve a pilot.

---

### The "50 Hidden Candidates" deliverable

When you send Rudy the pilot deliverable, this is what he receives — a
one-page PDF (or CSV) listing the 50 highest-fit candidates that RecruitProof
surfaced from his Encore archive that his team had NOT previously shortlisted.

```
═══════════════════════════════════════════════════════════════════════════════
  RecruitProof — 50 Hidden Candidates
  Customer: [Pilot Customer]  ·  Run: proof_run_001  ·  2026-07-15
  Source: 500,000 Encore-exported resumes  ·  Search: Senior Backend Engineer, Payments
═══════════════════════════════════════════════════════════════════════════════

  #    Name                  Title                          Company       Score  Status
  ───  ────────────────────  ─────────────────────────────  ────────────  ─────  ──────────────
   1   Maya Chen             Senior Backend Engineer        Stripe         9.2   NEW
   2   Daniel Okonkwo        Backend Engineer               Plaid          8.7   NEW
   3   Priya Nair            Staff Backend Engineer         Square         8.4   NEW
   4   Lukas Müller          Senior Backend Engineer        Coinbase       7.9   NEW
   5   Sofia Vargas          Backend Engineer               Plaid          7.7   NEW
   6   Jamal Fernández       Senior Backend Engineer        Planetscale    7.5   NEW
   7   Aiko Tanaka           Backend Engineer               Vercel         7.3   NEW
   8   Henrik Andersen       Senior Backend Engineer        Datadog        7.1   NEW
   9   Ananya Reddy          Staff Engineer                 Anthropic      6.9   NEW
  10   Diego Fernández       Backend Engineer               Twilio         6.7   NEW
  ...
  47   Lena Souza            Senior Backend Engineer        Netflix        6.1   NEW

═══════════════════════════════════════════════════════════════════════════════
  SUMMARY
═══════════════════════════════════════════════════════════════════════════════

  • 50 candidates surfaced that were NOT in your active Encore shortlists
  • 12 of 50 rated ≥ 4/5 by all 3 senior recruiters on your review panel
  • Top candidate (Maya Chen, 9.2/10) is a warm lead — previously applied
    to your company 14 months ago
  • 8 of 50 candidates have payments-domain experience (Stripe, Plaid,
    Coinbase, Square) — directly relevant to the role
  • Average search time across 3 JDs: 2.8 seconds (warm: 92ms p50)

  NEXT STEPS:
  1. Review the 12 recruiter-approved candidates (see hidden_candidates.csv)
  2. Approve outreach for the top 5 (drafts included in the deliverable ZIP)
  3. Schedule follow-up call to discuss Phase 2 (production deployment)

═══════════════════════════════════════════════════════════════════════════════
  Raw files deleted: 500,000 / 500,000 (100%)
  Deletion receipt: RCPT-2026-0716-001
  This report contains no PII beyond candidate names (already in your Encore).
═══════════════════════════════════════════════════════════════════════════════
```

**Deliverable ZIP contents:**

```
recruitproof_pilot_deliverable.zip
├── 50_hidden_candidates.pdf          ← the one-pager above
├── 50_hidden_candidates.csv          ← spreadsheet import (Excel/Sheets)
├── 50_hidden_candidates.json         ← API integration
├── outreach_drafts/
│   ├── 01_maya_chen.txt
│   ├── 02_daniel_okonkwo.txt
│   └── ... (top 5 only — personalized AI-drafted emails)
├── recruiter_review_panel.csv        ← 3-recruiter ratings for each candidate
├── proof_run_001_report.pdf          ← the full Million-CV Proof Report
├── roi_snapshot.pdf                  ← 1-page ROI calculation
└── deletion_receipt.pdf          ← proof that raw files were deleted
```

This is what Rudy holds in his hand. Every candidate is real (from his Encore
export). Every score is explainable. Every "NEW" status means his team hadn't
previously found this person. That's the pilot deliverable.
