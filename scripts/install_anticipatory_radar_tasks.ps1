param()
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path -Parent $PSScriptRoot
$radarReceipt = Join-Path $radarRoot 'runtime/local-migration/fresh-20261015/bootstrap-acceptance.json'
if (-not (Test-Path -LiteralPath $radarReceipt)) { throw 'Accepted local runtime required.' }
$radarPython = Join-Path $radarRoot '.venv/Scripts/python.exe'
$radarScript = Join-Path $PSScriptRoot 'anticipatory_radar.py'
$radarUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$radarPrincipal = New-ScheduledTaskPrincipal -UserId $radarUser -LogonType Interactive -RunLevel Limited
$captureAction = New-ScheduledTaskAction -Execute $radarPython -Argument ('"' + $radarScript + '" capture') -WorkingDirectory $radarRoot
# No EndBoundary: replaces the exhausted four-date acquisition pilot.
$captureTriggers = @(8,12,16 | ForEach-Object { New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours($_)) })
$captureSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -Priority 7
Register-ScheduledTask -TaskName 'Trading System Idle Prospective News Capture' -Action $captureAction -Trigger $captureTriggers -Principal $radarPrincipal -Settings $captureSettings -Force | Out-Null
$modelAction = New-ScheduledTaskAction -Execute $radarPython -Argument ('"' + $radarScript + '" model') -WorkingDirectory $radarRoot
$modelTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 1)
$modelSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RunOnlyIfIdle -IdleDuration (New-TimeSpan -Minutes 10) -IdleWaitTimeout (New-TimeSpan -Hours 23) -RestartOnIdle -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -Priority 7
$modelSettings.IdleSettings.StopOnIdleEnd = $true
Register-ScheduledTask -TaskName 'Trading System Idle Anticipatory Radar' -Action $modelAction -Trigger $modelTrigger -Principal $radarPrincipal -Settings $modelSettings -Force | Out-Null
Write-Output 'Recurring radar collection: 08:00/12:00/16:00 SAST while signed in. Small-model qualification/discovery: hourly, ten minutes idle. No end date or trading effects.'
