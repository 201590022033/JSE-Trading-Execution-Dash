param(
    [int]$Port = 5000,
    [string]$ReportDirectory = '',
    [switch]$Background,
    [switch]$JoinLocalMacroEvents
)
$ErrorActionPreference = 'Stop'
$dashboardRoot = Split-Path -Parent $PSScriptRoot
$dashboardPython = Join-Path $dashboardRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $dashboardPython)) { throw 'Project Python environment is missing.' }
if (-not $ReportDirectory) { $ReportDirectory = Join-Path $dashboardRoot 'runtime/local-backtest' }
$env:LOCAL_BACKTEST_REPORT_DIR = [IO.Path]::GetFullPath($ReportDirectory)
$env:HOST = '127.0.0.1'
$env:PORT = [string]$Port
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:OST_LOCAL_IMPORT_ENABLED = '1'
if ($JoinLocalMacroEvents) {
    # Read the already-configured local macro database without displaying its URL.
    $eventUrl = & $dashboardPython -c "import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get('DATABASE_URL', ''))" (Join-Path $dashboardRoot '.env.local')
    if ($LASTEXITCODE -ne 0 -or -not $eventUrl) { throw 'Local macro database configuration is unavailable.' }
    $eventUri = [Uri]$eventUrl
    if ($eventUri.Scheme -notin @('postgres','postgresql') -or
        $eventUri.Host -notin @('localhost','127.0.0.1','::1') -or
        $eventUri.Port -ne 5433 -or $eventUri.AbsolutePath -ne '/trading') {
        throw 'Local macro database identity is not the expected localhost:5433/trading.'
    }
    $env:EVENT_PREPARATION_DATABASE_URL = $eventUrl
}
if ($Background) {
    $dashboardLogs = Join-Path $dashboardRoot 'runtime'
    New-Item -ItemType Directory -Path $dashboardLogs -Force | Out-Null
    $dashboardProcess = Start-Process -FilePath $dashboardPython -ArgumentList 'app.py' `
        -WorkingDirectory $dashboardRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $dashboardLogs 'dashboard.stdout.log') `
        -RedirectStandardError (Join-Path $dashboardLogs 'dashboard.stderr.log')
    [pscustomobject]@{ State = 'STARTED_IN_BACKGROUND'; ProcessId = $dashboardProcess.Id; URL = "http://127.0.0.1:$Port/" }
    exit 0
}
Push-Location $dashboardRoot
try { & $dashboardPython app.py }
finally { Pop-Location }
