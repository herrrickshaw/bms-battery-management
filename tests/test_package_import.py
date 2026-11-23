"""The package must be importable on a clean interpreter (guards against NameErrors at class-definition time)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="bms/supervisor.py:149 annotates `Optional[float]` but only imports `List` from typing "
           "(line 29): importing bms raises NameError. Remove this marker once the import is fixed.",
)
def test_supervisor_module_imports_cleanly():
    r = subprocess.run([sys.executable, "-c", "import bms.supervisor"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr.strip().splitlines()[-1]
