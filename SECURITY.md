# Security

## Threat model

RecruitProof is designed for enterprises where candidate data is the most
sensitive asset in the company. Our threat model assumes:

- The network is hostile (attacker can reach the VM)
- The disk may be subpoenaed (data must be encrypted at rest)
- Insiders are the highest-risk threat (RBAC + audit logging required)
- Vendor cloud is not trusted (local-first by default)

## Data sovereignty

- **Local-first**: all candidate data stays on your VM. No outbound traffic
  during search, ingestion, or indexing.
- **No telemetry**: RecruitProof does not phone home. Version checks are
  opt-in only.
- **Regional deployment**: deploy in your AWS / Azure / GCP region of choice.
  We never copy data across regions.
- **Air-gap compatible**: RecruitProof can run fully air-gapped after the
  initial model download (which can be done via sneakernet).

## Encryption

| Layer | Algorithm | Key management |
|---|---|---|
| At rest (candidate data) | AES-256-GCM | Customer-managed KMS / Vault |
| At rest (FAISS index) | AES-256-GCM | Same as candidate data |
| In transit (API) | TLS 1.3 | Let's Encrypt / corporate PKI |
| In transit (internal) | mTLS | Self-signed CA (Docker network) |
| Backups | AES-256-GCM | Separate KMS key per backup |

## Authentication & RBAC

Five roles, all enforced server-side:

| Role | Permissions |
|---|---|
| Admin | Full access, user management, configuration |
| Recruiter | Search, view candidates, export shortlists |
| Hiring Manager | Search, view candidates (no export) |
| Auditor | Read-only access to all data + audit logs |
| Read-Only | Search only, no candidate detail |

Authentication: SSO via SAML 2.0 (Okta, Azure AD, Google Workspace) or local
bcrypt-hashed passwords. MFA supported via TOTP.

## Secure logging

- All actions logged: search, view, export, import, config change, login
- Logs contain: timestamp, user, role, action, candidate_id (hashed), IP
- Logs do NOT contain: resume text, candidate PII, search queries
- Logs are tamper-evident (hash-chained, signed daily)
- Logs are retained for 7 years (configurable)

## PHI / PII handling

RecruitProof explicitly does NOT collect or process:

- EEO data (race, gender, veteran status)
- Salary history
- Background check results
- Medical / disability information
- Immigration status (beyond "requires sponsorship: yes/no")

If your Encore export accidentally includes these fields, RecruitProof will:

1. Log a warning to the audit log
2. Strip the fields from the indexed candidate record
3. Not include them in any search result or export

## Disaster recovery

| Metric | Target |
|---|---|
| RPO (Recovery Point Objective) | 15 minutes |
| RTO (Recovery Time Objective) | 4 hours |
| Backup frequency | Hourly incremental, daily full |
| Backup retention | 30 days (configurable) |
| Backup location | Separate AZ or on-prem |
| Restore test | Quarterly (automated) |

## Vulnerability disclosure

Email security@scrutexity.com with any security finding.
We respond within 24 hours and credit responsible disclosure.

## Compliance roadmap

| Framework | Status |
|---|---|
| GDPR | ✅ Architecture is GDPR-compatible (local-first, data portability, right to erasure). Formal compliance review not yet completed. |
| CCPA | ✅ Compliant (no data sale, opt-out not required — we don't share) |
| SOC 2 Type I | 🔄 Planned (audit firm not yet engaged) |
| SOC 2 Type II | 🔄 Planned (Q1 2027) |
| ISO 27001 | 🔄 Planned (2027) |
| HIPAA | ❌ Not pursued (RecruitProof does not handle PHI) |

## Open-source security

Because RecruitProof's core is MIT-licensed and open-source, your security
team can audit every line of code that touches candidate data. No black boxes.

- Repository: https://github.com/Scrutexity/RecruitProof
- Security advisories: https://github.com/Scrutexity/RecruitProof/security/advisories
- Signed releases: every release is GPG-signed (public key in SECURITY.md)

## Penetration testing

RecruitProof's hosted platform undergoes annual third-party pentests.
Reports available under NDA. Customers may pentest their own deployment
without notifying Scrutexity (it's your infrastructure).
