"""Run the gated macro look-ahead against the reviewed local trading database."""
import argparse,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--force',action='store_true');parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    for line in (ROOT/'.env.local').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k,v=line.split('=',1);os.environ[k.strip()]=v.strip()
    u=urlsplit(os.environ['DATABASE_URL'])
    if u.hostname not in ('localhost','127.0.0.1') or u.port!=5433 or u.path!='/trading':raise ValueError('Expected local trading database')
    from scripts.local_runtime import process_lock
    from runtime_persistence import runtime_repository
    from market_intelligence.macro_lookahead import run
    with process_lock(ROOT/'runtime/macro-lookahead.lock'):
        repo=runtime_repository()
        try:
            result=run(repo,datetime.now(timezone.utc),force=args.force,refresh=args.refresh)
            print(json.dumps({'state':result['state'],'record_id':result['receipt']['record_id'],'counts_by_day':result['receipt']['counts_by_day'],'failures':result['receipt']['failures']}))
        finally:repo.close()
