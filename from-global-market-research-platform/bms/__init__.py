"""
BMS — Battery Management System Python package.

Modules
-------
config          Cell / pack / EKF parameters
cell_model      2-RC Thevenin equivalent circuit model
soc_estimator   Extended Kalman Filter SOC estimation
soh_estimator   State-of-Health (capacity & resistance fade)
cell_balancer   Passive cell balancing controller
power_limits    Charge / discharge power limit calculator
supervisor      Supervisory state machine (CCCV, faults, contactors)
thermal         PWM fan / heater thermal management controller
chemistries     LFP / Lead-Acid / NMC chemistry profiles
vehicles        Vehicle presets (2W, 4W, BUS) + factory function
bms_controller  Top-level pack controller (integrates all modules)
simulation      Desktop multi-vehicle simulation runner
"""

from .bms_controller import BMSController, BMSPackState
from .supervisor import BMSState, FaultCode, AlertCode
from .config import CellConfig, PackConfig, EKFConfig, DEFAULT_CELL, DEFAULT_PACK, DEFAULT_EKF
from .chemistries import ChemistryProfile, LFP, LEAD_ACID, NMC, CHEMISTRY_REGISTRY
from .thermal import FanController, ThermalManagementState, FanFaultCode
from .vehicles import (
    VehicleProfile,
    TWO_WHEELER, FOUR_WHEELER_RETRO, FOUR_WHEELER_MODERN, ELECTRIC_BUS,
    VEHICLE_REGISTRY,
    make_bms_controller,
)

__all__ = [
    # Core controller
    "BMSController",
    "BMSPackState",
    # State machine
    "BMSState",
    "FaultCode",
    "AlertCode",
    # Configuration
    "CellConfig",
    "PackConfig",
    "EKFConfig",
    "DEFAULT_CELL",
    "DEFAULT_PACK",
    "DEFAULT_EKF",
    # Chemistries
    "ChemistryProfile",
    "LFP",
    "LEAD_ACID",
    "NMC",
    "CHEMISTRY_REGISTRY",
    # Thermal
    "FanController",
    "ThermalManagementState",
    "FanFaultCode",
    # Vehicles
    "VehicleProfile",
    "TWO_WHEELER",
    "FOUR_WHEELER_RETRO",
    "FOUR_WHEELER_MODERN",
    "ELECTRIC_BUS",
    "VEHICLE_REGISTRY",
    "make_bms_controller",
]
