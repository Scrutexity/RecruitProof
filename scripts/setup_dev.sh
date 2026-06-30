#!/usr/bin/env bash
# scripts/setup_dev.sh — One-command RecruitProof dev environment setup
# ============================================================================
# Idempotent: safe to re-run. Detects missing pieces and installs them.
#
# Usage:
#   ./scripts/setup_dev.sh           # full setup
#   ./scripts/setup_dev.sh --quick   # skip the demo data + index build (just deps)
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

echo "RecruitProof — Dev Environment Setup"
echo "===================================="
echo ""

# ---- 1. Python version check ----
if ! command -v python3 &>/dev/null; then
    error "Python 3 is not installed. Install Python 3.10+ and re-run."
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python $PY_VERSION detected"
if [[ "$PY_VERSION" < "3.10" ]]; then
    error "Python 3.10+ required, got $PY_VERSION"
    exit 1
fi

# ---- 2. Virtualenv ----
if [ ! -d ".venv" ]; then
    info "Creating virtualenv at .venv/"
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
info "Virtualenv activated"

# ---- 3. Python dependencies ----
info "Installing Python dependencies (this takes ~3 minutes the first time)..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pytest black isort flake8 mypy --quiet
info "Dependencies installed"

# ---- 4. Verify the engine imports cleanly ----
info "Verifying the engine imports cleanly..."
python -c "import search, agents, hybrid_retrieval, ranker, jd_parser; print('  all engine modules import OK')"
info "Engine imports verified"

# ---- 5. Optional: demo data + index ----
if [ "$1" != "--quick" ]; then
    if [ ! -f "data/candidates.jsonl" ]; then
        info "Generating 10,000 synthetic candidates..."
        python generate_synthetic_data.py --count 10000 --out data/candidates.jsonl
    else
        info "data/candidates.jsonl already exists, skipping generation"
    fi

    if [ ! -f "output/candidates.faiss" ]; then
        info "Building hybrid FAISS + BM25 index (this takes ~2 minutes for 10K candidates)..."
        python precompute.py --candidates data/candidates.jsonl --output output/ \
            --model mini --index flat --hybrid
    else
        info "output/candidates.faiss already exists, skipping index build"
    fi

    info "Running a smoke-test search..."
    python search.py --jd data/sample_jd.txt --top 3 --candidates data/candidates.jsonl --hybrid 2>/dev/null | head -5
fi

# ---- 6. Run the test suite ----
info "Running the test suite..."
python -m pytest tests/ -v --tb=short -m "not slow" || warn "Some tests failed (non-blocking for setup)"

echo ""
echo "===================================="
info "Setup complete. Next steps:"
echo "  • Start the API server:    make dev"
echo "  • Run a search:            make search"
echo "  • Run the test suite:      make test"
echo "  • Generate demo PDFs:      make demo-pdfs"
echo "  • Build the Docker image:  make docker-build"
echo ""
echo "  Docs: README.md, DEPLOYMENT.md, ARCHITECTURE.md"
echo "===================================="
