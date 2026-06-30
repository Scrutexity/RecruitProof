#!/usr/bin/env bash
# scripts/validate_pr.sh — Pre-commit / pre-PR validation hook
# ============================================================================
# Run this before pushing. Fails fast on any issue.
#
# Install as a git hook:
#   cp scripts/validate_pr.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

FAIL=0

echo "RecruitProof — PR Validation"
echo "============================"

# ---- 1. Syntax check all Python files ----
echo "→ Syntax-checking Python files..."
for f in $(find . -name "*.py" -not -path "./.venv/*" -not -path "./__pycache__/*" -not -path "./recproof/*"); do
    if ! python3 -m py_compile "$f" 2>/dev/null; then
        error "Syntax error in $f"
        FAIL=1
    fi
done
[ $FAIL -eq 0 ] && info "All Python files compile"

# ---- 2. Lint (if deps installed) ----
if python3 -c "import flake8" 2>/dev/null; then
    echo "→ Running flake8..."
    if ! python3 -m flake8 *.py tests/ scripts/ --max-line-length=100 --max-complexity=15 --extend-ignore=E203,W503; then
        error "flake8 found issues"
        FAIL=1
    else
        info "flake8 clean"
    fi
fi

# ---- 3. Format check (if black installed) ----
if python3 -c "import black" 2>/dev/null; then
    echo "→ Checking formatting with black..."
    if ! python3 -m black --check --line-length=100 *.py tests/ scripts/ 2>/dev/null; then
        error "black found formatting issues (run: make format)"
        FAIL=1
    else
        info "black: formatting OK"
    fi
fi

# ---- 4. Run unit tests (skip slow ones) ----
if python3 -c "import pytest" 2>/dev/null; then
    echo "→ Running unit tests (skipping slow)..."
    if ! python3 -m pytest tests/ -m "not slow" --tb=short -q; then
        error "unit tests failed"
        FAIL=1
    else
        info "unit tests pass"
    fi
fi

# ---- 5. Verify the .env.example hasn't drifted from .env keys ----
if [ -f ".env.example" ] && [ -f ".env" ]; then
    echo "→ Checking .env vs .env.example..."
    if ! diff <(grep -oE '^[A-Z_]+' .env.example | sort) <(grep -oE '^[A-Z_]+' .env | sort) >/dev/null; then
        error ".env and .env.example have different keys"
        FAIL=1
    else
        info ".env matches .env.example keys"
    fi
fi

echo "============================"
if [ $FAIL -eq 0 ]; then
    info "All checks passed. Ready to commit."
    exit 0
else
    error "Validation failed. Fix the issues above before pushing."
    exit 1
fi
