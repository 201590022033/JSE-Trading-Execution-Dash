"""Retain a JSON trade snapshot with its actual local acquisition time."""
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.trade_tape import capture

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);a=p.parse_args()
    raw=a.input.read_bytes();data=json.loads(raw)
    digest,result=capture(data['instrument'],data['rows'],source=data['source'],captured_at=datetime.now(timezone.utc).isoformat(),root=ROOT/'runtime/local-backtest/trade-tape',source_sha256=hashlib.sha256(raw).hexdigest())
    archive=ROOT/'runtime/local-backtest/trade-tape'/(digest+'.source.json');archive.write_bytes(raw)
    print(json.dumps({'snapshot_id':digest,'summary':result['summary'],'captured_at':result['captured_at']}))

if __name__=='__main__':main()
