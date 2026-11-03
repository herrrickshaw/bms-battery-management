"""Characterisation tests: simulations must reproduce the pre-refactor outputs.

Digests in ``golden/baseline.json`` come from the original code (see
``characterise.py``, regenerated from the original ``main`` code).  Floats are
digested rounded to 9 significant digits, so the tests assert identical results
up to ~1e-9 relative: robust to libm/BLAS last-bit differences between macOS and
the Linux CI runners, while any real change in a number still fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import characterise  # noqa: E402

GOLDEN = json.loads(characterise.GOLDEN.read_text())


@pytest.fixture(scope="module")
def current():
    return characterise.collect()


def test_scenario_set_unchanged(current):
    assert sorted(current) == sorted(GOLDEN)


@pytest.mark.parametrize("scenario", sorted(GOLDEN))
def test_matches_baseline(current, scenario):
    assert current[scenario] == GOLDEN[scenario]
