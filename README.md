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
| `datasets/` | Kaggle-dataset validation — synthetic-equivalent generators + accuracy checks (RMSE/MAE/MAPE) against 6 public battery datasets (NASA, degradation, EV charging, RUL, BMS telemetry, distributed BMS) |

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m bms.simulation --vehicle two_wheeler   # single vehicle
python -m bms.simulation --degradation            # capacity/resistance fade over 300 cycles
python -m bms.simulation --datasets               # validate against Kaggle datasets
```

`download_kaggle_datasets.sh` fetches the real Kaggle CSVs (optional —
`--datasets` falls back to synthetic-equivalent data via
`bms/datasets/synthetic.py` if the real files aren't present).
`nasa-battery-life-prediction-dataset-cleaning.ipynb` is the exploratory
notebook the NASA loader/synthetic-generator pair was derived from.

## Test

```bash
pytest tests/
```

## Related

[`cell-guardian`](https://github.com/herrrickshaw/cell-guardian) (archived) shares the same core engine plus the original Kaggle CSVs (576MB, kept there rather than duplicated here) and a data-cleaning notebook variant. `bms/datasets/` here was ported from a stray `working-files` repo, not from cell-guardian directly, but is the same module.
