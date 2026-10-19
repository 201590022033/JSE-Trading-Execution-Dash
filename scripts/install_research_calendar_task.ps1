$ErrorActionPreference = 'Stop'
$calendarRoot = Split-Path -Parent $PSScriptRoot
$calendarReceipt = Join-Path $calendarRoot 'runtime/local-migration/fresh-20261015/bootstrap-acceptance.json'
if (-not (Test-Path -LiteralPath $calendarReceipt)) { throw 'Accepted local runtime required.' }
$calendarPython = Join-Path $calendarRoot '.venv/Scripts/python.exe'
$calendarScript = Join-Path $PSScriptRoot 'research_calendar.py'
$calendarUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$calendarPrincipal = New-ScheduledTaskPrincipal -UserId $calendarUser -LogonType Interactive -RunLevel Limited
$calendarAction = New-ScheduledTaskAction -Execute $calendarPython -Argument ('"' + $calendarScript + '" tick') -WorkingDirectory $calendarRoot
$calendarRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$calendarLogon = New-ScheduledTaskTrigger -AtLogOn -User $calendarUser
# This clock only reads local dates and appends small due receipts. It must not
# wait for idle; model/backtest work still uses the separate existing idle jobs.
$calendarSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -Priority 7
Register-ScheduledTask -TaskName 'Trading System Research Calendar' -Action $calendarAction -Trigger @($calendarRepeat, $calendarLogon) -Principal $calendarPrincipal -Settings $calendarSettings -Force | Out-Null
Write-Output 'Research calendar clock installed: every five minutes while signed in; no model or broker calls.'
