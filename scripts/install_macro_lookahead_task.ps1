$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskUser=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal=New-ScheduledTaskPrincipal -UserId $taskUser -LogonType S4U -RunLevel Limited
$python=Join-Path $taskRoot '.venv/Scripts/pythonw.exe'
$script=Join-Path $PSScriptRoot 'macro_lookahead.py'
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$script+'"') -WorkingDirectory $taskRoot
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'Trading System Macro Lookahead' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$script+'" --force') -WorkingDirectory $taskRoot
$trigger=New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '06:00'
Register-ScheduledTask -TaskName 'Trading System Monday Macro Lookahead' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName 'Trading System *Macro Lookahead' | Select-Object TaskName,State
