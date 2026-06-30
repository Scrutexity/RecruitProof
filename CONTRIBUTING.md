# Contributing to RecruitProof

First: thank you. RecruitProof is open-source because we believe recruiting
infrastructure should be auditable, local-first, and owned by the customer —
not the vendor. Every contribution advances that mission.

---

## Code of Conduct

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
Be excellent to each other. Recruitment is a high-stakes domain; be thoughtful
about candidate privacy, bias, and the real humans behind every resume.

---

## Development setup (10 minutes)

```bash
# 1. Clone
git clone https://github.com/Scrutexity/RecruitProof
cd RecruitProof

# 2. Create a virtualenv (Python 3.10+)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dev dependencies
pip install -r requirements.txt
pip install pytest black isort flake8 mypy

# 4. Generate test data + build the index
python generate_synthetic_data.py --count 10000 --out data/candidates.jsonl
python precompute.py --candidates data/candidates.jsonl --output output/ \
    --model mini --index flat --hybrid

# 5. Run the test suite
pytest tests/

# 6. Start the API server
python -m uvicorn api_server:app --reload
```

---

## Code style

We use the standard Python ecosystem. CI enforces all of these.

| Tool | Purpose | Config |
|---|---|---|
| `black` | Formatting | line-length = 100 |
| `isort` | Import ordering | profile = "black" |
| `flake8` | Linting | max-complexity = 15 |
| `mypy` | Type checking (gradual) | strict on `ranker.py`, `hybrid_retrieval.py` |

Run all checks locally before pushing:

```bash
make lint    # runs flake8 + black --check + isort --check
make test    # runs pytest
```

Or use the pre-commit hook:

```bash
cp scripts/validate_pr.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

## Pull request process

1. **Open an issue first** for any non-trivial change. We'll discuss the
   approach before you sink time into code. Trivial fixes (typos, doc tweaks)
   can go straight to PR.
2. **Branch from `main`**: `git checkout -b feat/my-feature`.
3. **One concern per PR.** A PR that fixes a bug AND adds a feature AND
   refactors a module is hard to review. Split it.
4. **Add tests** for any new logic. Aim for ≥ 80% coverage on changed lines.
5. **Update docs** (`README.md`, `ARCHITECTURE.md`, `PERFORMANCE.md`) if your
   change affects user-facing behavior.
6. **Sign the CLA** (Contributor License Agreement) on your first PR. It's
   a one-click electronic signature that confirms you have the right to
   contribute your code under the MIT license. We promise never to use it
   to relicense your work — we don't have one. Your contributions are licensed
   under MIT, same as the rest of the project. Just sign the one-click electronic
   confirmation on your first PR (a checkbox confirming you have the right to
   contribute your code under the MIT license).
7. **Pass CI.** All checks must be green before merge. We use GitHub Actions:
   - `lint` (black, isort, flake8, mypy)
   - `test` (pytest on Python 3.10, 3.11, 3.12)
   - `integration` (end-to-end search on 1K synthetic resumes)
8. **Squash-merge** into `main`. We keep the commit history clean.

Reviewers aim to respond within 48 hours. If a PR sits longer, ping us in
the GitHub discussion or email maintainers@scrutexity.com.

---

## Testing requirements

| Test type | Where | What we cover |
|---|---|---|
| Unit | `tests/test_ranker.py`, `tests/test_jd_parser.py`, `tests/test_hybrid_retrieval.py` | Pure functions, no I/O |
| Integration | `tests/test_search_e2e.py` | End-to-end search on 1K synthetic resumes |
| Performance | `tests/test_performance.py` (marked `@pytest.mark.slow`) | p50/p95 latency benchmarks |

**Run unit tests fast:** `pytest tests/ -m "not slow"`
**Run everything:** `pytest tests/`

To add a new test, follow the existing pattern in `tests/test_ranker.py`.
Use `pytest.fixture` for shared setup. Use `tmp_path` for filesystem tests.

---

## Architecture primer (read this before non-trivial contributions)

RecruitProof is hexagonal: domain logic (`ranker.py`, `jd_parser.py`,
`hybrid_retrieval.py`) has zero I/O dependencies. Adapters (`faiss_index.py`,
`embedder.py`, `ats_connectors.py`) speak to the outside world. Ports are
the function signatures in the domain layer.

**Don't** add `import requests` or `import faiss` to `ranker.py`.
**Do** add new adapter modules and pass them in via dependency injection.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.

---

## What we welcome

- 🐛 **Bug fixes** — especially around PDF extraction edge cases, fuzzy skill matching, and FAISS index corruption recovery
- 🚀 **Performance** — anything that reduces p99 latency or memory footprint
- 🔌 **New ATS connectors** — SmartRecruiters, iCIMS, BambooHR, Jobvite (follow the pattern in `ats_connectors.py`)
- 🌍 **Internationalization** — non-English JD parsing, non-Latin name handling
- 📚 **Docs** — typo fixes, clearer examples, new tutorials
- 🧪 **Tests** — especially edge cases that have bitten you in production
- 🔒 **Security hardening** — see [SECURITY.md](SECURITY.md)

## What we won't accept

- ❌ Features that require outbound network calls during search (we're local-first)
- ❌ EEO / demographic data collection (see [SECURITY.md](SECURITY.md) — we don't want it)
- ❌ Anything that breaks the FAISS index backward compatibility without a migration path
- ❌ Proprietary dependencies that aren't MIT/Apache-2.0/BSD licensed
- ❌ ATS write-back (we're read-only by design — see [INTEGRATIONS.md](INTEGRATIONS.md))

---

## Security disclosures

Found a security issue? **Do NOT open a public GitHub issue.**
Email security@scrutexity.com. We respond within 24 hours and credit
responsible disclosure. See [SECURITY.md](SECURITY.md) for the full policy.

---

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE) that covers the project.

---

Questions? Open a GitHub discussion or email maintainers@scrutexity.com.
We're a small team but we read everything.
