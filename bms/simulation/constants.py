"""Simulation constants shared by the scenario modules."""


CV_TAPER_TAU_S = 1200.0       # exponential CV-phase current decay time constant [s]
CHARGE_DONE_SOC = 0.95        # stop charging at this mean SOC [0-1]
DISCHARGE_DONE_SOC = 0.05     # stop discharging at this mean SOC [0-1]
MAX_BALANCE_S = 300           # maximum balancing rest [s]
BALANCED_SPREAD_V = 0.003     # cell-voltage spread considered balanced [V]
COLD_SETTLE_TICK = 7          # step index after INIT+PRECHARGE at which limits are sampled
