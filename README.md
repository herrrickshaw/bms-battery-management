# bms-battery-management

Electric Vehicle Battery Management System (BMS) library — cell-level modeling, state estimation, thermal/power management, and pack-level supervision.

Extracted 2026-07-13 from cross-repo contamination (this package had been accidentally committed inside an unrelated stock-screener repo).

## Modules (`bms/`)

| Module | Responsibility |
|---|---|
| `cell_model.py` | Single-cell electrochemical model, OCV-SOC lookup |
| `chemistries.py` | Chemistry profiles (LFP, NMC, lead-acid, ...) |
| `soc_estimator.py` | Extended Kalman Filter (EKF) state-of-charge estimator |
| `soh_estimator.py` | State-of-health estimation |
| `cell_balancer.py` | Passive/active cell balancing logic |
| `thermal.py` | Thermal management, fan control, fault codes |
| `power_limits.py` | Charge/discharge power-limit calculation |
| `bms_controller.py` | Pack-level BMS controller |
| `supervisor.py` | Supervisory controller — fault codes, alert codes, state machine |
| `driving_profiles.py` | Reference driving-condition profiles |
| `manufacturer_profiles.py` | Reference vehicle/manufacturer profiles |
| `vehicles.py` | Vehicle profile definitions |
| `config.py` | Default cell/pack/EKF configuration constants |
| `simulation.py` | End-to-end simulation entry point (CLI via `argparse`) |

## Install

```bash
pip install -r requirements.txt
```

## Test

```bash
pytest tests/
```

## Related

[`cell-guardian`](https://github.com/herrrickshaw/cell-guardian) (archived) shares this same core engine and additionally has a Kaggle-dataset validation module (`bms/datasets/` — loaders, synthetic-data generation, accuracy checks against 6 public battery datasets) not yet ported here.
