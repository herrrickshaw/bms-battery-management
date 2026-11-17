"""Per-second charge/balance/discharge scenarios for the three vehicle classes."""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..bms_controller import BMSController, BMSPackState
from ..vehicles import (
    TWO_WHEELER, FOUR_WHEELER_RETRO, ELECTRIC_BUS,
    VehicleProfile, make_bms_controller,
)
from .constants import (
    BALANCED_SPREAD_V, CHARGE_DONE_SOC, CV_TAPER_TAU_S, DISCHARGE_DONE_SOC, MAX_BALANCE_S,
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


def _initial_socs(profile: VehicleProfile, soc_init: float, spread: float = 0.02) -> List[float]:
    """Per-cell initial SOC with a slight linear spread so balancing is visible."""
    n = profile.n_cells_series
    return [float(np.clip(soc_init + spread * (i / max(n - 1, 1) - 0.5), 0.0, 1.0))
            for i in range(n)]


def _charge_phase(bms: BMSController, profile: VehicleProfile, history: List[BMSPackState],
                  dt: float, charge_s: int, print_interval: int) -> float:
    """CC-CV charge until SOC >= 95 % or the CV taper ends; returns the last time stamp [s]."""
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
            decay = np.exp(-(t - cv_start) / CV_TAPER_TAU_S)
            charge_current = cc_i * decay
            if abs(charge_current) < cv_term:
                break

        state = bms.step(current=charge_current, dt=dt, charge_requested=True)
        history.append(state)
        _row(state, t, print_interval)

        if not in_cv and max(state.cell_voltages_v) >= profile.cell_config.v_max:
            in_cv = True
            cv_start = t
        if state.pack_soc_mean >= CHARGE_DONE_SOC:
            break
    return t


def _balance_phase(bms: BMSController, history: List[BMSPackState], t: float,
                   dt: float, charge_s: int) -> float:
    """Rest at zero current until the cell-voltage spread is below 3 mV (max 300 s)."""
    for _ in range(min(MAX_BALANCE_S, charge_s)):
        t += dt
        state = bms.step(current=0.0, dt=dt)
        history.append(state)
        if state.balancing.v_spread < BALANCED_SPREAD_V:
            break
    return t


def _discharge_phase(bms: BMSController, history: List[BMSPackState], t: float, dt: float,
                     discharge_s: int, discharge_current: float, print_interval: int) -> float:
    """Constant-current discharge until SOC <= 5 % or a fault latches."""
    for _ in range(discharge_s):
        t += dt
        state = bms.step(current=discharge_current, dt=dt, discharge_requested=True)
        history.append(state)
        _row(state, t, print_interval)
        if state.pack_soc_mean <= DISCHARGE_DONE_SOC or state.fault_active:
            break
    return t


def _simulate_charge_discharge(
    profile: VehicleProfile,
    soc_init: float = 0.20,
    dt: float = 1.0,
    charge_s: int = 5400,
    discharge_s: int = 3600,
    discharge_current: Optional[float] = None,
    print_interval: int = 600,
) -> List[BMSPackState]:
    """Run a CC-CV charge, a balancing rest, then a constant-current discharge (1 Hz default)."""
    bms = make_bms_controller(profile, soc_init=_initial_socs(profile, soc_init), ambient_temp_c=25.0)
    history: List[BMSPackState] = []

    _header(profile)

    t = _charge_phase(bms, profile, history, dt, charge_s, print_interval)
    print(f"\n  >> Charge done  SOC={history[-1].pack_soc_mean*100:.1f}%  "
          f"V={history[-1].pack_voltage_v:.1f}V  T={history[-1].pack_temp_max_c:.1f}°C")

    t = _balance_phase(bms, history, t, dt, charge_s)

    if discharge_current is None:
        discharge_current = profile.cell_config.i_max_discharge * profile.n_cells_parallel * 0.5
    _discharge_phase(bms, history, t, dt, discharge_s, discharge_current, print_interval)

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
