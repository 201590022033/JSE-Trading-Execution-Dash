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


def windows_notification(instrument,state):
    if os.name!='nt': return 'UNAVAILABLE_NON_WINDOWS'
    # Pass plain text as stdin; XML escaping occurs inside PowerShell.
    script=r'''$ErrorActionPreference='Stop'
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime] > $null
$xml=[Windows.Data.Xml.Dom.XmlDocument]::new()
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>Strategy Radar</text><text></text></binding></visual></toast>')
$xml.GetElementsByTagName('text').Item(1).AppendChild($xml.CreateTextNode([Console]::In.ReadToEnd())) > $null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Strategy Radar').Show([Windows.UI.Notifications.ToastNotification]::new($xml))'''
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],input=f'{instrument}: {state} (research only)',text=True,encoding='utf-8',capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return 'SUBMITTED_TO_WINDOWS' if result.returncode==0 else 'WINDOWS_NOTIFICATION_FAILED'
    except (OSError,subprocess.TimeoutExpired): return 'WINDOWS_NOTIFICATION_FAILED'


def main():
    data_root=Path(os.environ.get('STRATEGY_RADAR_MONITOR_ROOT') or ROOT)
    service=RadarService(root=data_root); store=MonitorStore(service.folder/'monitor.sqlite3');owner=uuid.uuid4().hex
    now=lambda:datetime.now(timezone.utc)
    if not store.claim(owner,now()): return
    next_check=0.0; last_profile=None
    try:
        while store.config()['enabled']:
            if not store.claim(owner,now()): break
            settings=store.config()
            if settings['profile']!=last_profile: next_check=0.0; last_profile=settings['profile']
            current=time.monotonic()
            if current>=next_check:
                check_once(store,service,now(),notifier=windows_notification)
                next_check=time.monotonic()+store.config()['interval_seconds']
            time.sleep(15)
    finally: store.release(owner)
if __name__=='__main__': main()
