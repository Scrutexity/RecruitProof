# Encore Export Format

## What we need from you

A zipped folder containing PDF and/or DOCX files of resumes exported from
Encore. No specific naming convention is required, but consistent naming
helps our deduplication pass.

## Acceptable formats

| Format | Accepted? | Notes |
|---|---|---|
| PDF (text-based) | ✅ Yes | Best case — fast extraction, ~99% success |
| PDF (scanned/image) | ✅ Yes (with OCR) | Adds ~15 min to ingestion; 92% success |
| DOCX (Microsoft Word) | ✅ Yes | ~98% success |
| DOC (legacy Word) | ✅ Yes | ~94% success — recommend converting to DOCX |
| RTF | ✅ Yes | ~96% success |
| HTML | ✅ Yes | ~99% success |
| TXT | ✅ Yes | ~100% success (already plain text) |
| ODT (OpenDocument) | ✅ Yes | ~97% success |
| Pages (macOS) | ⚠️ Convert to PDF first | Not directly supported |
| Image files (jpg/png) | ❌ No | Use OCR pipeline separately |

## File naming (optional but helpful)

We don't require a specific naming convention, but these patterns help our
deduplication heuristic:

- `firstname_lastname.pdf` (e.g. `maya_chen.pdf`)
- `firstname_lastname_encoreid.pdf` (e.g. `maya_chen_45821.pdf`)
- `encoreid.pdf` (e.g. `45821.pdf`)

Avoid: filenames with no name or ID (e.g. `resume.pdf`, `cv_001.pdf`) —
dedup will fall back to content hashing only.

## Metadata (optional)

If you can include a `metadata.csv` alongside the resume files, we can
enrich the index with structured fields:

```csv
encore_id,name,email,current_title,current_company,location,last_contact_date
45821,Maya Chen,maya@example.com,Senior Backend Engineer,Stripe,Remote (US),2026-06-15
45822,Daniel Okonkwo,,Backend Engineer,Plaid,New York NY,2026-05-22
```

The `email` and `last_contact_date` fields are particularly valuable for
the "stale candidate" and "never-contacted" analytics in the Intelligence
Dashboard.

## Encryption

If your Encore export is password-protected (rare, but happens), include the
password in a separate file called `password.txt` (just the password, no
formatting). We'll delete it immediately after extraction.

## Size limits

| Tier | Max zip size | Max individual file size |
|---|---|---|
| Pilot (Option A) | 5 GB | 10 MB per resume |
| Pilot (Option B) | Unlimited | 10 MB per resume |
| Production | Unlimited | 10 MB per resume |

If your zip exceeds 5 GB, use Option B (your infrastructure) or split into
multiple zips and we'll process them sequentially.

## What we do NOT need

- ❌ Encore database credentials
- ❌ Encore API keys
- ❌ Direct Encore access
- ❌ Recruiter notes or ratings (we'll generate our own)
- ❌ Salary data
- ❌ EEO / demographic data (we explicitly do not want this — see SECURITY.md)

## Delivery

- **Option A:** Upload to our secure S3 bucket (URL provided per pilot)
- **Option B:** Place on your infrastructure, we'll process in place
- **Alternative:** Dropbox / Google Drive / WeTransfer link emailed to pilot@scrutexity.com

## After delivery

You'll receive an acknowledgment within 1 hour of delivery, including:

- File count received
- Total size
- Estimated completion time
- Run ID (for tracking)

The proof report follows within 24 hours.
