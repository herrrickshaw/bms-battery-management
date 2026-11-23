"""Offline tests for the report/plot helpers, CLI dispatch and per-vehicle scenario wrappers.

matplotlib is never imported for real: a recording fake is injected through ``sys.modules``.
"""
from __future__ import annotations

import runpy
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bms.simulation import charge_discharge, cli, report
from bms.vehicles import ELECTRIC_BUS, FOUR_WHEELER_RETRO, TWO_WHEELER


def _hist(n=3, soc=0.5, volt=50.0, temp=30.0, cur=2.0, fan=40.0, soh=97.0):
    return [
        SimpleNamespace(
            timestamp_s=float(i), pack_soc_mean=soc + i * 0.01, pack_voltage_v=volt + i,
            pack_temp_max_c=temp + i, pack_current_a=cur + i,
            thermal=SimpleNamespace(fan_pwm_pct=fan + i),
            soh=SimpleNamespace(soh_capacity_pct=soh - i),
        )
        for i in range(n)
    ]


@pytest.fixture
def fake_mpl(monkeypatch):
    plt = MagicMock(name="pyplot")
    gridspec = MagicMock(name="gridspec")
    axes = [MagicMock(name=f"ax{i}") for i in range(6)]
    fig = MagicMock(name="fig")
    fig.add_subplot.side_effect = axes
    plt.figure.return_value = fig
    mpl = MagicMock(name="matplotlib", pyplot=plt, gridspec=gridspec)
    monkeypatch.setitem(sys.modules, "matplotlib", mpl)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", plt)
    monkeypatch.setitem(sys.modules, "matplotlib.gridspec", gridspec)
    return SimpleNamespace(plt=plt, fig=fig, axes=axes, gridspec=gridspec)


class TestComparisonTable:
    def test_rows_and_sections_printed(self, capsys):
        report.print_comparison_table()
        out = capsys.readouterr().out
        assert out.count("=" * 90) == 3
        for needle in ("2-Wheeler (Scooter)", "4W Retrofit (PbA)", "4W Modern LFP", "Electric Bus",
                       "163.8 kWh", "CC-CV-Float", "Supported chemistries", "Lifecycle simulations"):
            assert needle in out
        header = [ln for ln in out.splitlines() if "Vehicle" in ln and "Chemistry" in ln]
        assert len(header) == 1
        assert header[0].split() == ["Vehicle", "Chemistry", "Pack", "Voltage", "Energy", "Motor", "Charge"]


