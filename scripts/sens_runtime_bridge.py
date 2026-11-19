"""Existing retained-source tick plus delivery to the dashboard; no source fetching."""
from pathlib import Path
import os,sys,json,subprocess
from datetime import datetime,timezone
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    if '--bridge-only' not in sys.argv:
        subprocess.run([sys.executable,str(ROOT/'scripts/anticipatory_radar.py'),'tick'],cwd=ROOT,check=True)
    from runtime_persistence import runtime_repository
    from market_intelligence.sens_runtime_bridge import sync
    from scripts.local_runtime import process_lock
    from dotenv import dotenv_values
    target_url=dotenv_values(ROOT/'.env.local')['DATABASE_URL']
    source_url=json.loads((ROOT/'runtime/local-migration/fresh-20261015/environment.json').read_text())['DATABASE_URL']
    for url,port,db in [(target_url,5433,'/trading'),(source_url,55432,'/trading_local_20261015')]:
        u=urlsplit(url)
        if u.hostname not in ('localhost','127.0.0.1') or u.port!=port or u.path!=db: raise ValueError('Unexpected SENS bridge database')
    with process_lock(ROOT/'runtime/sens-runtime-bridge.lock'):
        from application.opportunities.ost_data import atomic_json
        from urllib.parse import quote
        checkpoint = ROOT/'runtime/sens-runtime-bridge-cursors.json'
        try:
            cursors = json.loads(checkpoint.read_text(encoding='utf-8'))
        except FileNotFoundError:
            cursors = {}
        source=runtime_repository(database_url=source_url+('&' if '?' in source_url else '?')+'options='+quote('-c default_transaction_read_only=on'));target=runtime_repository(database_url=target_url)
        try:
            with source.transaction():
                result=sync(source,target,datetime.now(timezone.utc),cursors=cursors)
            if result['next_cursors'] != cursors:
                atomic_json(checkpoint, result['next_cursors'])
            print(json.dumps(result))
        finally:source.close();target.close()
def run_with_macro(bridge=main, invoke=subprocess.Popen, args=None):
    # A legacy bridge failure must not prevent the independent macro check.
    # The original bridge exception still propagates to its SENS roster job.
    args = sys.argv if args is None else args
    try:
        bridge()
    finally:
        if '--bridge-only' not in args:
            try:
                invoke([sys.executable, str(ROOT/'scripts/ai_expectation_dispatch.py')],
                       cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, close_fds=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except OSError as exc:
                from scripts.share_expectations import write_check as write_share_check
                from scripts.macro_expectations import write_check as write_macro_check
                result = {'state':'WORKER_START_ERROR','error_type':type(exc).__name__}
                write_share_check(result)
                write_macro_check(result)

if __name__=='__main__':
    run_with_macro()

