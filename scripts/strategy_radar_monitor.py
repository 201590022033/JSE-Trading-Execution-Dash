"""Separate quiet monitor process, started only through an explicit enable action."""
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.strategy_radar.monitor import MonitorStore,check_once
from application.strategy_radar.service import RadarService
from application.strategy_radar.viewpoint_inbox import ViewPointInbox
from application.strategy_radar.viewpoint_collector import ViewPointCollector
from application.strategy_radar.monitor import market_status


def windows_notification(instrument,state):
    if os.name!='nt': return 'UNAVAILABLE_NON_WINDOWS'
    # Pass plain text as stdin; XML escaping occurs inside PowerShell.
    script=r'''$ErrorActionPreference='Stop'
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime] > $null
$registered = @(Get-StartApps | Where-Object { $_.AppID -eq 'Strategy Radar' })
if ($registered.Count -eq 0) { [Console]::Out.Write('WINDOWS_SENDER_NOT_REGISTERED'); exit 0 }
$notifier=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Strategy Radar')
if ($notifier.Setting.ToString() -ne 'Enabled') { [Console]::Out.Write('WINDOWS_NOTIFICATION_DISABLED'); exit 0 }
$xml=[Windows.Data.Xml.Dom.XmlDocument]::new()
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>Strategy Radar</text><text></text></binding></visual></toast>')
$xml.GetElementsByTagName('text').Item(1).AppendChild($xml.CreateTextNode([Console]::In.ReadToEnd())) > $null
$notifier.Show([Windows.UI.Notifications.ToastNotification]::new($xml))
[Console]::Out.Write('SUBMITTED_TO_WINDOWS')'''
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],input=f'{instrument}: {state} (research only)',text=True,encoding='utf-8',capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        status=result.stdout.strip()
        allowed={'SUBMITTED_TO_WINDOWS','WINDOWS_SENDER_NOT_REGISTERED','WINDOWS_NOTIFICATION_DISABLED'}
        return status if result.returncode==0 and status in allowed else 'WINDOWS_NOTIFICATION_FAILED'
    except (OSError,subprocess.TimeoutExpired): return 'WINDOWS_NOTIFICATION_FAILED'


def main():
    data_root=Path(os.environ.get('STRATEGY_RADAR_MONITOR_ROOT') or ROOT)
    service=RadarService(root=data_root); store=MonitorStore(service.folder/'monitor.sqlite3');owner=uuid.uuid4().hex
    now=lambda:datetime.now(timezone.utc)
    if not store.claim(owner,now()): return
    inbox = ViewPointInbox(service)
    collector = ViewPointCollector(service)
    next_check=0.0; last_settings=None
    try:
        while store.config()['enabled']:
            if not store.claim(owner,now()): break
            settings=store.config()
            schedule = settings['profile'], settings['interval_seconds']
            if schedule != last_settings:
                next_check = 0.0
                last_settings = schedule
            current=time.monotonic()
            if current>=next_check:
                if market_status(now()) == 'OPEN':
                    collection = collector.collect(service.store.radar_choices())
                    from application.opportunities.ost_data import atomic_json
                    atomic_json(service.folder / 'viewpoint-collection.json',
                                {**collection, 'checked_at': now().isoformat()})
                if not store.claim(owner,now()):
                    break
                check_once(store,service,now(),notifier=windows_notification,load_exports=inbox.load)
                next_check=time.monotonic()+store.config()['interval_seconds']
            time.sleep(15)
    finally: store.release(owner)
if __name__=='__main__': main()
