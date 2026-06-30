# Encore Migration

## Migration philosophy

**Encore stays live throughout the migration.** RecruitProof runs alongside
it in parallel mode. Zero downtime, zero risk.

Your recruiters keep using Encore for active reqs. RecruitProof handles the
search intelligence layer. Cutover happens only when your team is ready.

## Phase 1 — Pilot (24 hours)

**Goal:** Prove RecruitProof can search your Encore resume database.

**What you do:**
1. Export 5,000–50,000 resumes from Encore as a zipped folder of PDF/DOCX files
2. Send us the zip + 3 job descriptions
3. We return shortlists + ROI report within 24 hours

**What we do:**
1. Ingest the zip (parse, dedup, extract text)
2. Build a hybrid FAISS + BM25 index
3. Run 3 searches, generate shortlists
4. Generate the Million-CV Proof Report
5. Delete your raw files (deletion certificate provided)

**Encore impact:** Zero. Encore is not touched.

**Time:** 24 hours elapsed, 45 minutes of your team's time.

---

## Phase 2 — Read-only API connector (1 week)

**Goal:** RecruitProof automatically syncs new Encore resumes every 24 hours.

**What you do:**
1. Create an Encore API key with read-only scope
2. Provide the key + Encore base URL to RecruitProof
3. Approve the field mapping (Encore field → RecruitProof field)

**What we do:**
1. Configure the Encore connector (read-only)
2. Run initial full sync (all active candidates)
3. Schedule 24-hour delta sync
4. Validate: every Encore candidate appears in RecruitProof

**Encore impact:** Zero. Read-only connector, we never write.

**Time:** 1 week (mostly your IT team's approval cycle).

---

## Phase 3 — Parallel mode (30 days)

**Goal:** Recruiters use RecruitProof for search, Encore for tracking.

**What you do:**
1. Train recruiters (30 min each)
2. Recruiters search in RecruitProof, track in Encore
3. Weekly review: are recruiters finding better candidates faster?

**What we do:**
1. Provide recruiter training
2. Monitor usage + audit logs
3. Weekly check-in with the recruiting lead
4. Tune scoring weights based on recruiter feedback

**Encore impact:** Zero. Encore continues to be the system of record.

**Time:** 30 days.

**Exit criteria:**
- ≥ 80% of recruiters actively using RecruitProof weekly
- Recruiter-reported time-to-shortlist reduced by ≥ 50%
- At least 1 "hidden candidate" surfaced that was hired

---

## Phase 4 — Cutover (1 day)

**Goal:** RecruitProof becomes the primary search tool. Encore remains as
fallback.

**What you do:**
1. Decide: cutover or extend parallel mode?
2. If cutover: redirect the search bookmark from Encore to RecruitProof
3. Keep Encore live for 90 days as fallback

**What we do:**
1. Generate the cutover checklist
2. Send the go-live certificate
3. Schedule the 30-day post-cutover review

**Encore impact:** Zero — Encore stays live.

**Time:** 1 day.

---

## Phase 5 — Encore decommission (optional, 90+ days later)

**Goal:** Turn off Encore if you're confident.

**What you do:**
1. Export Encore data one final time (backup)
2. Decommission Encore
3. Save the Encore backup in cold storage for compliance

**What we do:**
1. Generate the decommission certificate
2. Confirm RecruitProof is the system of record

**Encore impact:** Encore is turned off.

**Time:** 1 day.

---

## Rollback

At any phase, you can roll back:

| Phase | Rollback action | Time |
|---|---|---|
| 1 (Pilot) | Delete RecruitProof data | 5 min |
| 2 (Connector) | Revoke API key, delete RecruitProof data | 15 min |
| 3 (Parallel) | Redirect bookmark back to Encore | 5 min |
| 4 (Cutover) | Redirect bookmark back to Encore | 5 min |
| 5 (Decommission) | Restore Encore from backup | 1-4 hours |

**Rollback is always possible. RecruitProof never deletes or modifies Encore.**

---

## Field mapping (Encore → RecruitProof)

Default mapping (editable in Phase 2):

| Encore field | RecruitProof field | Notes |
|---|---|---|
| `candidate_id` | `id` | Direct |
| `first_name` + `last_name` | `name` | Concatenated |
| `email` | `email` | Direct |
| `phone` | `phone` | Direct |
| `current_title` | `current_title` | Direct |
| `employer` | `current_company` | Direct |
| `location` | `location` | Direct |
| `resume_file` | (ingested as text) | PDF/DOCX path |
| `skills` | `skills` | Pipe-separated |
| `years_experience` | `years_experience` | Integer |
| `last_activity_date` | `last_active_days_ago` | Computed |
| `tags` | `tags` | Direct |
| `application_status` | (ignored) | RecruitProof doesn't track applications |
| `recruiter_notes` | (ignored) | Out of scope — stays in Encore |
| `eeo_data` | (ignored + stripped) | We don't want EEO data |

---

## What we DON'T migrate

- ❌ Recruiter notes (stay in Encore)
- ❌ Application history (stays in Encore)
- ❌ EEO data (we don't want it)
- ❌ Salary data (we don't want it)
- ❌ Interview feedback (stays in Encore)
- ❌ Offer history (stays in Encore)

RecruitProof is a search intelligence layer, not an ATS replacement. Encore
remains the system of record for everything except search.

---

## FAQ

**Q: Do we have to replace Encore?**
A: No. RecruitProof runs alongside Encore indefinitely. Many customers never decommission Encore.

**Q: What if Encore changes their API?**
A: RecruitProof's connector is versioned. We adapt within 2 weeks of any Encore API change. Your data stays safe.

**Q: Can we keep Encore as our system of record forever?**
A: Yes. Many customers do. RecruitProof is the search layer; Encore is the workflow layer.

**Q: How long does the full migration take?**
A: Pilot: 24 hours. Production: 1 week. Full cutover: 30+ days (your pace).

**Q: What's the riskiest step?**
A: None. Every step is reversible. The most common "issue" is recruiters preferring RecruitProof so much they stop using Encore — which is the goal.
