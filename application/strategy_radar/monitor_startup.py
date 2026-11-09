"""Optional Windows sign-in task for an explicitly enabled local monitor."""
from pathlib import Path
import os
import subprocess
import sys

TASK_NAME='JSE Strategy Radar Local Monitor 01a1b186'

def set_autostart(enabled):
    if type(enabled) is not bool: raise ValueError('boolean required')
    if os.name!='nt': return 'UNAVAILABLE_NON_WINDOWS'
    if enabled:
        root=Path(__file__).resolve().parents[2]
        executable=Path(sys.executable); pythonw=executable.with_name('pythonw.exe')
        if not pythonw.exists(): return 'PYTHONW_UNAVAILABLE'
        command=subprocess.list2cmdline([str(pythonw),str(root/'scripts/strategy_radar_monitor.py')])
        args=['schtasks.exe','/Create','/TN',TASK_NAME,'/SC','ONLOGON','/TR',command,'/F']
    else:
        args=['schtasks.exe','/Delete','/TN',TASK_NAME,'/F']
    try:
        result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return 'REGISTERED' if enabled and result.returncode==0 else 'REMOVED' if not enabled and result.returncode==0 else 'FAILED'
    except (OSError,subprocess.TimeoutExpired): return 'FAILED'
