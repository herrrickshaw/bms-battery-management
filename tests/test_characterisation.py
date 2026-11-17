"""Characterisation tests: simulations must reproduce the pre-refactor outputs.

``golden/baseline.json`` comes from the ORIGINAL ``main`` code (see
``characterise.py``).  Console output and all non-float values / structure are
compared exactly.  Floats are compared through order-sensitive sums with a
1e-9 relative tolerance: robust to libm/BLAS last-bit differences between the
macOS capture and the Linux CI runners, while any real change in a number,
its position or the result's shape still fails.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import characterise  # noqa: E402

GOLDEN = json.loads(characterise.GOLDEN.read_text())


REL_TOL = 1e-9
# summary key -> key of the matching sum of absolute values (the error scale)
_SCALE = {"sum": "abs_sum", "wsum": "wabs_sum"}


def _matches(actual, golden):
    """Exact except for float summaries, which get a relative tolerance."""
    if isinstance(golden, dict) and "n_floats" in golden:
        if not isinstance(actual, dict) or actual.keys() != golden.keys():
            return False
        for key, want in golden.items():
            got = actual[key]
            if key in _SCALE:
                if abs(got - want) > REL_TOL * max(golden[_SCALE[key]], abs(want)):
                    return False
            elif key in ("abs_sum", "wabs_sum", "abs_max"):
                if not math.isclose(got, want, rel_tol=REL_TOL):
                    return False
            elif got != want:
                return False
        return True
    if isinstance(golden, dict):
        return (isinstance(actual, dict) and actual.keys() == golden.keys()
                and all(_matches(actual[k], golden[k]) for k in golden))
    return actual == golden


@pytest.fixture(scope="module")
def current():
    return characterise.collect()


def test_scenario_set_unchanged(current):
    assert sorted(current) == sorted(GOLDEN)


@pytest.mark.parametrize("scenario", sorted(GOLDEN))
def test_matches_baseline(current, scenario):
    assert _matches(current[scenario], GOLDEN[scenario]), (current[scenario], GOLDEN[scenario])
