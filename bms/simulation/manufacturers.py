"""Ather / Ola / Tesla / BYD pack and ageing comparison."""

from __future__ import annotations

from typing import Tuple


from ..vehicles import (
    VehicleProfile,
)
from ..manufacturer_profiles import (
    ATHER_450X, OLA_S1_PRO, TESLA_MODEL3_SR, BYD_HAN_EV,
    ATHER_DRIVING, OLA_DRIVING, TESLA_DRIVING, BYD_DRIVING,
)
from ..driving_profiles import (
    DrivingConditions,
    compute_stress_factors, annual_soh_loss_pct, months_to_eol, soh_at_month,
)


# ---------------------------------------------------------------------------
# Manufacturer comparison
# ---------------------------------------------------------------------------

def manufacturer_ageing(
    vp: VehicleProfile,
    dc: DrivingConditions,
    base_rate_per_efc: float,
    calendar_aging_pct_year: float,
) -> Tuple[float, float, float, float]:
    """Return ``(stress_total, efc_per_year, annual_loss_pct, eol_months)`` for one vehicle."""
    _, _, _, stress = compute_stress_factors(dc)
    efcs = dc.trips_per_day * 365.25 * dc.dod_per_trip
    loss = annual_soh_loss_pct(base_rate_per_efc, dc, calendar_aging_pct_year)
    eol_m = months_to_eol(vp.pack_cfg.soh_warning_pct, base_rate_per_efc, dc, calendar_aging_pct_year)
    return stress, efcs, loss, eol_m


_VEHICLES = {
    "Ather 450X":  (ATHER_450X,      ATHER_DRIVING),
    "Ola S1 Pro":  (OLA_S1_PRO,       OLA_DRIVING),
    "Tesla M3 SR": (TESLA_MODEL3_SR,  TESLA_DRIVING),
    "BYD Han EV":  (BYD_HAN_EV,      BYD_DRIVING),
}


def _print_pack_specs(vehicles: dict) -> None:
    """Print the title banner and the pack-spec table."""
    print(f"\n{'='*90}")
    print("  MANUFACTURER BMS COMPARISON — Ather · Ola Electric · Tesla · BYD")
    print(f"{'='*90}")

    headers = ["Vehicle", "Chemistry", "Pack", "Voltage", "Energy", "Motor", "Cooling", "Charge"]
    rows = []
    for name, (vp, _) in vehicles.items():
        rows.append([
            name,
            vp.chemistry.symbol,
            f"{vp.n_cells_series}S{vp.n_cells_parallel}P",
            f"{vp.nominal_pack_voltage_v:.0f} V",
            f"{vp.nominal_pack_energy_kwh:.1f} kWh",
            f"{vp.motor_power_kw:.0f} kW",
            "Active" if vp.has_active_cooling else "Passive",
            f"{vp.charging_stages}-stage",
        ])
    col_w = [14, 10, 10, 9, 10, 9, 9, 9]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_w)
    print(fmt.format(*headers))
    print("  " + "-" * 88)
    for r in rows:
        print(fmt.format(*r))


def _print_driving_stress(vehicles: dict, base_rate_per_efc: float,
                          calendar_aging_pct_year: float) -> dict:
    """Print the driving-stress table; return per-vehicle results (empty SOH series)."""
    print(f"\n  Typical driving conditions & degradation stress (base_rate={base_rate_per_efc*100:.4f}%/EFC):")
    h2 = ["Vehicle", "Driving scenario", "C-dis", "T_pack", "DoD%", "FC%", "Stress×", "EFC/yr", "EOL(yr)"]
    w2 = [14, 32, 7, 7, 6, 5, 9, 8, 9]
    fmt2 = "  " + "  ".join(f"{{:<{w}}}" for w in w2)
    print(fmt2.format(*h2))
    print("  " + "-" * 106)

    results = {}
    for name, (vp, dc) in vehicles.items():
        stress, efcs, loss, eol_m = manufacturer_ageing(vp, dc, base_rate_per_efc, calendar_aging_pct_year)
        eol_str = f"{eol_m/12:.1f}" if eol_m < 200 * 12 else "∞"
        print(fmt2.format(
            name, dc.description[:32],
            f"{dc.avg_discharge_c_rate:.2f}", f"{dc.avg_pack_temp_c:.0f}°C",
            f"{dc.dod_per_trip*100:.0f}%", f"{dc.fast_charge_fraction*100:.0f}%",
            f"{stress:.3f}×", f"{efcs:.0f}", eol_str,
        ))
        results[name] = {
            "profile": vp,
            "driving": dc,
            "annual_loss_pct": loss,
            "eol_months": eol_m,
            "soh_by_year": [],
        }
    return results


def _print_soh_projection(vehicles: dict, results: dict, base_rate_per_efc: float,
                          calendar_aging_pct_year: float, simulation_years: int) -> None:
    """Print projected SOH per year and append (year, soh) points to ``results``."""
    print(f"\n  Projected SOH (%) over {simulation_years} years:")
    col = 13
    header_row = f"  {'Year':>6}" + "".join(f"  {n:>{col}}" for n in vehicles)
    print(header_row)
    print("  " + "-" * (8 + (col + 2) * len(vehicles)))

    for yr in range(simulation_years + 1):
        row = f"  {yr:>6}"
        for name, (vp, dc) in vehicles.items():
            soh = soh_at_month(yr * 12, base_rate_per_efc, dc, calendar_aging_pct_year)
            results[name]["soh_by_year"].append((yr, round(soh, 1)))
            warn = vp.pack_cfg.soh_warning_pct
            crit = vp.pack_cfg.soh_critical_pct
            marker = "!" if soh < crit else ("~" if soh < warn else "")
            cell = f"{soh:.1f}{marker}"
            row += f"  {cell:>{col}}"
        print(row)


def _print_differentiators() -> None:
    """Print the legend and the per-manufacturer notes."""
    print("\n  ~ = SOH below warning threshold   ! = below critical threshold")
    print("\n  Key BMS differentiators:")
    print("    Ather 450X  : Cloud-connected ADS; warp/eco modes; air-cooled (hot pack)")
    print("    Ola S1 Pro  : MoveOS 4; liquid cooling reduces pack temp vs Ather")
    print("    Tesla M3 SR : Octovalve thermal; Supercharger V3 (2.8C); trip planning")
    print("    BYD Han EV  : Cell-to-Body (CTB); nail-test safe; 120 kW DC; heat pump\n")


def simulate_manufacturer_comparison(
    base_rate_per_efc: float = 1e-4,
    calendar_aging_pct_year: float = 0.5,
    simulation_years: int = 8,
) -> dict:
    """
    Side-by-side BMS and degradation comparison for Ather, Ola, Tesla, and BYD.

    Uses manufacturer-specific driving conditions that reflect each vehicle's
    target market, typical usage pattern, and cooling system capability.

    Parameters
    ----------
    base_rate_per_efc : float
        Base degradation rate at reference conditions (1C, 25°C, 100% DoD).
    calendar_aging_pct_year : float
        Calendar SOH loss [%/yr].
    simulation_years : int
        Projection horizon [years].

    Returns
    -------
    dict keyed by short name → {profile, driving_cond, soh_by_year, eol_months}.
    """
    vehicles = _VEHICLES
    _print_pack_specs(vehicles)
    results = _print_driving_stress(vehicles, base_rate_per_efc, calendar_aging_pct_year)
    _print_soh_projection(vehicles, results, base_rate_per_efc, calendar_aging_pct_year, simulation_years)
    _print_differentiators()
    return results
