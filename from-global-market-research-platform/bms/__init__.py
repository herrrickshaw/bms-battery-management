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
bms_controller  Top-level pack controller (integrates all modules)
simulation      Desktop simulation runner
"""

from .bms_controller import BMSController, BMSPackState
from .supervisor import BMSState, FaultCode
from .config import CellConfig, PackConfig, EKFConfig, DEFAULT_CELL, DEFAULT_PACK, DEFAULT_EKF

__all__ = [
    "BMSController",
    "BMSPackState",
    "BMSState",
    "FaultCode",
    "CellConfig",
    "PackConfig",
    "EKFConfig",
    "DEFAULT_CELL",
    "DEFAULT_PACK",
    "DEFAULT_EKF",
]
