import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch):
    """Run every test from the repo root so relative data paths resolve."""
    monkeypatch.chdir(ROOT)
