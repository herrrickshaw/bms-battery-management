"""
Battery chemistry profiles: OCV-SOC lookup tables and cell parameter presets.

Supported chemistries
---------------------
LFP  — LiFePO4: flat OCV plateau, long cycle life, safe  (EKF critical)
PbA  — Lead-Acid: mature, cheap, high self-discharge     (retrofit EVs)
NMC  — Li(NiMnCo)O2: high energy density, cars & buses  (steep OCV curve)

Usage
-----
    from bms.chemistries import LFP, LEAD_ACID, NMC
    cell = CellModel(config=LFP.cell_config, ocv_table=LFP.ocv_table)
"""

from dataclasses import dataclass
import numpy as np
from .config import CellConfig


@dataclass(frozen=True)
class ChemistryProfile:
    name: str
    symbol: str
    ocv_table: np.ndarray           # [SOC, OCV_per_cell]
    cell_config: CellConfig
    self_discharge_pct_month: float # %/month
    charge_efficiency: float        # round-trip fraction (0–1)
    float_voltage_v: float          # Stage-3 float charge voltage per cell
    description: str


# ---------------------------------------------------------------------------
# LiFePO4 (LFP) — used in modern 2-wheelers, 4-wheelers, buses
# ---------------------------------------------------------------------------
_LFP_OCV = np.array([
    [0.00, 2.500],
    [0.05, 3.000],
    [0.10, 3.120],
    [0.20, 3.180],
    [0.30, 3.210],
    [0.40, 3.230],
    [0.50, 3.240],
    [0.60, 3.250],
    [0.70, 3.260],
    [0.80, 3.280],
    [0.90, 3.320],
    [0.95, 3.400],
    [1.00, 3.650],
])

_LFP_CELL = CellConfig(
    nominal_capacity_ah=100.0,
    soc_min=0.05, soc_max=0.95,
    v_nominal=3.20, v_max=3.65, v_min=2.50,
    r0=0.002, r1=0.001, c1=3000.0, r2=0.002, c2=30000.0,
    i_max_charge=-50.0, i_max_discharge=200.0,
    i_cc_charge=-50.0, i_cv_term=-5.0,
    t_max_charge=45.0, t_min_charge=0.0,
    t_max_discharge=60.0, t_min_discharge=-20.0,
    t_nominal=25.0,
    thermal_capacity_j_k=1500.0, thermal_resistance_k_w=5.0,
)

LFP = ChemistryProfile(
    name="Lithium Iron Phosphate",
    symbol="LFP",
    ocv_table=_LFP_OCV,
    cell_config=_LFP_CELL,
    self_discharge_pct_month=2.0,
    charge_efficiency=0.97,
    float_voltage_v=3.40,
    description="Safe, long-cycle-life LFP. Flat OCV needs EKF for accurate SOC.",
)


# ---------------------------------------------------------------------------
# Lead-Acid (PbA) — used in retrofit EVs (IJAREEIE paper: 72V, 130Ah pack)
#
# Pack from paper: 6 × 12 V modules = 72 V, each module = 6 cells × 2 V
# Total cells: 36 cells × 2 V = 72 V.
# Charging: 3-stage (CC bulk → CV absorption → Float)
# Optimum operating: 25–33 °C; dangerous above 50 °C
# ---------------------------------------------------------------------------
_PBA_OCV = np.array([
    [0.00, 1.750],   # severely over-discharged
    [0.10, 1.870],
    [0.20, 1.920],
    [0.30, 1.960],
    [0.40, 1.980],
    [0.50, 2.000],   # nominal
    [0.60, 2.020],
    [0.70, 2.060],
    [0.80, 2.100],
    [0.90, 2.150],
    [0.95, 2.200],
    [1.00, 2.300],   # open-circuit fully charged
])

_PBA_CELL = CellConfig(
    nominal_capacity_ah=130.0,          # per IJAREEIE paper
    soc_min=0.20, soc_max=0.95,         # lead-acid shouldn't go below 20 %
    v_nominal=2.00, v_max=2.40, v_min=1.75,
    # Internal resistance for a large 130 Ah VRLA cell is low (~1-2 mΩ).
    # Values scale inversely with capacity: small cells have higher R.
    r0=0.001, r1=0.001, c1=5000.0,
    r2=0.001, c2=100000.0,
    i_max_charge=-10.0,                 # charger in paper: 0 to 10 A
    i_max_discharge=130.0,              # 1 C
    i_cc_charge=-10.0,                  # CC charge current
    i_cv_term=-1.0,                     # ~0.01 C float threshold
    t_max_charge=40.0,                  # paper: below 40 °C
    t_min_charge=10.0,                  # paper: 10–50 °C range
    t_max_discharge=50.0,               # paper: 50 °C is dangerous
    t_min_discharge=0.0,
    t_nominal=29.0,                     # paper: 25–33 °C optimum, mid = 29
    thermal_capacity_j_k=4000.0,        # lead-acid is thermally massive
    thermal_resistance_k_w=3.0,
)

LEAD_ACID = ChemistryProfile(
    name="Lead-Acid (VRLA)",
    symbol="PbA",
    ocv_table=_PBA_OCV,
    cell_config=_PBA_CELL,
    self_discharge_pct_month=10.0,      # 3–20 %, mid-range per paper
    charge_efficiency=0.72,             # 50–95 %, conservative
    float_voltage_v=2.27,               # standard float ~2.25–2.30 V/cell
    description=(
        "Lead-acid 2V cells. 3-stage CC→Topping→Float charging. "
        "Retrofit EV pack from IJAREEIE paper: 36S × 2V = 72V, 130Ah."
    ),
)


# ---------------------------------------------------------------------------
# NMC (Li(NiMnCo)O2) — higher energy density, used in premium 4-wheelers
# ---------------------------------------------------------------------------
_NMC_OCV = np.array([
    [0.00, 3.000],
    [0.05, 3.420],
    [0.10, 3.500],
    [0.20, 3.620],
    [0.30, 3.680],
    [0.40, 3.730],
    [0.50, 3.780],
    [0.60, 3.840],
    [0.70, 3.920],
    [0.80, 4.010],
    [0.90, 4.100],
    [0.95, 4.160],
    [1.00, 4.200],
])

_NMC_CELL = CellConfig(
    nominal_capacity_ah=60.0,
    soc_min=0.05, soc_max=0.95,
    v_nominal=3.70, v_max=4.20, v_min=3.00,
    r0=0.002, r1=0.001, c1=2000.0, r2=0.003, c2=20000.0,
    i_max_charge=-60.0,                 # 1 C
    i_max_discharge=300.0,              # 5 C peak
    i_cc_charge=-60.0,
    i_cv_term=-3.0,                     # 0.05 C
    t_max_charge=45.0, t_min_charge=0.0,
    t_max_discharge=60.0, t_min_discharge=-20.0,
    t_nominal=25.0,
    thermal_capacity_j_k=1200.0, thermal_resistance_k_w=4.0,
)

NMC = ChemistryProfile(
    name="Lithium Nickel Manganese Cobalt Oxide",
    symbol="NMC",
    ocv_table=_NMC_OCV,
    cell_config=_NMC_CELL,
    self_discharge_pct_month=1.5,
    charge_efficiency=0.98,
    float_voltage_v=3.90,
    description="High energy density NMC. Steep OCV aids SOC estimation. Premium EVs.",
)

# Registry for easy lookup
CHEMISTRY_REGISTRY = {
    "LFP": LFP,
    "PbA": LEAD_ACID,
    "NMC": NMC,
}
