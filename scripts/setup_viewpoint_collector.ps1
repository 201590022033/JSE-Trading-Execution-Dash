$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$profile = Join-Path $project 'runtime/local-swing-data/strategy-radar/viewpoint-edge-profile'
$edge = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Microsoft/Edge/Application/msedge.exe'
if (-not (Test-Path -LiteralPath $edge)) {
    throw 'Microsoft Edge installation was not found.'
}
& $edge "--user-data-dir=$profile" 'https://viewpoint.iress.co.za/st/'
