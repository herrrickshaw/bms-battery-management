"""
BMS multi-vehicle desktop simulation.

Demonstrates the BMS running across three EV classes:
  1. Electric 2-Wheeler  (48V LFP scooter)
  2. Retrofit 4-Wheeler  (72V Lead-Acid, IJAREEIE 2019 paper)
  3. Electric Bus        (409.6V LFP, 150 kW)

Also includes:
  4. Degradation simulation — SOH capacity/resistance fade over N cycles.
  5. Cold-temperature simulation — performance and fault behavior at low temperatures.
  6. Driving conditions simulation — how driving style affects long-term SOH.

Run:
    python -m bms.simulation                  # all three vehicles
    python -m bms.simulation --vehicle 2W     # single vehicle
    python -m bms.simulation --plot           # save plots to reports/
    python -m bms.simulation --degradation    # capacity fade over 300 cycles
    python -m bms.simulation --cold           # cold temperature sweep
    python -m bms.simulation --driving        # driving conditions degradation
    python -m bms.simulation --manufacturers  # Ather/Ola/Tesla/BYD comparison

This used to be a single module; it is now a package split by scenario.  Every
old ``bms.simulation.<name>`` import path is re-exported here.
"""

from __future__ import annotations

from .charge_discharge import (  # noqa: F401  private names kept importable
    _balance_phase, _charge_phase, _discharge_phase, _header, _initial_socs, _row,
    _simulate_charge_discharge, simulate_electric_bus, simulate_four_wheeler_retrofit,
    simulate_two_wheeler,
)
from .cli import VEHICLE_MAP, _run_datasets_validation, main  # noqa: F401
from .cold import ColdCaseResult, run_cold_case, simulate_cold_temperature
from .constants import (
    BALANCED_SPREAD_V, CHARGE_DONE_SOC, COLD_SETTLE_TICK, CV_TAPER_TAU_S,
    DISCHARGE_DONE_SOC, MAX_BALANCE_S,
)
from .degradation import DegradationPoint, project_degradation, simulate_degradation
from .driving import DrivingStressRow, driving_stress_rows, linear_soh_pct, simulate_driving_degradation
from .manufacturers import manufacturer_ageing, simulate_manufacturer_comparison
from .report import _plot, print_comparison_table  # noqa: F401

__all__ = [
    "BALANCED_SPREAD_V", "CHARGE_DONE_SOC", "COLD_SETTLE_TICK", "CV_TAPER_TAU_S",
    "DISCHARGE_DONE_SOC", "MAX_BALANCE_S", "ColdCaseResult", "DegradationPoint",
    "DrivingStressRow", "VEHICLE_MAP", "driving_stress_rows", "linear_soh_pct", "main",
    "manufacturer_ageing", "print_comparison_table", "project_degradation", "run_cold_case",
    "simulate_cold_temperature", "simulate_degradation", "simulate_driving_degradation",
    "simulate_electric_bus", "simulate_four_wheeler_retrofit", "simulate_manufacturer_comparison",
    "simulate_two_wheeler",
]
