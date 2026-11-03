"""Driving-style ageing projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


from ..vehicles import (
    VehicleProfile,
)
from ..driving_profiles import (
    DRIVING_PROFILES, DrivingConditions,
    compute_stress_factors, efc_per_year,
    annual_soh_loss_pct, months_to_eol,
)


# ---------------------------------------------------------------------------
# Driving conditions degradation simulation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DrivingStressRow:
    """Stress / ageing summary for one driving profile."""
    cond: DrivingConditions
    stress_total: float      # combined C-rate x temperature x DoD stress factor
    efc_per_year: float      # equivalent full cycles per year
    annual_loss_pct: float   # SOH loss [% / year]
    eol_months: float        # months until SOH reaches the warning threshold


def driving_stress_rows(
    conditions_list: Sequence[DrivingConditions],
    warn_pct: float,
    base_rate_per_efc: float,
    calendar_aging_pct_year: float,
) -> List[DrivingStressRow]:
    """Pure stress / EOL summary, one row per driving profile."""
    rows = []
    for cond in conditions_list:
        _, _, _, total = compute_stress_factors(cond)
        rows.append(DrivingStressRow(
            cond=cond,
            stress_total=total,
            efc_per_year=efc_per_year(cond),
            annual_loss_pct=annual_soh_loss_pct(base_rate_per_efc, cond, calendar_aging_pct_year),
            eol_months=months_to_eol(warn_pct, base_rate_per_efc, cond, calendar_aging_pct_year),
        ))
    return rows


def linear_soh_pct(annual_loss_pct: float, year: float) -> float:
    """SOH [%] after ``year`` years at a constant ``annual_loss_pct``, floored at 0."""
    return max(0.0, 100.0 - annual_loss_pct * year)


def simulate_driving_degradation(
    profile: VehicleProfile,
    conditions_list=None,
    base_rate_per_efc: float = 1e-4,
    calendar_aging_pct_year: float = 0.5,
    simulation_years: int = 10,
    print_every_years: int = 1,
) -> dict:
    """
    Project SOH evolution under different real-world driving patterns.

    Uses an analytical stress model (no per-second BMS steps) combining:
      - C-rate stress     : f_C  = mean(√C_discharge, √C_charge)
      - Temperature stress: f_T  = 1.5^((T-25)/10) above 25°C; +3%/°C below
      - DoD stress        : f_DoD = DoD²
      - Calendar ageing   : fixed term added regardless of cycling

    Parameters
    ----------
    profile : VehicleProfile
        Pack being evaluated (provides chemistry and SOH thresholds).
    conditions_list : list[DrivingConditions] | None
        Profiles to compare.  Default: all 6 built-in profiles.
    base_rate_per_efc : float
        Degradation fraction per EFC at reference (1C, 25°C, 100% DoD).
        Default 1e-4 (0.01%/EFC) — calibrated so city driving ≈ 1.4%/yr.
    calendar_aging_pct_year : float
        Time-dependent SOH loss [%/yr] regardless of cycling (SEI growth).
    simulation_years : int
        Duration to project [years].
    print_every_years : int
        Row frequency in the SOH-over-time table.

    Returns
    -------
    dict  keyed by profile name → list of (year, soh_pct) tuples.
    """
    if conditions_list is None:
        conditions_list = list(DRIVING_PROFILES.values())

    warn_pct = profile.pack_cfg.soh_warning_pct
    crit_pct = profile.pack_cfg.soh_critical_pct

    print(f"\n{'='*86}")
    print(f"  DRIVING CONDITIONS DEGRADATION — {profile.name}")
    print(f"  Chemistry: {profile.chemistry.symbol}  |  "
          f"base_rate={base_rate_per_efc*100:.4f}%/EFC  |  "
          f"calendar_aging={calendar_aging_pct_year}%/yr  |  "
          f"EOL threshold: SOH={warn_pct}%")
    print(f"{'='*86}")

    # ---- Profile summary table -------------------------------------------
    h = ["Profile", "C-dis", "T(°C)", "DoD%", "FC%", "StressX", "EFC/yr", "EOL(yr)"]
    w = [24, 7, 7, 6, 5, 9, 8, 9]
    fmt = "  " + "  ".join(f"{{:<{x}}}" for x in w)
    print(fmt.format(*h))
    print("  " + "-" * 84)

    results = {}
    for row in driving_stress_rows(conditions_list, warn_pct, base_rate_per_efc, calendar_aging_pct_year):
        cond = row.cond
        eol_str = f"{row.eol_months/12:.1f}" if row.eol_months < 120 * 12 else "Never"
        print(fmt.format(
            cond.name[:24],
            f"{cond.avg_discharge_c_rate:.2f}",
            f"{cond.avg_pack_temp_c:.0f}",
            f"{cond.dod_per_trip*100:.0f}%",
            f"{cond.fast_charge_fraction*100:.0f}%",
            f"{row.stress_total:.3f}×",
            f"{row.efc_per_year:.0f}",
            eol_str,
        ))
        results[cond.name] = {"annual_loss_pct": row.annual_loss_pct, "eol_months": row.eol_months,
                              "soh_by_year": []}

    # ---- SOH-over-time table ---------------------------------------------
    print()
    months_steps = [m for m in range(0, simulation_years * 12 + 1,
                                     max(1, print_every_years * 12))]

    # Header row
    name_width = 6  # "Year"
    col_width = 10
    header_row = f"  {'Year':>{name_width}}" + "".join(
        f"  {c.name[:col_width]:>{col_width}}" for c in conditions_list
    )
    print(header_row)
    print("  " + "-" * (name_width + (col_width + 2) * len(conditions_list) + 2))

    for month in months_steps:
        year = month / 12
        row = f"  {year:>{name_width}.1f}"
        for cond in conditions_list:
            soh = linear_soh_pct(results[cond.name]["annual_loss_pct"], year)
            results[cond.name]["soh_by_year"].append((year, round(soh, 1)))
            marker = ""
            if soh < crit_pct:
                marker = "!"    # critical
            elif soh < warn_pct:
                marker = "~"    # warning
            cell = f"{soh:.1f}{marker}"
            row += f"  {cell:>{col_width}}"
        print(row)

    print(f"\n  Legend: ~ = SOH below warning ({warn_pct}%)   ! = SOH below critical ({crit_pct}%)")

    # ---- Stress factor explanation ----------------------------------------
    print(f"""
  Stress model (per profile):
    f_C   = (√C_discharge + √C_charge_blend) / 2   [C-rate damage]
    f_T   = 1.5^((T−25)/10) if T≥25°C; 1+0.03×(25−T) if T<25°C  [Arrhenius]
    f_DoD = DoD²                                    [volume-change fatigue]
    eff_rate/EFC = base_rate × f_C × f_T × f_DoD
    annual_loss  = eff_rate × EFC/yr × 100%  +  {calendar_aging_pct_year}% calendar

  Interpretation:
    Aggressive driving degrades the pack faster on all three axes simultaneously:
    high C-rate + hot pack + deep DoD. The cold-climate profile shows that
    sub-zero temperatures add a lithium-plating penalty even at modest C-rates.
""")

    return results
