$ErrorActionPreference = "Stop"

py -m pip install pyinstaller flask flask-cors requests
py -m PyInstaller --clean ScoreboardDashboard.spec

Write-Host "Built: dist\ScoreboardDashboard.exe"
