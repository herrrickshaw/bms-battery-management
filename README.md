# EV Battery Management System (BMS) library

A pure-Python/NumPy library for modelling an electric-vehicle battery pack: 2-RC Thevenin cell models, an Extended Kalman Filter state-of-charge (SOC) estimator, state-of-health (SOH) tracking, passive cell balancing, thermal and power-limit logic, and a supervisory state machine. It ships vehicle and manufacturer presets (scooter, retrofit lead-acid car, compact LFP car, bus; Ather 450X, Ola S1 Pro, Tesla Model 3 SR, BYD Han) and a simulation CLI that prints charge/discharge, degradation, cold-temperature and driving-style ageing tables.

> Status: maintained, research/educational. Extracted on 2026-07-13 from an unrelated stock-screener repo where it had been committed by mistake. Manufacturer parameters are estimates derived from published specifications, not OEM data; not for use on real batteries.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/herrrickshaw/bms-battery-management/blob/main/notebooks/colab_test.ipynb)
New to the repo? See [HOW_TO_USE_WITH_AI.md](HOW_TO_USE_WITH_AI.md).

## What it does
- Simulates a 1 Hz CC-CV charge, balancing rest and constant-current discharge for 2W, 4W (retrofit lead-acid / compact LFP) and bus packs (`BMSController.step`).
- Estimates per-cell SOC with an EKF on a 2-RC equivalent-circuit model (`soc_estimator.py`, `cell_model.py`).
- Projects capacity and resistance fade, cold-temperature behaviour (+25 to -30 C) and 10-year SOH under six driving profiles.
- Compares Ather / Ola / Tesla / BYD pack specs and projected ageing.
- Provides eight chemistry profiles: LFP, lead-acid, NMC, Na-ion, LMFP, LTO, Li-S, solid-state NMC.
- Validates the model against synthetic equivalents of six public Kaggle battery datasets (RMSE / MAE / MAPE).

## Quick start
```bash
git clone https://github.com/herrrickshaw/bms-battery-management.git
cd bms-battery-management
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bms.simulation --vehicle 2W        # one vehicle class: 2W | 4W_RETRO | BUS
```
Other flags: `--degradation`, `--cold`, `--driving`, `--manufacturers`, `--datasets`, `--plot` (needs matplotlib; writes `reports/bms_multi_vehicle.png`). With no flag, all three vehicle classes run (the 8-hour lead-acid case takes several minutes).

## How it works
`BMSController.step(current, dt)` advances one control cycle:

| Stage | Module | Output |
|---|---|---|
| Cell physics (2-RC Thevenin, OCV-SOC table) | `cell_model.py`, `chemistries.py` | terminal voltage, temperature |
| SOC estimation (EKF per cell) | `soc_estimator.py` | SOC estimate |
| SOH (capacity / R0 fade) | `soh_estimator.py` | `SOHState` |
| Passive balancing | `cell_balancer.py` | bypass currents, voltage spread |
| Power limits (SOC, temperature, SOH derating) | `power_limits.py` | charge/discharge limits |
| Supervisory state machine (CC-CV-float, faults, alerts) | `supervisor.py` | contactor / enable flags |
| Fan / heater PWM | `thermal.py` | `ThermalManagementState` |

Presets live in `vehicles.py` and `manufacturer_profiles.py` (both build chemistries via `with_cell_config`). `simulation/` (a package; `python -m bms.simulation` is unchanged) keeps computation in pure functions (`project_degradation`, `run_cold_case`, `driving_stress_rows`, `manufacturer_ageing`) and prints tables on top.

## Repository layout
| Path | Purpose |
|---|---|
| `bms/` | The library: cell model, estimators, balancer, thermal, power limits, supervisor, controller |
| `bms/vehicles.py`, `bms/manufacturer_profiles.py`, `bms/driving_profiles.py` | Vehicle presets, OEM presets, driving-stress ageing model |
| `bms/simulation/` | CLI (`python -m bms.simulation`) |
| `bms/datasets/` | Synthetic dataset generators, loaders and accuracy validation |
| `tests/` | Unit tests plus bit-identical characterisation tests (`tests/golden/baseline.json`) |
| `download_kaggle_datasets.sh` | Optional: fetches the real Kaggle CSVs (needs your own Kaggle credentials) |
| `nasa-battery-life-prediction-dataset-cleaning.ipynb`, `notebooks/` | Exploratory / Colab notebooks |
| `from-global-market-research-platform/` | Stale snapshot of the original extraction; superseded by `bms/` (see Limitations) |

## Data sources
| Source | What is taken | Access route | Licence / caveat |
|---|---|---|---|
| Six public Kaggle battery datasets (NASA, degradation, EV charging, RUL, BMS telemetry, distributed BMS) | Real CSVs, optional | `download_kaggle_datasets.sh` (user's own Kaggle token) | Kaggle dataset licences apply; not redistributed here |
| Published OEM specifications (Ather, Ola, Tesla, BYD) and IJAREEIE Vol. 8 Issue 4 (2019) | Pack topology and rough parameters | Transcribed into `manufacturer_profiles.py` / `vehicles.py` | Estimates only |

`--datasets` runs on seeded synthetic equivalents (`bms/datasets/synthetic.py`) when the real files are absent.

## Configuration
No environment variables. Cell, pack and EKF defaults are dataclasses in `bms/config.py`; simulation constants (CV taper time constant, SOC cut-offs) are named at the top of `bms/simulation/constants.py`. Kaggle credentials (`~/.kaggle/kaggle.json`) are only needed for the optional download script and are never committed.

## Testing
```bash
pip install -r requirements.txt
ruff check .
pytest -q          # ~140 tests, ~30 s
```
`tests/test_characterisation.py` hashes the console output and the `float.hex()` of every numeric result against digests captured from the pre-refactor code, so any change to estimator equations or parameters fails loudly. Regenerate with `python tests/characterise.py` only for an intended behaviour change.

## Limitations and known issues
- Parameters are estimates; OCV tables and RC values are not validated against cell-level test data.
- Degradation and driving-ageing projections are analytical, accelerated demo models, not lifetime predictions.
- `from-global-market-research-platform/` is an older copy of the package (it lacks the `--datasets` flag); it is not imported by anything and is kept only to avoid deleting history-referenced files.
- `fix_and_push_kaggle.sh` is a leftover maintenance helper that checks out a hard-coded branch name; review before running.
- `requirements.txt` previously omitted `pandas`, which `bms/datasets/` needs.

## Related repositories
[`cell-guardian`](https://github.com/herrrickshaw/cell-guardian) (archived) shares the same core engine plus the original Kaggle CSVs (576 MB, kept there rather than duplicated here). [`ev-battery-management-sim`](https://github.com/herrrickshaw/ev-battery-management-sim) is a sibling simulation repo. `bms/datasets/` here was ported from a stray `working-files` repo, not directly from cell-guardian.

## Licence
No licence file yet — all rights reserved.