class TestPlot:
    def test_missing_matplotlib_is_reported_not_raised(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)
        monkeypatch.setitem(sys.modules, "matplotlib.gridspec", None)
        out_dir = tmp_path / "reports"
        report._plot({"2W": _hist()}, output_dir=str(out_dir))
        assert "matplotlib not installed" in capsys.readouterr().out
        assert not out_dir.exists()

    def test_plot_saves_png_in_output_dir(self, fake_mpl, tmp_path, capsys):
        out_dir = tmp_path / "nested" / "reports"
        report._plot({"2W": _hist()}, output_dir=str(out_dir))
        assert out_dir.is_dir()
        expected = str(out_dir / "bms_multi_vehicle.png")
        fake_mpl.plt.savefig.assert_called_once_with(expected, dpi=150, bbox_inches="tight")
        fake_mpl.plt.close.assert_called_once_with()
        assert f"Plot saved → {expected}" in capsys.readouterr().out

    def test_default_output_dir_is_reports(self, fake_mpl, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report._plot({"BUS": _hist()})
        assert (tmp_path / "reports").is_dir()
        assert fake_mpl.plt.savefig.call_args.args[0].replace("\\", "/") == "reports/bms_multi_vehicle.png"

    def test_series_values_scaling_colors_and_labels(self, fake_mpl, tmp_path):
        hist = _hist()
        report._plot({"2W": hist, "OTHER": hist}, output_dir=str(tmp_path))
        ax = fake_mpl.axes
        assert all(a.plot.call_count == 2 for a in ax)
        # panel 0: SOC scaled x100; panel 1: voltage unscaled
        first = ax[0].plot.call_args_list[0]
        assert first.args[0] == [0.0, 1.0, 2.0]
        assert first.args[1] == pytest.approx([50.0, 51.0, 52.0])
        assert first.kwargs == {"label": "2W", "color": "#2ecc71", "linewidth": 1.2}
        assert ax[0].plot.call_args_list[1].kwargs["color"] == "gray"
        assert ax[1].plot.call_args_list[0].args[1] == [50.0, 51.0, 52.0]
        assert ax[2].plot.call_args_list[0].args[1] == [30.0, 31.0, 32.0]
        assert ax[3].plot.call_args_list[0].args[1] == [2.0, 3.0, 4.0]
        assert ax[4].plot.call_args_list[0].args[1] == [40.0, 41.0, 42.0]   # fan duty
        assert ax[5].plot.call_args_list[0].args[1] == [97.0, 96.0, 95.0]   # SOH capacity

    def test_axis_labels_and_titles(self, fake_mpl, tmp_path):
        report._plot({"4W_RETRO": _hist()}, output_dir=str(tmp_path))
        titles = [a.set_title.call_args.args[0] for a in fake_mpl.axes]
        ylabels = [a.set_ylabel.call_args.args[0] for a in fake_mpl.axes]
        assert titles == ["State of Charge", "Pack Voltage", "Max Cell Temperature", "Pack Current",
                          "Cooling Fan Duty", "Capacity SOH"]
        assert ylabels == ["SOC (%)", "Voltage (V)", "Temp (°C)", "Current (A)", "Fan (%)", "SOH (%)"]
        for a in fake_mpl.axes:
            a.set_xlabel.assert_called_once_with("Time (s)")
            a.legend.assert_called_once_with(fontsize=8)
        assert fake_mpl.axes[0].plot.call_args.kwargs["color"] == "#e74c3c"
        fake_mpl.fig.suptitle.assert_called_once()

    def test_bus_color(self, fake_mpl, tmp_path):
        report._plot({"BUS": _hist()}, output_dir=str(tmp_path))
        assert fake_mpl.axes[0].plot.call_args.kwargs["color"] == "#3498db"


class TestCliDispatch:
    @pytest.fixture
    def calls(self, monkeypatch):
        calls = []
        monkeypatch.setattr(cli, "print_comparison_table", lambda: calls.append("table"))

        def fake(name):
            return lambda *a, **k: calls.append((name, a, k)) or [name]

        monkeypatch.setitem(cli.VEHICLE_MAP, "2W", fake("2W"))
        monkeypatch.setitem(cli.VEHICLE_MAP, "4W_RETRO", fake("4W_RETRO"))
        monkeypatch.setitem(cli.VEHICLE_MAP, "BUS", fake("BUS"))
        for attr, name in [("simulate_two_wheeler", "2W"), ("simulate_four_wheeler_retrofit", "4W_RETRO"),
                           ("simulate_electric_bus", "BUS"), ("simulate_degradation", "deg"),
                           ("simulate_cold_temperature", "cold"), ("simulate_driving_degradation", "drive"),
                           ("simulate_manufacturer_comparison", "mfr")]:
            monkeypatch.setattr(cli, attr, fake(name))
        monkeypatch.setattr(cli, "_run_datasets_validation", lambda: calls.append("datasets"))
        monkeypatch.setattr(cli, "_plot", lambda h: calls.append(("plot", sorted(h))))
        return calls

    def test_default_runs_all_vehicles_in_order_without_plot(self, calls):
        cli.main([])
        assert [c if isinstance(c, str) else c[0] for c in calls] == ["table", "2W", "4W_RETRO", "BUS"]

    def test_plot_flag_passes_all_histories(self, calls):
        cli.main(["--plot"])
        assert calls[-1] == ("plot", ["2W", "4W_RETRO", "BUS"])

    @pytest.mark.parametrize("veh", ["2W", "4W_RETRO", "BUS"])
    def test_vehicle_flag_runs_only_that_vehicle(self, calls, veh):
        cli.main(["--vehicle", veh])
        assert [c if isinstance(c, str) else c[0] for c in calls] == ["table", veh]

    def test_vehicle_with_plot_does_not_plot(self, calls):
        cli.main(["--vehicle", "BUS", "--plot"])
        assert [c if isinstance(c, str) else c[0] for c in calls] == ["table", "BUS"]

    def test_degradation_arguments(self, calls):
        cli.main(["--degradation"])
        assert calls[1:] == [("deg", (TWO_WHEELER,), dict(n_cycles=300, deg_rate=0.001)),
                             ("deg", (ELECTRIC_BUS,), dict(n_cycles=300, deg_rate=0.0005))]

    def test_cold_runs_two_wheeler_then_bus(self, calls):
        cli.main(["--cold"])
        assert calls[1:] == [("cold", (TWO_WHEELER,), {}), ("cold", (ELECTRIC_BUS,), {})]

    def test_driving_arguments(self, calls):
        cli.main(["--driving"])
        assert calls[1:] == [("drive", (TWO_WHEELER,), dict(simulation_years=10)),
                             ("drive", (ELECTRIC_BUS,), dict(simulation_years=10))]

    def test_manufacturers_arguments(self, calls):
        cli.main(["--manufacturers"])
        assert calls[1:] == [("mfr", (), dict(simulation_years=8))]

    def test_datasets_flag(self, calls):
        cli.main(["--datasets"])
        assert calls == ["table", "datasets"]

    def test_mode_priority_order(self, calls):
        cli.main(["--datasets", "--manufacturers", "--driving", "--cold", "--degradation"])
        assert [c[0] for c in calls[1:]] == ["deg", "deg"]
        calls.clear()
        cli.main(["--datasets", "--manufacturers", "--driving", "--cold"])
        assert [c[0] for c in calls[1:]] == ["cold", "cold"]
        calls.clear()
        cli.main(["--datasets", "--manufacturers", "--driving"])
        assert [c[0] for c in calls[1:]] == ["drive", "drive"]
        calls.clear()
        cli.main(["--datasets", "--manufacturers"])
        assert [c[0] for c in calls[1:]] == ["mfr"]

    def test_mode_wins_over_vehicle(self, calls):
        cli.main(["--cold", "--vehicle", "BUS"])
        assert all(c[0] == "cold" for c in calls[1:])

    def test_vehicle_map_keys(self):
        assert list(cli.VEHICLE_MAP) == ["2W", "4W_RETRO", "BUS"]

    def test_unknown_vehicle_rejected(self):
        with pytest.raises(SystemExit):
            cli.main(["--vehicle", "nope"])


class TestDatasetsMode:
    def test_prints_and_validates(self, monkeypatch, capsys):
        import pandas as pd

        import bms.datasets as ds
        data = {"alpha": pd.DataFrame({"a": [1, 2, 3]}), "beta": pd.DataFrame({"b": [1]})}
        seen = {}

        def validate(d):
            seen["v"] = d
            return {"r": 1}

        monkeypatch.setattr(ds, "load_all_synthetic", lambda: data)
        monkeypatch.setattr(ds, "validate_bms_model", validate)
        monkeypatch.setattr(ds, "print_validation_report", lambda r: seen.setdefault("p", r))
        cli._run_datasets_validation()
        out = capsys.readouterr().out
        assert "Datasets ready: ['alpha', 'beta']" in out
        assert "alpha" in out and "3 rows" in out and "1 rows" in out
        assert seen["v"] is data and seen["p"] == {"r": 1}

    def test_python_dash_m_entry_calls_main(self, monkeypatch):
        called = []
        monkeypatch.setattr(cli, "main", lambda *a, **k: called.append(1))
        monkeypatch.delitem(sys.modules, "bms.simulation.__main__", raising=False)
        runpy.run_module("bms.simulation", run_name="__main__")
        assert called == [1]

    def test_importing_main_module_does_not_run(self, monkeypatch):
        called = []
        monkeypatch.setattr(cli, "main", lambda *a, **k: called.append(1))
        monkeypatch.delitem(sys.modules, "bms.simulation.__main__", raising=False)
        runpy.run_module("bms.simulation.__main__", run_name="not_main")
        assert called == []


class TestScenarioWrappers:
    @pytest.fixture
    def rec(self, monkeypatch):
        rec = []
        monkeypatch.setattr(charge_discharge, "_simulate_charge_discharge",
                            lambda profile, **kw: rec.append((profile, kw)) or "hist")
        return rec

    def test_two_wheeler_parameters(self, rec):
        assert charge_discharge.simulate_two_wheeler() == "hist"
        assert rec == [(TWO_WHEELER, dict(soc_init=0.15, charge_s=3600, discharge_s=2400,
                                          discharge_current=20.0, print_interval=600))]

    def test_retrofit_parameters(self, rec):
        charge_discharge.simulate_four_wheeler_retrofit()
        assert rec == [(FOUR_WHEELER_RETRO, dict(soc_init=0.30, charge_s=28800, discharge_s=10800,
                                                 discharge_current=43.0, print_interval=3600))]

    def test_bus_parameters(self, rec):
        charge_discharge.simulate_electric_bus()
        assert rec == [(ELECTRIC_BUS, dict(soc_init=0.20, charge_s=7200, discharge_s=3600,
                                           discharge_current=100.0, print_interval=600))]

    def test_kwargs_are_forwarded(self, rec):
        charge_discharge.simulate_two_wheeler(dt=0.5)
        assert rec[0][1]["dt"] == 0.5


class TestChargeDischargeEngine:
    def test_short_run_history_and_banners(self, capsys):
        hist = charge_discharge._simulate_charge_discharge(
            TWO_WHEELER, soc_init=0.5, charge_s=5, discharge_s=4, discharge_current=7.0, print_interval=2)
        out = capsys.readouterr().out
        assert ">> Charge done" in out and ">> Discharge done" in out
        assert out.count("Fault=") == 1
        # charge ticks + rest ticks (balancing already within 3 mV exits after first rest tick) + discharge ticks
        charge = [s for s in hist if s.pack_current_a < 0]
        discharge = [s for s in hist if s.pack_current_a > 0]
        assert len(charge) == 5 and all(s.pack_current_a == charge[0].pack_current_a for s in charge)
        assert len(discharge) == 4 and all(s.pack_current_a == 7.0 for s in discharge)
        assert charge[0].pack_current_a == TWO_WHEELER.cell_config.i_max_charge * TWO_WHEELER.n_cells_parallel
        assert [s.timestamp_s for s in hist] == sorted(s.timestamp_s for s in hist)

    def test_default_discharge_current_is_half_max_c(self):
        hist = charge_discharge._simulate_charge_discharge(
            TWO_WHEELER, soc_init=0.5, charge_s=2, discharge_s=2, print_interval=1000)
        cfg = TWO_WHEELER.cell_config
        expected = cfg.i_max_discharge * TWO_WHEELER.n_cells_parallel * 0.5
        assert hist[-1].pack_current_a == pytest.approx(expected)

    def test_initial_soc_spread_is_two_percent_centered(self):
        hist = charge_discharge._simulate_charge_discharge(
            TWO_WHEELER, soc_init=0.5, charge_s=1, discharge_s=1, discharge_current=1.0, print_interval=1000)
        socs = hist[0].cell_soc_estimates
        assert max(socs) - min(socs) == pytest.approx(0.02, abs=2e-3)
        assert socs[0] < socs[-1]
        v = hist[0].cell_voltages_v
        assert v[-1] > v[0]  # higher-SOC cells sit at higher terminal voltage

    def test_high_soc_start_stops_charge_at_95_percent(self):
        hist = charge_discharge._simulate_charge_discharge(
            TWO_WHEELER, soc_init=0.99, charge_s=50, discharge_s=1, discharge_current=1.0, print_interval=1000)
        charge = [s for s in hist if s.pack_current_a < 0]
        assert len(charge) == 1  # SOC already >= 0.95 after the first tick

    def test_discharge_stops_at_soc_floor(self):
        hist = charge_discharge._simulate_charge_discharge(
            TWO_WHEELER, soc_init=0.04, charge_s=1, discharge_s=50, discharge_current=1.0, print_interval=1000)
        discharge = [s for s in hist if s.pack_current_a == 1.0]
        assert len(discharge) == 1


class TestPhasesAndConstants:
    def test_initial_socs_spread_and_clip(self):
        socs = charge_discharge._initial_socs(TWO_WHEELER, 0.5)
        assert len(socs) == TWO_WHEELER.n_cells_series
        assert socs[0] == pytest.approx(0.49)
        assert socs[-1] == pytest.approx(0.51)
        assert socs == sorted(socs)
        clipped = charge_discharge._initial_socs(TWO_WHEELER, 1.0)
        assert max(clipped) == 1.0
        assert min(charge_discharge._initial_socs(TWO_WHEELER, 0.0)) == 0.0

    def test_initial_socs_custom_spread(self):
        socs = charge_discharge._initial_socs(TWO_WHEELER, 0.5, spread=0.1)
        assert socs[-1] - socs[0] == pytest.approx(0.1)

    def test_constants_values(self):
        from bms.simulation import constants as k
        assert (k.CV_TAPER_TAU_S, k.CHARGE_DONE_SOC, k.DISCHARGE_DONE_SOC) == (1200.0, 0.95, 0.05)
        assert (k.MAX_BALANCE_S, k.BALANCED_SPREAD_V) == (300, 0.003)

    def test_balance_phase_caps_at_min_of_max_and_charge_s(self):
        calls = []

        class FakeBms:
            def step(self, current, dt, **kw):
                calls.append((current, dt, kw))
                return SimpleNamespace(balancing=SimpleNamespace(v_spread=1.0))

        hist = []
        t = charge_discharge._balance_phase(FakeBms(), hist, 10.0, 0.5, charge_s=7)
        assert len(hist) == 7 and t == pytest.approx(13.5)
        assert all(c == (0.0, 0.5, {}) for c in calls)
        hist = []
        charge_discharge._balance_phase(FakeBms(), hist, 0.0, 1.0, charge_s=10_000)
        assert len(hist) == 300

    def test_balance_phase_stops_below_3mv_exclusive(self):
        spreads = iter([0.01, 0.003, 0.0029, 0.5])

        class FakeBms:
            def step(self, **kw):
                return SimpleNamespace(balancing=SimpleNamespace(v_spread=next(spreads)))

        hist = []
        charge_discharge._balance_phase(FakeBms(), hist, 0.0, 1.0, 100)
        assert len(hist) == 3  # 0.003 is not < 0.003; 0.0029 is

    def test_discharge_phase_stops_on_fault_or_floor(self):
        def run(states):
            it = iter(states)

            class FakeBms:
                def step(self, **kw):
                    return next(it)

            hist = []
            t = charge_discharge._discharge_phase(FakeBms(), hist, 5.0, 1.0, 10, 3.0, 10_000)
            return len(hist), t

        mk = lambda soc, fault=False: SimpleNamespace(pack_soc_mean=soc, fault_active=fault)  # noqa: E731
        assert run([mk(0.5), mk(0.5, True), mk(0.5)]) == (2, 7.0)
        assert run([mk(0.5), mk(0.05), mk(0.5)]) == (2, 7.0)
        assert run([mk(0.5), mk(0.0501), mk(0.5), mk(0.04)]) == (4, 9.0)

    def test_charge_phase_cv_taper_terminates(self, monkeypatch):
        monkeypatch.setattr(charge_discharge, "_row", lambda *a: None)
        # first tick reaches v_max -> CV; decaying current falls below the termination current
        cfg = SimpleNamespace(i_max_charge=10.0, i_cv_term=-1.0, v_max=4.0)
        profile = SimpleNamespace(cell_config=cfg, n_cells_parallel=1)
        seen = []

        class FakeBms:
            def step(self, current, dt, charge_requested):
                seen.append(current)
                return SimpleNamespace(cell_voltages_v=[4.0], pack_soc_mean=0.1, supervisor=None)

        hist = []
        t = charge_discharge._charge_phase(FakeBms(), profile, hist, 1.0, 100_000, 10**9)
        assert seen[0] == 10.0
        assert seen[1] == pytest.approx(10.0 * 2.718281828 ** (-1 / 1200.0), rel=1e-6)
        assert all(a > b for a, b in zip(seen, seen[1:]))
        assert seen[-1] >= 1.0 > 10.0 * 2.718281828 ** (-t / 1200.0)

    def test_charge_phase_stops_at_exactly_95_percent(self, monkeypatch):
        monkeypatch.setattr(charge_discharge, "_row", lambda *a: None)
        cfg = SimpleNamespace(i_max_charge=10.0, i_cv_term=-1.0, v_max=4.0)
        profile = SimpleNamespace(cell_config=cfg, n_cells_parallel=1)
        seen = []

        class FakeBms:
            def step(self, current, dt, charge_requested):
                seen.append(current)
                return SimpleNamespace(cell_voltages_v=[3.0], pack_soc_mean=0.95)

        charge_discharge._charge_phase(FakeBms(), profile, [], 1.0, 50, 10**9)
        assert len(seen) == 1                       # SOC >= 0.95 (inclusive) ends the phase at once

    def test_cv_taper_termination_is_strict(self, monkeypatch):
        monkeypatch.setattr(charge_discharge, "_row", lambda *a: None)
        # dt=0 keeps the taper factor at exactly 1.0, so the CV current equals the termination current
        cfg = SimpleNamespace(i_max_charge=5.0, i_cv_term=-5.0, v_max=4.0)
        profile = SimpleNamespace(cell_config=cfg, n_cells_parallel=1)
        seen = []

        class FakeBms:
            def step(self, current, dt, charge_requested):
                seen.append(current)
                return SimpleNamespace(cell_voltages_v=[4.0], pack_soc_mean=0.1)

        charge_discharge._charge_phase(FakeBms(), profile, [], 0.0, 5, 10**9)
        assert len(seen) == 5                       # |I| == I_term is not "below" it: no early exit
