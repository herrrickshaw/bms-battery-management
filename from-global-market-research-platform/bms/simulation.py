"""
BMS desktop simulation — demonstrates a full charge → balance → discharge cycle.

Run:
    python -m bms.simulation
    python -m bms.simulation --plot          # requires matplotlib

Outputs a summary table to stdout and (optionally) saves plots to reports/.
"""

import argparse
import sys
import os
import numpy as np
from typing import List

from .bms_controller import BMSController, BMSPackState
from .config import DEFAULT_CELL, DEFAULT_PACK, DEFAULT_EKF


def _print_header():
    cols = ["Time(s)", "State", "SOC%", "V_pack(V)", "I(A)", "T_max(C)", "V_spread(mV)", "Fault"]
    print(f"{'|'.join(f'{c:>14}' for c in cols)}")
    print("-" * (15 * len(cols)))


def _print_row(state: BMSPackState, interval: int):
    if int(state.timestamp_s) % interval != 0:
        return
    row = [
        f"{state.timestamp_s:>14.0f}",
        f"{state.supervisor.state.name:>14}",
        f"{state.pack_soc_mean*100:>14.1f}",
        f"{state.pack_voltage_v:>14.2f}",
        f"{state.pack_current_a:>14.1f}",
        f"{state.pack_temp_max_c:>14.1f}",
        f"{state.balancing.v_spread*1000:>14.2f}",
        f"{state.fault_description:>14}",
    ]
    print("|".join(row))


def run_simulation(
    n_cells: int = 16,
    soc_init: float = 0.20,
    dt: float = 1.0,
    charge_duration_s: int = 7200,     # 2-hour charge
    discharge_current_a: float = 100.0,
    discharge_duration_s: int = 3000,
    plot: bool = False,
) -> List[BMSPackState]:
    """
    Full simulation: CC-CV charge → passive balancing → constant-current discharge.

    Returns a list of BMSPackState snapshots (one per dt step).
    """

    # Introduce a small initial SOC spread to demonstrate balancing
    soc_spread = 0.02
    socs = [soc_init + soc_spread * (i / max(n_cells - 1, 1) - 0.5) for i in range(n_cells)]
    socs = [float(np.clip(s, 0.0, 1.0)) for s in socs]

    bms = BMSController(
        n_cells=n_cells,
        cell_cfg=DEFAULT_CELL,
        pack_cfg=DEFAULT_PACK,
        ekf_cfg=DEFAULT_EKF,
        soc_init=socs,
        ambient_temp_c=25.0,
    )

    history: List[BMSPackState] = []
    print(f"\n{'='*60}")
    print(f"BMS Simulation  |  {n_cells}S pack  |  Q={DEFAULT_CELL.nominal_capacity_ah} Ah")
    print(f"{'='*60}")
    _print_header()

    # ----------------------------------------------------------------
    # Phase 1: CC-CV Charge
    # ----------------------------------------------------------------
    charge_i = DEFAULT_CELL.i_max_charge   # negative
    in_cv = False
    cv_start_t = 0.0

    for tick in range(charge_duration_s):
        t = tick * dt

        if not in_cv:
            charge_current = charge_i
        else:
            # Simulate charger tapering in CV phase
            elapsed_cv = t - cv_start_t
            charge_current = charge_i * np.exp(-elapsed_cv / 600.0)
            if abs(charge_current) < abs(DEFAULT_CELL.i_cv_term):
                break

        state = bms.step(
            current=charge_current,
            dt=dt,
            charge_requested=True,
            discharge_requested=False,
        )
        history.append(state)
        _print_row(state, interval=300)

        # Detect CC→CV transition
        if not in_cv and max(state.cell_voltages_v) >= DEFAULT_CELL.v_max:
            in_cv = True
            cv_start_t = t

        if state.pack_soc_mean >= 0.95:
            break

    print(f"\n-- Charge complete  SOC={history[-1].pack_soc_mean*100:.1f}%  V={history[-1].pack_voltage_v:.2f} V")

    # ----------------------------------------------------------------
    # Phase 2: Passive Balancing (idle, low current)
    # ----------------------------------------------------------------
    for tick in range(600):
        state = bms.step(current=0.0, dt=dt, charge_requested=False, discharge_requested=False)
        history.append(state)
        _print_row(state, interval=120)
        if state.balancing.v_spread < 0.003:
            break

    print(f"-- Balancing done  ΔV={history[-1].balancing.v_spread*1000:.1f} mV")

    # ----------------------------------------------------------------
    # Phase 3: Constant-Current Discharge
    # ----------------------------------------------------------------
    for tick in range(discharge_duration_s):
        state = bms.step(
            current=discharge_current_a,
            dt=dt,
            charge_requested=False,
            discharge_requested=True,
        )
        history.append(state)
        _print_row(state, interval=300)
        if state.pack_soc_mean <= 0.05 or state.fault_active:
            break

    print(f"-- Discharge done  SOC={history[-1].pack_soc_mean*100:.1f}%")
    print(f"   SOH_Q={history[-1].soh.soh_capacity_pct:.2f}%  R0_est={history[-1].soh.r0_estimate*1000:.2f} mΩ\n")

    if plot:
        _plot_results(history)

    return history


def _plot_results(history: List[BMSPackState]):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("matplotlib not installed — skipping plots.")
        return

    t = [s.timestamp_s for s in history]
    soc = [s.pack_soc_mean * 100 for s in history]
    v_pack = [s.pack_voltage_v for s in history]
    current = [s.pack_current_a for s in history]
    t_max = [s.pack_temp_max_c for s in history]
    v_spread = [s.balancing.v_spread * 1000 for s in history]
    soh_q = [s.soh.soh_capacity_pct for s in history]

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle("BMS Simulation Results", fontsize=14, fontweight="bold")
    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)

    axes = [
        (gs[0, 0], t, soc, "SOC (%)", "State of Charge"),
        (gs[0, 1], t, v_pack, "Pack Voltage (V)", "Pack Voltage"),
        (gs[1, 0], t, current, "Current (A)", "Pack Current  (+ve=discharge)"),
        (gs[1, 1], t, t_max, "Temperature (°C)", "Max Cell Temperature"),
        (gs[2, 0], t, v_spread, "Voltage Spread (mV)", "Cell Voltage Imbalance"),
        (gs[2, 1], t, soh_q, "SOH (%)", "Capacity State of Health"),
    ]

    for spec, x, y, ylabel, title in axes:
        ax = fig.add_subplot(spec)
        ax.plot(x, y, linewidth=1.2)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

    os.makedirs("reports", exist_ok=True)
    out_path = "reports/bms_simulation.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {out_path}")
    plt.close()


# ------------------------------------------------------------------
# CLI entry-point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BMS desktop simulation")
    parser.add_argument("--cells", type=int, default=16, help="Number of series cells")
    parser.add_argument("--soc-init", type=float, default=0.20, help="Initial SOC [0–1]")
    parser.add_argument("--dt", type=float, default=1.0, help="Time step [s]")
    parser.add_argument("--plot", action="store_true", help="Save simulation plots")
    args = parser.parse_args()

    run_simulation(
        n_cells=args.cells,
        soc_init=args.soc_init,
        dt=args.dt,
        plot=args.plot,
    )


if __name__ == "__main__":
    main()
