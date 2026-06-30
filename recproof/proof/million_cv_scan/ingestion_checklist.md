# Ingestion Checklist

## Before export

- Confirm read-only access.
- Confirm whether Encore stores resume text or only attachments.
- Confirm PDF/DOCX export fields.
- Confirm whether emails, phone numbers, and notes are included.
- Confirm retention and deletion rules.
- Confirm whether candidate consent terms allow internal rediscovery search.

## During import

- Virus scan files.
- Hash every source document.
- Extract text.
- Normalize candidate identity.
- Dedupe by email, phone, name, and semantic fingerprint.
- Log failed files.
- Build embeddings.
- Build FAISS and optional BM25 index.
- Run role-specific proof searches.

## After import

- Produce executive report.
- Produce failure repair queue.
- Produce duplicate report.
- Produce top hidden candidates.
- Delete temporary raw files if required.
