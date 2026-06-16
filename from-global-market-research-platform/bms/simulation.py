"""
BMS multi-vehicle desktop simulation.

Demonstrates the BMS running across three EV classes:
  1. Electric 2-Wheeler  (48V LFP scooter)
  2. Retrofit 4-Wheeler  (72V Lead-Acid, IJAREEIE 2019 paper)
  3. Electric Bus        (409.6V LFP, 150 kW)

Run:
    python -m bms.simulation                  # all three vehicles
    python -m bms.simulation --vehicle 2W     # single vehicle
    python -m bms.simulation --plot           # save plots to reports/
"""

import argparse
import os
import numpy as np
from typing import List

from .bms_controller import BMSController, BMSPackState
from .vehicles import (
    TWO_WHEELER, FOUR_WHEELER_RETRO, FOUR_WHEELER_MODERN, ELECTRIC_BUS,
    VehicleProfile, make_bms_controller,
)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _header(profile: VehicleProfile):
    print(f"\n{profile.summary()}")
    cols = ["Time(s)", "State", "SOC%", "V_pack(V)", "I(A)", "T_max(C)", "Fan%", "Alerts"]
    print(f"  {'|'.join(f'{c:>10}' for c in cols)}")
    print("  " + "-" * (11 * len(cols)))


def _row(state: BMSPackState, t: float, interval: int):
    if int(t) % interval != 0:
        return
    alert_str = ",".join(a.name for a in state.alerts) if state.alerts else "-"
    cols = [
        f"{t:>10.0f}",
        f"{state.supervisor.state.name:>10}",
        f"{state.pack_soc_mean*100:>10.1f}",
        f"{state.pack_voltage_v:>10.2f}",
        f"{state.pack_current_a:>10.1f}",
        f"{state.pack_temp_max_c:>10.1f}",
        f"{state.thermal.fan_pwm_pct:>10.1f}",
        f"{alert_str:>10}",
    ]
    print("  " + "|".join(cols))


def _simulate_charge_discharge(
    profile: VehicleProfile,
    soc_init: float = 0.20,
    dt: float = 1.0,
    charge_s: int = 5400,
    discharge_s: int = 3600,
    discharge_current: float = None,
    print_interval: int = 600,
) -> List[BMSPackState]:
    """Run a CC-CV charge followed by constant-current discharge."""

    # Slight SOC spread across cells to show balancing
    n = profile.n_cells_series
    spread = 0.02
    socs = [float(np.clip(soc_init + spread * (i / max(n - 1, 1) - 0.5), 0.0, 1.0))
            for i in range(n)]

    bms = make_bms_controller(profile, soc_init=socs, ambient_temp_c=25.0)
    history: List[BMSPackState] = []

    _header(profile)

    # ---- Phase 1: CC-CV Charge ----
    cc_i = profile.cell_config.i_max_charge * profile.n_cells_parallel
    cv_term = abs(profile.cell_config.i_cv_term) * profile.n_cells_parallel
    in_cv = False
    cv_start = 0.0
    t = 0.0

    for tick in range(charge_s):
        t = tick * dt
        if not in_cv:
            charge_current = cc_i
        else:
            decay = np.exp(-(t - cv_start) / 1200.0)
            charge_current = cc_i * decay
            if abs(charge_current) < cv_term:
                break

        state = bms.step(current=charge_current, dt=dt, charge_requested=True)
        history.append(state)
        _row(state, t, print_interval)

        if not in_cv and max(state.cell_voltages_v) >= profile.cell_config.v_max:
            in_cv = True
            cv_start = t
        if state.pack_soc_mean >= 0.95:
            break

    print(f"\n  >> Charge done  SOC={history[-1].pack_soc_mean*100:.1f}%  "
          f"V={history[-1].pack_voltage_v:.1f}V  T={history[-1].pack_temp_max_c:.1f}°C")

    # ---- Phase 2: Balancing at rest ----
    for _ in range(min(300, charge_s)):
        t += dt
        state = bms.step(current=0.0, dt=dt)
        history.append(state)
        if state.balancing.v_spread < 0.003:
            break

    # ---- Phase 3: CC Discharge ----
    if discharge_current is None:
        discharge_current = profile.cell_config.i_max_discharge * profile.n_cells_parallel * 0.5

    for tick in range(discharge_s):
        t += dt
        state = bms.step(current=discharge_current, dt=dt, discharge_requested=True)
        history.append(state)
        _row(state, t, print_interval)
        if state.pack_soc_mean <= 0.05 or state.fault_active:
            break

    last = history[-1]
    print(f"\n  >> Discharge done  SOC={last.pack_soc_mean*100:.1f}%  "
          f"Fault={last.fault_description}  "
          f"SOH={last.soh.soh_capacity_pct:.2f}%  "
          f"Fan={last.thermal.fan_pwm_pct:.0f}%\n")

    return history


# ---------------------------------------------------------------------------
# Per-vehicle simulation functions
# ---------------------------------------------------------------------------

def simulate_two_wheeler(**kwargs) -> List[BMSPackState]:
    """Electric scooter / e-bike: 15S LFP, 48V, 1.5 kW."""
    return _simulate_charge_discharge(
        TWO_WHEELER,
        soc_init=0.15,
        charge_s=3600,
        discharge_s=2400,
        discharge_current=20.0,     # 0.67C — typical scooter load
        print_interval=600,
        **kwargs,
    )


