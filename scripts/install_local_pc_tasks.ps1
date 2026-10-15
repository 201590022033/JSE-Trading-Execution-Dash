param([switch]$EnableWorker)
$ErrorActionPreference = 'Stop'
$localRoot = Split-Path -Parent $PSScriptRoot
$localFolder = Join-Path $localRoot 'runtime/local-migration/fresh-20261015'
$localReceipt = Join-Path $localFolder 'bootstrap-acceptance.json'
if (-not (Test-Path -LiteralPath $localReceipt)) { throw 'Accepted fresh bootstrap receipt required.' }
$localPython = Join-Path $localRoot '.venv/Scripts/python.exe'
$localLauncher = Join-Path $PSScriptRoot 'run_local_pc.py'
$localUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$localPrincipal = New-ScheduledTaskPrincipal -UserId $localUser -LogonType Interactive -RunLevel Limited
$localStartupAction = New-ScheduledTaskAction -Execute $localPython -Argument ('"' + $localLauncher + '" dashboard') -WorkingDirectory $localRoot
$localStartupTrigger = New-ScheduledTaskTrigger -AtLogOn -User $localUser
$localStartupSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName 'Trading System Local PC Startup' -Action $localStartupAction -Trigger $localStartupTrigger -Principal $localPrincipal -Settings $localStartupSettings -Force | Out-Null
$localWorkerAction = New-ScheduledTaskAction -Execute $localPython -Argument ('"' + $localLauncher + '" cycle') -WorkingDirectory $localRoot
$localWorkerTrigger = New-ScheduledTaskTrigger -Daily -At '09:00'
$localWorkerSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RunOnlyIfIdle -IdleDuration (New-TimeSpan -Minutes 10) -IdleWaitTimeout (New-TimeSpan -Hours 23) -RestartOnIdle -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) -Priority 7
Register-ScheduledTask -TaskName 'Trading System Local PC Idle Worker' -Action $localWorkerAction -Trigger $localWorkerTrigger -Principal $localPrincipal -Settings $localWorkerSettings -Force | Out-Null
if ($EnableWorker) { Enable-ScheduledTask -TaskName 'Trading System Local PC Idle Worker' | Out-Null }
else { Disable-ScheduledTask -TaskName 'Trading System Local PC Idle Worker' | Out-Null }
$localBackupAction = New-ScheduledTaskAction -Execute $localPython -Argument ('"' + $localLauncher + '" backup') -WorkingDirectory $localRoot
$localBackupTrigger = New-ScheduledTaskTrigger -Daily -At '02:00'
Register-ScheduledTask -TaskName 'Trading System Local PC Idle Backup' -Action $localBackupAction -Trigger $localBackupTrigger -Principal $localPrincipal -Settings $localWorkerSettings -Force | Out-Null
$localCollectorName = 'Trading System Local Swing Daily Data'
$localCollector = Get-ScheduledTask -TaskName $localCollectorName -ErrorAction SilentlyContinue
if ($localCollector) {
    $localBackup = Join-Path $localFolder 'collector-before-local-cutover.xml'
    if (-not (Test-Path -LiteralPath $localBackup)) {
        Export-ScheduledTask -TaskName $localCollectorName | Set-Content -LiteralPath $localBackup
    }
    # Preserve all task settings/triggers/principal; remove only cloud delivery.
    $localActions = $localCollector.Actions
    foreach ($localAction in $localActions) {
        if ($localAction.Arguments -match 'collect_swing_data.py') {
            $localAction.Arguments = $localAction.Arguments -replace '\s+--upload\b', ''
        }
    }
    Set-ScheduledTask -TaskName $localCollectorName -Action $localActions | Out-Null
}
Write-Output 'Local startup installed; worker uses 10-minute idle gate and below-normal priority. Collector cloud upload removed.'
