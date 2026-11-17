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
        from urllib.parse import quote
        source=runtime_repository(database_url=source_url+('&' if '?' in source_url else '?')+'options='+quote('-c default_transaction_read_only=on'));target=runtime_repository(database_url=target_url)
        try:
            with source.transaction():
                result=sync(source,target,datetime.now(timezone.utc))
            print(json.dumps(result))
        finally:source.close();target.close()
def run_with_macro(bridge=main, invoke=subprocess.run, args=None):
    # A legacy bridge failure must not prevent the independent macro check.
    # The original bridge exception still propagates to its SENS roster job.
    args = sys.argv if args is None else args
    try:
        bridge()
    finally:
        if '--bridge-only' not in args:
            for script in ('macro_expectations.py','share_expectations.py'):
                try:
                    invoke([sys.executable,str(ROOT/'scripts'/script),'--run'],
                           cwd=ROOT,check=False,timeout=240)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    if script == 'macro_expectations.py':
                        from scripts.macro_expectations import write_check
                    else:
                        from scripts.share_expectations import write_check
                    write_check({'state':'WORKER_START_OR_TIMEOUT_ERROR','error_type':type(exc).__name__, 'reason':type(exc).__name__})

if __name__=='__main__':
    run_with_macro()

