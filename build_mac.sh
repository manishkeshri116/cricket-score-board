#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install pyinstaller flask flask-cors requests
python3 -m PyInstaller --clean ScoreboardDashboard.spec

echo "Built: dist/ScoreboardDashboard"
