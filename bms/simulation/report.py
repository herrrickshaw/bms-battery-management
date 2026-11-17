"""Static comparison table and matplotlib plot."""

from __future__ import annotations

import os




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

  Supported chemistries (bms.chemistries):
    Established : LFP · Lead-Acid (PbA) · NMC
    Emerging    : Na-Ion · LMFP · LTO · Li-Sulfur · Solid-State NMC

  Lifecycle simulations (--degradation / --cold / --driving):
    Degradation : Capacity fade + R0 growth model over N cycles (Wöhler model)
    Cold temp   : Discharge performance and BMS fault sweep from +25°C to −30°C
    Driving     : SOH projection for 6 real-world driving patterns over 10 years
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
