"""Unattended local warning clock; no source, model or broker requests."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import os,sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    for line in (ROOT/'.env.local').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k,v=line.split('=',1);os.environ[k.strip()]=v.strip()
    u=urlsplit(os.environ.get('DATABASE_URL',''))
    if u.hostname not in ('localhost','127.0.0.1') or u.port!=5433 or u.path!='/trading':
        raise ValueError('Expected local trading database on port 5433')
    from runtime_persistence import runtime_repository
    from market_intelligence import research_calendar as cal,anticipatory_radar as radar
    from scripts.local_runtime import process_lock
    now=datetime.now(timezone.utc)
    with process_lock(ROOT/'runtime/macro-calendar-clock.lock'):
        repo=runtime_repository()
        try:
            result=cal.tick(repo,now);radar.tick(repo,now)
            report={'checked_at':now.isoformat(),'state':result['state'],'new_receipts':result['new_receipts']}
        finally:repo.close()
    path=ROOT/'runtime/macro-calendar-clock.json';path.write_text(json.dumps(report),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
