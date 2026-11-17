"""Command-line entry point for ``python -m bms.simulation``."""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from ..vehicles import TWO_WHEELER, ELECTRIC_BUS
from .charge_discharge import simulate_two_wheeler, simulate_four_wheeler_retrofit, simulate_electric_bus
from .cold import simulate_cold_temperature
from .degradation import simulate_degradation
from .driving import simulate_driving_degradation
from .manufacturers import simulate_manufacturer_comparison
from .report import print_comparison_table, _plot


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

VEHICLE_MAP = {
    "2W": simulate_two_wheeler,
    "4W_RETRO": simulate_four_wheeler_retrofit,
    "BUS": simulate_electric_bus,
}


def _run_datasets_validation() -> None:
    """Validate the BMS model against the (synthetic-equivalent) Kaggle datasets."""
    from ..datasets import load_all_synthetic, validate_bms_model, print_validation_report
    print("\n  Generating synthetic Kaggle dataset equivalents...")
    datasets = load_all_synthetic()
    print(f"  Datasets ready: {list(datasets.keys())}")
    for name, df in datasets.items():
        print(f"    {name:<25} {len(df):>8,} rows  {list(df.columns)}")
    results = validate_bms_model(datasets)
    print_validation_report(results)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="BMS multi-vehicle simulation")
    parser.add_argument("--vehicle", choices=list(VEHICLE_MAP.keys()),
                        help="Run only this vehicle class (default: all)")
    parser.add_argument("--plot", action="store_true", help="Save comparison plot")
    parser.add_argument("--degradation", action="store_true",
                        help="Run degradation simulation (capacity/resistance fade over 300 cycles)")
    parser.add_argument("--cold", action="store_true",
                        help="Run cold-temperature discharge sweep (+25 to −30°C)")
    parser.add_argument("--driving", action="store_true",
                        help="Run driving-conditions degradation projection (10-year SOH table)")
    parser.add_argument("--manufacturers", action="store_true",
                        help="Ather / Ola / Tesla / BYD pack specs and degradation comparison")
    parser.add_argument("--datasets", action="store_true",
                        help="Validate BMS model against 6 Kaggle battery datasets")
    args = parser.parse_args(argv)

    print_comparison_table()

    if args.degradation:
        # Show degradation for 2-wheeler (fast, readable output) and bus (large pack)
        simulate_degradation(TWO_WHEELER, n_cycles=300, deg_rate=0.001)
        simulate_degradation(ELECTRIC_BUS, n_cycles=300, deg_rate=0.0005)
        return

    if args.cold:
        simulate_cold_temperature(TWO_WHEELER)
        simulate_cold_temperature(ELECTRIC_BUS)
        return

    if args.driving:
        simulate_driving_degradation(TWO_WHEELER, simulation_years=10)
        simulate_driving_degradation(ELECTRIC_BUS, simulation_years=10)
        return

    if args.manufacturers:
        simulate_manufacturer_comparison(simulation_years=8)
        return

    if args.datasets:
        _run_datasets_validation()
        return

    if args.vehicle:
        VEHICLE_MAP[args.vehicle]()
    else:
        histories = {}
        histories["2W"]       = simulate_two_wheeler()
        histories["4W_RETRO"] = simulate_four_wheeler_retrofit()
        histories["BUS"]      = simulate_electric_bus()

        if args.plot:
            _plot(histories)
