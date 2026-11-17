"""Unit tests for the pure computation helpers extracted from bms.simulation."""
from __future__ import annotations

import pytest

from bms import simulation as sim
from bms.manufacturer_profiles import ATHER_450X, ATHER_DRIVING
from bms.vehicles import TWO_WHEELER


def test_project_degradation_samples_first_every_nth_and_last():
    pts = sim.project_degradation(TWO_WHEELER, n_cycles=60, print_every=25)
    assert [p.cycle for p in pts] == [1, 25, 50, 60]


def test_project_degradation_linear_fade_and_status():
    pt = sim.project_degradation(TWO_WHEELER, n_cycles=300, deg_rate=0.001)[-1]
    assert pt.soh_q == pytest.approx(70.0)
    assert pt.r0_aged == pytest.approx(TWO_WHEELER.cell_config.r0 * 1000.0 * 1.3)
    assert pt.status == "WARNING"          # 70 % is below the 80 % warning, not below critical


def test_linear_soh_floors_at_zero():
    assert sim.linear_soh_pct(2.0, 10) == 80.0
    assert sim.linear_soh_pct(50.0, 10) == 0.0


def test_manufacturer_ageing_efc_formula():
    stress, efcs, loss, eol = sim.manufacturer_ageing(ATHER_450X, ATHER_DRIVING, 1e-4, 0.5)
    assert efcs == pytest.approx(ATHER_DRIVING.trips_per_day * 365.25 * ATHER_DRIVING.dod_per_trip)
    assert stress > 0 and loss > 0.5 and eol > 0


def test_run_cold_case_warm_ambient_has_no_fault():
    r = sim.run_cold_case(TWO_WHEELER, 25.0, 10.0, 30, 0.8)
    assert r.fault == "-" and not r.dis_blocked
    assert 0.0 < r.soc_final < 0.8 and r.ah_out == pytest.approx(10.0 * 30 / 3600.0)


def test_cli_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        sim.main(["--help"])
    assert exc.value.code == 0
    assert "--manufacturers" in capsys.readouterr().out
