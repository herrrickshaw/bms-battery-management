"""
Loaders for real Kaggle battery datasets.

Download instructions
---------------------
Install Kaggle CLI and run from the repo root:

    pip install kaggle
    # Place kaggle.json (from kaggle.com → Account → API Token) in ~/.kaggle/

    mkdir -p data/kaggle
    kaggle datasets download patrickfleith/nasa-battery-dataset         -p data/kaggle/nasa         --unzip
    kaggle datasets download programmer3/lithium-ion-battery-degradation-dataset -p data/kaggle/degradation --unzip
    kaggle datasets download ziya07/ev-battery-charging-data            -p data/kaggle/ev_charging  --unzip
    kaggle datasets download ignaciovinuales/battery-remaining-useful-life-rul   -p data/kaggle/rul         --unzip
    kaggle datasets download akhileshdkapse/version21-bms-dataset       -p data/kaggle/bms_v21      --unzip
    kaggle datasets download micamadi/synthetic-distributed-battery-management-system -p data/kaggle/dist_bms --unzip

Each loader below finds the CSV automatically under its directory.
Falls back to the synthetic generator if the directory does not exist.
"""

import os
import glob
import pandas as pd
from typing import Optional
from .synthetic import (
    generate_nasa_battery,
    generate_degradation,
    generate_ev_charging,
    generate_rul_features,
    generate_bms_telemetry,
    generate_distributed_bms,
)

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "kaggle")


def _first_csv(directory: str) -> Optional[str]:
    """Return the first CSV file found recursively in `directory`."""
    hits = glob.glob(os.path.join(directory, "**", "*.csv"), recursive=True)
    return hits[0] if hits else None


def load_nasa(directory: str = os.path.join(_BASE, "nasa")) -> pd.DataFrame:
    """
    Load the NASA battery dataset.
    Falls back to synthetic if the directory does not exist.
    """
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [nasa] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [nasa] real data not found — using synthetic (run loaders.py download block)")
    return generate_nasa_battery()


def load_degradation(directory: str = os.path.join(_BASE, "degradation")) -> pd.DataFrame:
    """Load the Li-Ion Degradation dataset (cycle-level summaries)."""
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [degradation] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [degradation] real data not found — using synthetic")
    return generate_degradation()


def load_ev_charging(directory: str = os.path.join(_BASE, "ev_charging")) -> pd.DataFrame:
    """Load the EV Battery Charging dataset."""
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [ev_charging] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [ev_charging] real data not found — using synthetic")
    return generate_ev_charging()


def load_rul(directory: str = os.path.join(_BASE, "rul")) -> pd.DataFrame:
    """Load the Battery RUL feature dataset."""
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [rul] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [rul] real data not found — using synthetic")
    return generate_rul_features()


def load_bms_telemetry(directory: str = os.path.join(_BASE, "bms_v21")) -> pd.DataFrame:
    """Load the BMS v2.1 telemetry dataset."""
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [bms_v21] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [bms_v21] real data not found — using synthetic")
    return generate_bms_telemetry()


def load_distributed_bms(directory: str = os.path.join(_BASE, "dist_bms")) -> pd.DataFrame:
    """Load the Synthetic Distributed BMS dataset."""
    csv = _first_csv(directory)
    if csv:
        df = pd.read_csv(csv)
        print(f"  [dist_bms] loaded real data: {csv}  ({len(df):,} rows)")
        return df
    print("  [dist_bms] real data not found — using synthetic")
    return generate_distributed_bms()


DOWNLOAD_COMMANDS = """
# ── Kaggle dataset download commands ─────────────────────────────────────────
# Run these from the repo root after placing kaggle.json in ~/.kaggle/

mkdir -p data/kaggle

kaggle datasets download patrickfleith/nasa-battery-dataset \\
    -p data/kaggle/nasa --unzip

kaggle datasets download programmer3/lithium-ion-battery-degradation-dataset \\
    -p data/kaggle/degradation --unzip

kaggle datasets download ziya07/ev-battery-charging-data \\
    -p data/kaggle/ev_charging --unzip

kaggle datasets download ignaciovinuales/battery-remaining-useful-life-rul \\
    -p data/kaggle/rul --unzip

kaggle datasets download akhileshdkapse/version21-bms-dataset \\
    -p data/kaggle/bms_v21 --unzip

kaggle datasets download micamadi/synthetic-distributed-battery-management-system \\
    -p data/kaggle/dist_bms --unzip
# ─────────────────────────────────────────────────────────────────────────────
"""
