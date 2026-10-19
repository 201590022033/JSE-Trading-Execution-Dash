param([switch]$EnableRunner)
$ErrorActionPreference = 'Stop'
$draftRoot = Split-Path -Parent $PSScriptRoot
$draftReceipt = Join-Path $draftRoot 'runtime/local-migration/fresh-20261015/bootstrap-acceptance.json'
if (-not (Test-Path -LiteralPath $draftReceipt)) { throw 'Accepted local runtime required.' }
$draftPython = Join-Path $draftRoot '.venv/Scripts/python.exe'
$draftScript = Join-Path $PSScriptRoot 'calendar_ollama.py'
$draftUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$draftPrincipal = New-ScheduledTaskPrincipal -UserId $draftUser -LogonType Interactive -RunLevel Limited
$draftAction = New-ScheduledTaskAction -Execute $draftPython -Argument ('"' + $draftScript + '" run') -WorkingDirectory $draftRoot
$draftTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$draftSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RunOnlyIfIdle -IdleDuration (New-TimeSpan -Minutes 10) -IdleWaitTimeout (New-TimeSpan -Hours 23) -RestartOnIdle -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -Priority 7
# Explicitly require StopOnIdleEnd; the owned Windows job additionally kills the
# dedicated Ollama server and its runner if this task is stopped or crashes.
$draftSettings.IdleSettings.StopOnIdleEnd = $true
Register-ScheduledTask -TaskName 'Trading System Idle Calendar Ollama' -Action $draftAction -Trigger $draftTrigger -Principal $draftPrincipal -Settings $draftSettings -Force | Out-Null
if ($EnableRunner) { Enable-ScheduledTask -TaskName 'Trading System Idle Calendar Ollama' | Out-Null }
else { Disable-ScheduledTask -TaskName 'Trading System Idle Calendar Ollama' | Out-Null }
Write-Output 'Calendar draft runner installed: hourly while signed in, 10 minutes idle, below-normal priority, disabled unless explicitly enabled. No trades or automatic expectation acceptance.'
