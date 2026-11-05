"""Compare saved Sasol trades with retained Brent and USD/ZAR references."""
import json
from hashlib import sha256
from pathlib import Path
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.proxy_context import compare

def read(path):
 raw=path.read_bytes();digest=sha256(raw).hexdigest()
 if digest not in path.stem:raise ValueError('retained input hash mismatch')
 return json.loads(raw),digest

def main():
 root=ROOT/'runtime/local-backtest/component-learning';data=ROOT/'runtime/local-swing-data/cross-asset-research'
 status=json.loads((root/'SASOL.json').read_text(encoding='utf-8'))
 exp=next(x for x in status['experiments'] if x['component']=='volume_mode')
 proxies={};sources={}
 for name,pattern in [('BRENT','BZ_F-*.json'),('USDZAR','ZAR_X-*.json')]:
  paths=sorted(data.glob(pattern),key=lambda p:p.stat().st_mtime,reverse=True)
  if not paths:continue
  source,digest=read(paths[0]);proxies[name]=source
  sources[name]={k:source.get(k) for k in ('symbol','product','expected_units','acquired_at','historical_availability')}
  sources[name]['sha256']=digest
 stages={}
 for result in exp['results']:
  if not result.get('artifacts'):continue
  artifact,_=read(root/'artifacts'/(result['artifacts'][0]+'.json'))
  stages[result['stage']]=compare(artifact,proxies)
 report={'schema':'m5-proxy-comparison-v1','created_at':datetime.now(timezone.utc).isoformat(),
  'instrument':'SASOL','experiment_id':exp['experiment_id'],'sources':sources,'stages':stages,
  'limitations':['RECONSTRUCTED_HISTORICAL_TIMING','NOT_POINT_IN_TIME_MODEL_EVIDENCE',
   'POSTHOC_TRADE_SUBSETS_NOT_A_PORTFOLIO_REPLAY','NOT_A_CAUSAL_CLAIM'], 'live_execution':False}
 raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=sha256(raw).hexdigest()
 folder=ROOT/'runtime/local-backtest/context-research';folder.mkdir(parents=True,exist_ok=True)
 with (folder/(digest+'.json')).open('xb') as f:f.write(raw)
 print(json.dumps({'report_sha256':digest,'sources':list(sources),
  'comparisons':{k:v['comparisons'] for k,v in stages.items()},'live_execution':False}))
if __name__=='__main__':main()
