# Data Handling Agreement — RecruitProof Pilot

**Version:** 1.0 (template — not yet executed)
**Date:** [Effective Date — to be set upon execution]
**Between:** Scrutexity ("Processor") and [Customer Name] ("Controller")

---

## 1. Purpose

This agreement governs the processing of candidate resume data ("Personal Data")
by RecruitProof during the pilot program. The Controller provides a ZIP archive
of PDF/DOCX resumes; the Processor runs RecruitProof locally to produce a
ranked shortlist and evidence packet.

## 2. Data Processing Scope

**What is processed:**
- PDF and DOCX resume files containing candidate names, contact information,
  employment history, skills, and education.

**What is NOT processed:**
- EEO data (race, gender, veteran status) — stripped if detected
- Salary history — not collected
- Background check results — not collected
- Medical or disability information — not collected
- Immigration status beyond "requires sponsorship: yes/no" — not collected

## 3. Data Location

**Option A — Processor-local:**
- Data is processed on the Processor's local machine in [Processor's jurisdiction — to be specified upon execution].
- No data is uploaded to any cloud service.
- No data is transmitted to any third party.
- Raw files are deleted within 24 hours of pilot delivery.

**Option B — Controller-local (recommended):**
- Data is processed on the Controller's infrastructure via a Docker container.
- The Processor never receives, accesses, or stores the data.
- The Controller deletes the Docker image and all outputs when done.

## 4. No AI Vendor Data Sharing

The Processor confirms that:
- No candidate data is sent to OpenAI, Anthropic, Google, or any other AI vendor.
- No candidate data is used to train any model.
- All scoring and reasoning is generated locally via deterministic, template-based
  logic (no LLM calls are made unless the Controller explicitly enables them by
  setting an API key — which is not required for the pilot).

## 5. Data Retention and Deletion

- Raw resume files (PDF/DOCX) are deleted within 24 hours of pilot delivery.
- A deletion receipt (PDF + JSON) is generated and provided to the Controller,
  including SHA-256 hashes of all deleted files.
- The only retained artifacts are: the ranked shortlist (CSV/PDF), the proof
  report, and the audit ledger — none of which contain raw resume text beyond
  candidate names and extracted skills.
- The Controller may request immediate deletion at any time.

## 6. Security Measures

- All processing runs locally (no cloud, no external API calls).
- Backups (if any) are encrypted with Fernet (AES-128-CBC + HMAC-SHA256).
- Audit logs are hash-chained and tamper-evident.
- The Processor's machine is password-protected and encrypted at the disk level.

## 7. Controller Rights

The Controller may:
- Request a copy of all data processed during the pilot.
- Request immediate deletion of all data at any time.
- Audit the RecruitProof source code (MIT-licensed, available at
  https://github.com/Scrutexity/RecruitProof).
- Choose Option B (Controller-local processing) to ensure the Processor never
  touches the data.

## 8. Processor Obligations

The Processor will:
- Process Personal Data only for the purpose of generating the pilot shortlist.
- Not share, sell, or transfer Personal Data to any third party.
- Not use Personal Data for any purpose other than the pilot.
- Delete all raw files within 24 hours and provide a deletion receipt.
- Notify the Controller within 24 hours of any security incident.

## 9. Liability

- The Processor's liability is limited to the pilot fee (if any).
- The Processor is not liable for candidate data that was already in the
  Controller's Encore archive prior to the pilot.
- The Processor carries no insurance specific to this pilot. For production
  deployments, cyber liability insurance will be obtained.

## 10. Term

This agreement is effective from the date the Controller sends the ZIP file
and expires 30 days after pilot delivery, at which point all retained artifacts
(excluding the deletion receipt) will be deleted upon request.

## 11. Governing Law

[To be determined based on the Controller's jurisdiction.]

---

**Signed:**

___________________________
[Processor Name], Scrutexity
Date: ___________

___________________________
[Controller Name], [Customer]
Date: ___________

---

*This is a template. Have your legal team review and modify before signing.*
