"""Run a five-minute research clock only during recent local dashboard use."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'runtime/local-migration/fresh-20261015'
COMMANDS={'calendar':'research_calendar.py','radar':'anticipatory_radar.py'}


def dashboard_active():
    try:
        with urlopen('http://127.0.0.1:5000/api/v1/dashboard/activity',timeout=2) as response:
            data=json.loads(response.read(4096))
        return data.get('state')=='AVAILABLE' and data.get('active') is True
    except (OSError,ValueError,TypeError):
        return False


def run(kind, *, activity=dashboard_active, execute=subprocess.run):
    if kind not in COMMANDS: raise ValueError('unknown dashboard clock')
    if not activity():
        return {'state':'DORMANT_NO_RECENT_DASHBOARD_ACTIVITY','clock':kind}
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    try:
        child=execute([sys.executable,str(ROOT/'scripts'/COMMANDS[kind]),'tick'],cwd=ROOT,
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=105,creationflags=flags)
        return {'state':'COMPLETED' if child.returncode == 0 else 'FAILED',
                'clock':kind,'exit_code':child.returncode}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'state':'FAILED','clock':kind,'error_type':type(exc).__name__}


def main():
    kind=sys.argv[1] if len(sys.argv)==2 else ''
    result=run(kind); result['checked_at']=datetime.now(timezone.utc).isoformat()
    # A compact status avoids silent failures without retaining process output.
    FOLDER.mkdir(parents=True,exist_ok=True)
    path=FOLDER/('dashboard-clock-'+kind+'.json'); tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,sort_keys=True)+'\n',encoding='utf-8'); os.replace(tmp,path)
    return 0 if result['state'] != 'FAILED' else 1


if __name__=='__main__': raise SystemExit(main())
