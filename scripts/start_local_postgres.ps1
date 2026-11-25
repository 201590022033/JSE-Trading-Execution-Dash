param(
    [string]$PythonPath = (Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe')
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Dashboard Python was not found at '$PythonPath'. Restore the project virtual environment or pass -PythonPath."
}
. (Join-Path $PSScriptRoot "load_local_env.ps1")
$env:HOST = "127.0.0.1"

& $PythonPath (Join-Path $PSScriptRoot "..\app.py")
exit $LASTEXITCODE
