#!/usr/bin/env bash
# download_kaggle_datasets.sh
# Run this on your LOCAL machine to download all 6 Kaggle battery datasets.
#
# Prerequisites:
#   1. pip install kaggle
#   2. Place kaggle.json in ~/.kaggle/   (get it from kaggle.com → Account → API Token)
#      chmod 600 ~/.kaggle/kaggle.json
#
# Usage:
#   chmod +x download_kaggle_datasets.sh
#   ./download_kaggle_datasets.sh

set -e

echo "=== Kaggle Battery Dataset Downloader ==="

# ── Check kaggle CLI ──────────────────────────────────────────────────────────
if ! command -v kaggle &> /dev/null; then
    echo "kaggle CLI not found. Installing..."
    pip install kaggle
fi

# ── Check credentials ─────────────────────────────────────────────────────────
if [ ! -f "$HOME/.kaggle/kaggle.json" ] && [ ! -f "$HOME/.kaggle/access_token" ]; then
    echo ""
    echo "ERROR: No Kaggle credentials found."
    echo "  1. Go to https://www.kaggle.com/settings/account"
    echo "  2. Scroll to 'API' section → 'Create New Token'"
    echo "  3. Save the downloaded kaggle.json to ~/.kaggle/kaggle.json"
    echo "  4. Run: chmod 600 ~/.kaggle/kaggle.json"
    echo "  Then re-run this script."
    exit 1
fi

mkdir -p data/kaggle

# ── Dataset 1: NASA Battery Dataset ──────────────────────────────────────────
echo ""
echo "[1/6] NASA Battery Dataset (patrickfleith)..."
kaggle datasets download patrickfleith/nasa-battery-dataset \
    -p data/kaggle/nasa --unzip
echo "      → data/kaggle/nasa/"

# ── Dataset 2: Li-Ion Degradation ────────────────────────────────────────────
echo ""
echo "[2/6] Li-Ion Battery Degradation (programmer3)..."
kaggle datasets download programmer3/lithium-ion-battery-degradation-dataset \
    -p data/kaggle/degradation --unzip
echo "      → data/kaggle/degradation/"

# ── Dataset 3: EV Battery Charging ───────────────────────────────────────────
echo ""
echo "[3/6] EV Battery Charging Data (ziya07)..."
kaggle datasets download ziya07/ev-battery-charging-data \
    -p data/kaggle/ev_charging --unzip
echo "      → data/kaggle/ev_charging/"

# ── Dataset 4: Battery RUL ────────────────────────────────────────────────────
echo ""
echo "[4/6] Battery Remaining Useful Life (ignaciovinuales)..."
kaggle datasets download ignaciovinuales/battery-remaining-useful-life-rul \
    -p data/kaggle/rul --unzip
echo "      → data/kaggle/rul/"

# ── Dataset 5: BMS v2.1 Telemetry ────────────────────────────────────────────
echo ""
echo "[5/6] BMS v2.1 Dataset (akhileshdkapse)..."
kaggle datasets download akhileshdkapse/version21-bms-dataset \
    -p data/kaggle/bms_v21 --unzip
echo "      → data/kaggle/bms_v21/"

# ── Dataset 6: Distributed BMS ───────────────────────────────────────────────
echo ""
echo "[6/6] Synthetic Distributed BMS (micamadi)..."
kaggle datasets download micamadi/synthetic-distributed-battery-management-system \
    -p data/kaggle/dist_bms --unzip
echo "      → data/kaggle/dist_bms/"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Download complete ==="
echo ""
echo "Files downloaded:"
find data/kaggle -name "*.csv" | sort | while read f; do
    rows=$(( $(wc -l < "$f") - 1 ))
    echo "  $f  (${rows} rows)"
done

echo ""
echo "Next step — run validation against real data:"
echo "  python -m bms.simulation --datasets"
