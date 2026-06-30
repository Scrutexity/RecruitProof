"""
tests/conftest.py — Pytest configuration + fixtures
===================================================

Adds the repo root to sys.path so test files can `from ranker import ...`
without ceremony. Also registers the `slow` marker.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
