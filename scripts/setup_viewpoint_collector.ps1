$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv/Scripts/python.exe'
Push-Location $project
try {
    & $python -m application.strategy_radar.viewpoint_collector
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
