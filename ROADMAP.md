# Roadmap

## Currently shipped (v0.3.0)

- ✅ FAISS IndexFlatIP + IndexIVFFlat
- ✅ BM25 sparse retrieval + RRF hybrid fusion
- ✅ 5-signal MultiSignalRanker (Sem 40 + Role 20 + Skill 15 + Behav 15 + Career 10)
- ✅ 4-agent screening pipeline (Sourcing → Screen → DeepEval → Explain)
- ✅ Workday / Greenhouse / Lever / Ashby ATS connectors (form schemas + evasion profiles)
- ✅ Competitive intelligence + pricing calculator
- ✅ PDF/DOCX ingestion pipeline
- ✅ Local LLM support (Ollama) + OpenAI fallback
- ✅ CSV / JSON / human-readable output modes
- ✅ Batch JD processing
- ✅ Per-candidate explain (`--explain <id>`)
- ✅ Benchmark mode (`--benchmark N`)

## Q3 2026 (v0.4.0)

- 🔄 Encore read-only API connector
- 🔄 Web UI (Next.js dashboard — the one you're looking at)
- 🔄 Slack / Teams notifications
- 🔄 Daily shortlist digest (email + Slack)
- 🔄 SAML 2.0 SSO
- 🔄 Audit log UI
- 🔄 OCR pipeline for image-only PDFs (Tesseract)
- 🔄 SOC 2 Type I audit

## Q4 2026 (v0.5.0)

- 🔄 SmartRecruiters connector
- 🔄 PostgreSQL metadata store (for >10M candidates)
- 🔄 HNSW index variant (for >5M candidates)
- 🔄 Multi-tenant deployment
- 🔄 RecruitProof Cloud (hosted, managed)
- 🔄 Outreach email generation (per-candidate, LLM-powered)
- 🔄 Boolean search mode (for recruiters who prefer it)
- 🔄 Saved searches + alerts

## Q1 2027 (v0.6.0)

- 🔄 SOC 2 Type II audit
- 🔄 Kubernetes deployment (Helm chart)
- 🔄 Multi-region replication
- 🔄 Custom fine-tuned embeddings (per-customer domain)
- 🔄 Predictive time-to-fill analytics
- 🔄 Diversity sourcing (opt-in, with bias auditing)
- 🔄 Interview scheduling integration (Calendly / Chili Piper)

## Q2 2027 (v0.7.0)

- 🔄 ISO 27001 certification
- 🔄 Voice outreach agent (Twilio + ElevenLabs)
- 🔄 Mobile app (recruiter on-the-go)
- 🔄 Public API (REST + GraphQL)
- 🔄 Plugin marketplace (third-party connectors)

## Beyond 2027

- Multi-modal candidate intelligence (video cover letters, portfolio analysis)
- Predictive retention analytics (which hires will stay 2+ years)
- Skills ontology (auto-update skills graph from market data)
- Compensation benchmarking (real-time, by role + region)
- Internal mobility marketplace (match existing employees to open reqs)

---

## How we prioritize

1. **Customer requests** — enterprise customers vote with their renewals
2. **Security & compliance** — non-negotiable, always prioritized
3. **Performance** — every release must maintain or improve p99 latency
4. **Differentiation** — features that competitors can't easily copy
5. **Polish** — UI/UX improvements that increase recruiter adoption

## What we won't build

- ❌ ATS workflow (we're a search intelligence layer, not an ATS)
- ❌ EEO data collection (we don't want it, see SECURITY.md)
- ❌ Background checks (out of scope, plenty of good vendors)
- ❌ Resume rewriting for candidates (different product)
- ❌ Job board scraping (LinkedIn TOS issues, not worth it)

---

## Release cadence

- Minor releases (v0.X.0): quarterly
- Patch releases (v0.X.Y): as needed, typically monthly
- Security releases: within 24 hours of disclosure

All releases are GPG-signed and announced on GitHub Releases + the RecruitProof
newsletter.

## Long-term support

- v0.3.x: supported through 2027
- v0.4.x: supported through 2028
- Each minor release: 18 months of security patches

## Customer influence

Enterprise customers get a seat on the product advisory board (quarterly
call, roadmap input). The top 5 most-requested features each quarter ship
in the next minor release.
