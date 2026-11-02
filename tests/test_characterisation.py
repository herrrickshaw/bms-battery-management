"""Characterisation tests: simulations must reproduce the pre-refactor outputs.

Digests in ``golden/baseline.json`` come from the original code (see
``characterise.py``).  Floats are compared via their exact hex form, so these
tests assert bit-identical results.  If a platform's libm ever differs in the
last bit, regenerate locally rather than loosening the comparison blindly.
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
