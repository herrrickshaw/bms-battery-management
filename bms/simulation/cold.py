"""Cold-temperature discharge sweep."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from .constants import COLD_SETTLE_TICK, DISCHARGE_DONE_SOC


from ..vehicles import (
    VehicleProfile, make_bms_controller,
)


# ---------------------------------------------------------------------------
# Cold-temperature simulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColdCaseResult:
    """Outcome of one constant-current discharge at a fixed ambient temperature."""
    t_start: float       # initial cell temperature [deg C]
    t_peak: float        # peak pack temperature [deg C]
    soc_final: float     # mean SOC at the end [0-1]
    ah_out: float        # charge removed [Ah]
    dis_blocked: bool    # discharge power limit ~0 at the settle tick
    chg_blocked: bool    # charge power limit ~0 at the settle tick
    fault: str           # latched fault name or "-"


def run_cold_case(
    profile: VehicleProfile,
    t_amb: float,
    discharge_current: float,
    max_discharge_s: int,
    soc_init: float,
) -> ColdCaseResult:
    """Discharge ``profile`` at ``discharge_current`` [A] from ``t_amb`` [deg C] until SOC/fault/timeout."""
    bms = make_bms_controller(profile, soc_init=soc_init, ambient_temp_c=t_amb)
    t_peak = t_amb
    fault_str = "-"
    ah_out = 0.0
    soc_final = soc_init
    dis_blocked = False
    chg_blocked = False

    for tick in range(max_discharge_s):
        state = bms.step(current=discharge_current, dt=1.0, discharge_requested=True)
        t_peak = max(t_peak, state.pack_temp_max_c)

        # Check power limits at first discharging step
        if tick == COLD_SETTLE_TICK:  # after INIT+PRECHARGE settle
            if state.power_limits.i_max_discharge < 1.0:
                dis_blocked = True
            if state.power_limits.i_max_charge > -1.0:
                chg_blocked = True

        if state.fault_active:
            fault_str = state.fault_description
            soc_final = state.pack_soc_mean
            ah_out += discharge_current / 3600.0
            break

        if state.pack_soc_mean <= DISCHARGE_DONE_SOC:
            soc_final = state.pack_soc_mean
            ah_out += discharge_current / 3600.0
            break

        soc_final = state.pack_soc_mean
        ah_out += discharge_current / 3600.0

    return ColdCaseResult(t_amb, t_peak, soc_final, ah_out, dis_blocked, chg_blocked, fault_str)


def simulate_cold_temperature(
    profile: VehicleProfile,
    ambient_temps_c: List[float] = None,
    discharge_current: float = None,
    max_discharge_s: int = 1800,
    soc_init: float = 0.80,
) -> dict:
    """
    Compare discharge performance and fault behavior at different ambient temperatures.

    Shows three key cold-temperature effects:
    1. Reduced power limits (PowerLimitsCalculator blocks charge/discharge below t_min).
    2. Increased cell resistance at low temperatures (cell model thermal derating).
    3. BMS fault when temperature is below t_min_discharge (UNDER_TEMPERATURE).

    Parameters
    ----------
    profile : VehicleProfile
        Pack to test.
    ambient_temps_c : list[float]
        Ambient temperatures to sweep (°C).  Default: [25, 5, -10, -20, -30].
    discharge_current : float
        Pack discharge current [A].  Default: 30% of max discharge current.
    max_discharge_s : int
        Maximum simulation duration per temperature [s].
    soc_init : float
        Initial SOC for all runs.

    Returns
    -------
    dict  keyed by ambient temperature.
    """
    if ambient_temps_c is None:
        ambient_temps_c = [25.0, 5.0, -10.0, -20.0, -30.0]
    if discharge_current is None:
        discharge_current = profile.cell_config.i_max_discharge * profile.n_cells_parallel * 0.30

    cell = profile.cell_config
    t_min_dis = cell.t_min_discharge
    t_min_chg = cell.t_min_charge

    print(f"\n{'='*80}")
    print(f"  COLD TEMPERATURE SIMULATION — {profile.name}")
    print(f"  Chemistry: {profile.chemistry.symbol}  |  I_discharge={discharge_current:.0f} A  |  SOC_init={soc_init*100:.0f}%")
    print(f"  t_min_discharge={t_min_dis}°C  |  t_min_charge={t_min_chg}°C")
    print(f"{'='*80}")

    headers = ["T_amb(°C)", "T_start(°C)", "T_peak(°C)", "SOC_f%", "Ah_out",
               "DchgBlocked", "ChgBlocked", "Fault"]
    print(f"  {'|'.join(f'{h:>11}' for h in headers)}")
    print("  " + "-" * (12 * len(headers)))

    results = {}

    for t_amb in ambient_temps_c:
        r = run_cold_case(profile, t_amb, discharge_current, max_discharge_s, soc_init)
        cols = [
            f"{t_amb:>11.1f}",
            f"{r.t_start:>11.1f}",
            f"{r.t_peak:>11.1f}",
            f"{r.soc_final*100:>11.1f}",
            f"{r.ah_out:>11.1f}",
            f"{'YES' if r.dis_blocked else 'no':>11}",
            f"{'YES' if r.chg_blocked else 'no':>11}",
            f"{r.fault:>11}",
        ]
        print("  " + "|".join(cols))

        results[t_amb] = {
            "t_amb_c": t_amb,
            "t_peak_c": round(r.t_peak, 1),
            "soc_final": round(r.soc_final, 3),
            "ah_out": round(r.ah_out, 1),
            "discharge_blocked": r.dis_blocked,
            "charge_blocked": r.chg_blocked,
            "fault": r.fault,
        }

    print(f"\n  Note: BMS faults at cell T < {t_min_dis}°C (discharge) / T < {t_min_chg}°C (charge).")
    print("  'DchgBlocked': PowerLimits sets i_max_discharge=0 at t_min_discharge threshold.")
    print("  'ChgBlocked' : PowerLimits sets i_max_charge=0 at t_min_charge threshold.")
    print(f"  Resistance increases ~0.5%/°C below t_nominal={cell.t_nominal}°C → more voltage sag.\n")

    return results
