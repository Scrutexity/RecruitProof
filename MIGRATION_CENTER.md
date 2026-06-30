# Migration Center

## The problem

Every ATS replacement project dies because of migration risk.

CEOs don't block on price. They block on:

> *"What if the migration breaks our recruiting process for 3 months?"*
> *"What if we lose candidate data?"*
> *"What if the new system doesn't match what recruiters are used to?"*

## The solution

RecruitProof Migration Center gives you complete confidence.

A 6-phase pipeline that runs **alongside your current ATS** with zero downtime,
read-only connectors, preview-before-import, and one-click rollback.

---

## Phase 1: Connect

- Read-only connector to Encore (we never write)
- Test connection — verifies credentials + permissions
- Preview available fields from Encore
- Map Encore fields → RecruitProof schema (auto-mapped, manually adjustable)

**Time:** 30 minutes
**Risk:** Zero — read-only

---

## Phase 2: Validate

- Schema validation (every field type-checked)
- Duplicate detection (email + name + phone heuristics)
- Data quality report (missing fields, malformed entries)
- Missing-field warnings (which Encore fields aren't mapped)

**Time:** 1 hour (for 500K resumes)
**Output:** Validation report (PDF + CSV)

---

## Phase 3: Preview

- See exactly what will be imported
- Sample 100 candidates randomly
- Side-by-side comparison: Encore view vs. RecruitProof view
- Full report of changes ("47 fields added, 0 fields removed, 12 fields remapped")

**Time:** 30 minutes
**Output:** Preview report

---

## Phase 4: Dry Run

- Full import to temporary storage (not production)
- Validate against 5 real searches
- Compare results with your existing Encore searches
- No production impact — your current ATS keeps running

**Time:** 2 hours (for 500K resumes)
**Output:** Dry-run report with search-by-search comparison

---

## Phase 5: Production Import

- One-click final import
- Incremental sync options (hourly / daily delta updates from Encore)
- Rollback capability (revert to pre-import state in < 5 minutes)
- Import verification (every record checksum-verified)

**Time:** 1 hour (for 500K resumes)
**Output:** Completion certificate

---

## Phase 6: Go-Live

- Switch over in 15 minutes
- Run alongside Encore for 30 days (parallel mode)
- Gradual rollout per team (Team A week 1, Team B week 2, etc.)
- Zero downtime — Encore stays live as fallback

**Time:** 15 minutes (cutover) + 30 days (parallel mode)
**Output:** Go-live certificate + 30-day parallel-mode report

---

## Migration Status Dashboard

```
Migration Status: Encore → RecruitProof

✅ Phase 1: Connected (read-only)              30 min
✅ Phase 2: Schema Validated                   1 hr
✅ Phase 3: Preview Generated                  30 min
⏳ Phase 4: Dry Run in Progress                2 hr
   └─ 234,712 / 500,000 candidates processed (47%)
   └─ ETA: 1 hr 8 min remaining
   └─ Throughput: 4,200 candidates/min
⬜ Phase 5: Production Import Ready
⬜ Phase 6: Go-Live

[ Review Dry Run Results ]    [ Pause ]    [ Rollback ]
```

---

## Why Migration Confidence Wins Deals

- **Risk reduction** — no surprises, preview everything
- **Transparency** — see exactly what will change before it changes
- **Speed** — move in days, not months
- **Trust** — read-only connectors, previews, rollbacks
- **Parallel mode** — never take down your current ATS

> We don't just help you switch. We make switching safe.

---

## Rollback guarantee

At any point during phases 4–6, you can click **Rollback** and RecruitProof
will:

1. Stop the current operation
2. Revert the production index to the pre-import checkpoint
3. Restore the candidate database to its pre-migration state
4. Generate a rollback report (what was reverted, when, by whom)

Rollback takes **less than 5 minutes** regardless of database size.

---

## Completion certificate

After Phase 5, RecruitProof generates a signed completion certificate:

```
RecruitProof Migration Completion Certificate
==============================================
Customer:        [Your Company]
Source ATS:      Encore
Records migrated: 487,420 of 500,000 (97.5% success)
Failed records:  12,580 (see failed-records.csv)
Started:         2026-07-15 09:00 UTC
Completed:       2026-07-15 11:47 UTC
Duration:        2 hours 47 minutes
Validation:      All records checksum-verified
Rollback point:  2026-07-15 08:59 UTC (pre-import)

Signed: RecruitProof Migration Engine v0.3.0
Verified by: [Your CTO / IT Lead]
```

This certificate is auditable and satisfies most enterprise compliance
requirements (SOC2, ISO 27001 change-management controls).

---

## See also

- [ENCORE_MIGRATION.md](ENCORE_MIGRATION.md) — Encore-specific migration details
- [AUDIT_AND_COMPLIANCE.md](AUDIT_AND_COMPLIANCE.md) — Compliance documentation
- [SECURITY.md](SECURITY.md) — Security architecture