def simulate_four_wheeler_retrofit(**kwargs) -> List[BMSPackState]:
    """
    Retrofit IC→EV car: 36S Lead-Acid, 72V/130Ah, 10 kW BLDC.
    Source: IJAREEIE Vol. 8, Issue 4, April 2019.
    3-stage CC → CV(Topping) → Float charging.
    """
    return _simulate_charge_discharge(
        FOUR_WHEELER_RETRO,
        soc_init=0.30,
        charge_s=28800,             # paper: 8 hours full charge
        discharge_s=10800,          # paper: ~3 hours at normal load
        discharge_current=43.0,     # ~10kW / 72V ≈ 138A → 43A avg
        print_interval=3600,
        **kwargs,
    )


def simulate_electric_bus(**kwargs) -> List[BMSPackState]:
    """Electric bus: 128S2P LFP, 409.6V, 150 kW, 163.8 kWh."""
    return _simulate_charge_discharge(
        ELECTRIC_BUS,
        soc_init=0.20,
        charge_s=7200,
        discharge_s=3600,
        discharge_current=100.0,    # ~41 kW city cruising load (peak is 366 A)
        print_interval=600,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Comparison summary table
# ---------------------------------------------------------------------------

def print_comparison_table():
    print("\n" + "=" * 90)
    print("  BMS MULTI-VEHICLE CAPABILITY COMPARISON")
    print("=" * 90)
    headers = ["Vehicle", "Chemistry", "Pack", "Voltage", "Energy", "Motor", "Charge"]
    rows = [
        ["2-Wheeler (Scooter)", "LFP",       "15S1P",  "48V",    "1.4 kWh",  "1.5 kW",  "CC-CV"],
        ["4W Retrofit (PbA)",   "Lead-Acid", "36S1P",  "72V",    "9.4 kWh",  "10 kW",   "CC-CV-Float"],
        ["4W Modern LFP",       "LFP",       "32S1P",  "102V",   "6.1 kWh",  "30 kW",   "CC-CV"],
        ["Electric Bus",        "LFP",       "128S2P", "409V",   "163.8 kWh","150 kW",  "CC-CV"],
    ]
    col_w = [22, 12, 8, 8, 11, 9, 14]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_w)
    print(fmt.format(*headers))
    print("  " + "-" * 88)
    for r in rows:
        print(fmt.format(*r))
    print("=" * 90)

    print("""
  Key BMS algorithms (common across all vehicles):
    SOC estimation  : Extended Kalman Filter on 2-RC Thevenin model
    SOH estimation  : Capacity fade (Ah throughput) + R0 growth (dV/dI)
    Cell balancing  : Passive bleed-down with dead-band hysteresis
    Charging        : Stage 1 CC bulk → Stage 2 CV topping → (Stage 3 Float for PbA)
    Power limits    : SOC + temperature + SOH derating
    Thermal         : PWM fan controller; heater below T_min
    Protection      : OV / UV / OC / OT / isolation fault → contactor open
    Alerts          : Driver warnings (low SOC, high temp, cell imbalance)
""")


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _plot(histories: dict, output_dir: str = "reports"):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("matplotlib not installed — skipping plots.")
        return

    os.makedirs(output_dir, exist_ok=True)
    colors = {"2W": "#2ecc71", "4W_RETRO": "#e74c3c", "BUS": "#3498db"}

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("BMS Multi-Vehicle Simulation", fontsize=14, fontweight="bold")
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    plots = [
        (gs[0, 0], "pack_soc_mean", 100, "SOC (%)", "State of Charge"),
        (gs[0, 1], "pack_voltage_v", 1,  "Voltage (V)", "Pack Voltage"),
        (gs[0, 2], "pack_temp_max_c", 1, "Temp (°C)", "Max Cell Temperature"),
        (gs[1, 0], "pack_current_a", 1,  "Current (A)", "Pack Current"),
        (gs[1, 1], None, 1, "Fan (%)", "Cooling Fan Duty"),
        (gs[1, 2], None, 1, "SOH (%)", "Capacity SOH"),
    ]

    for spec, attr, scale, ylabel, title in plots:
        ax = fig.add_subplot(spec)
        for label, hist in histories.items():
            t = [s.timestamp_s for s in hist]
            if attr:
                y = [getattr(s, attr) * scale for s in hist]
            elif ylabel == "Fan (%)":
                y = [s.thermal.fan_pwm_pct for s in hist]
            else:
                y = [s.soh.soh_capacity_pct for s in hist]
            ax.plot(t, y, label=label, color=colors.get(label, "gray"), linewidth=1.2)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    path = os.path.join(output_dir, "bms_multi_vehicle.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  Plot saved → {path}")
    plt.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

VEHICLE_MAP = {
    "2W": simulate_two_wheeler,
    "4W_RETRO": simulate_four_wheeler_retrofit,
    "BUS": simulate_electric_bus,
}


def main():
    parser = argparse.ArgumentParser(description="BMS multi-vehicle simulation")
    parser.add_argument("--vehicle", choices=list(VEHICLE_MAP.keys()),
                        help="Run only this vehicle class (default: all)")
    parser.add_argument("--plot", action="store_true", help="Save comparison plot")
    args = parser.parse_args()

    print_comparison_table()

    if args.vehicle:
        VEHICLE_MAP[args.vehicle]()
    else:
        histories = {}
        histories["2W"]       = simulate_two_wheeler()
        histories["4W_RETRO"] = simulate_four_wheeler_retrofit()
        histories["BUS"]      = simulate_electric_bus()

        if args.plot:
            _plot(histories)


if __name__ == "__main__":
    main()
