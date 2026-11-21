$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m PyInstaller build.spec --clean --noconfirm
Write-Host "EXE: $((Resolve-Path 'dist\MagisterLive.exe').Path)"
