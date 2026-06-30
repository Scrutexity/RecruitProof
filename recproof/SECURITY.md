# Security

RecruitProof is designed as a private candidate intelligence layer.

## Principles

- Read-only ingestion first.
- Local-first processing where possible.
- No external LLM calls unless explicitly enabled.
- Hash source files and maintain a run manifest.
- Minimize PII in demos and exports.
- Keep raw CVs out of public repos.

## Demo warning

Never commit real resumes, candidate emails, phone numbers, notes, or Encore exports to GitHub.
