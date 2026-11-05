"""Run matched historical context/control replays from retained local inputs."""
import argparse,json,sys
from hashlib import sha256
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.components import Components
from application.backtest_lab.context_replay import compare
from application.backtest_lab.learning_loop import split_sessions,_prefix
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.research_context import fundamental_facts

def verified(path):
 raw=path.read_bytes()
 if len(raw)>32_000_000 or sha256(raw).hexdigest()!=path.stem:raise ValueError('input integrity mismatch')
 return json.loads(raw)

def main():
 p=argparse.ArgumentParser();p.add_argument('--instrument',choices=('SASOL','BTI','FSR','ABSPJ'),default='SASOL')
 p.add_argument('--family',choices=('swing','pull'),default='swing')
 p.add_argument('--proxy-variants',action='store_true',help='Run three separately labelled retrospective proxy filters');a=p.parse_args()
 root=ROOT/'runtime/local-backtest/component-learning';status=json.loads((root/(a.instrument+'.json')).read_text(encoding='utf-8'))
 lineage=status.get('source_lineage_sha256')
 if not lineage:raise ValueError('source lineage is not retained for this instrument')
 source=verified(root/'inputs'/(lineage+'.json'));rows=source['rows']
 charts={a.instrument:[{'timestamp':r['session'],**{f:r.get(f) for f in ('open','high','low','close','volume')}} for r in rows]}
 charts['ETF_STX40']=[{'timestamp':r['session'],'close':r['close']} for r in source['benchmark_rows'] if r.get('close') is not None]
 provenance=next(v for r in reversed(rows) for v in r.get('fields',{}).values() if isinstance(v,dict) and v.get('source_sha256'))
 manifest=from_chart(a.instrument,{'bars':charts[a.instrument],'provenance':{'provider':'ZEBRA_FIELD_BRANCH',
    'source_sha256':provenance['source_sha256'],'acquired_at':provenance['acquired_at']}})
 exp=next(x for x in status['experiments'] if x['component']!='INTERACTION' and x.get('results'))
 artifact=verified(root/'artifacts'/(exp['results'][0]['artifacts'][0]+'.json'))
 config=Components(**artifact['control']['config'])
 if a.family=='pull':
  config=Components(family='pull',profile_id='pullback_daily_research',profile_version='1.0.0',
   entry='family_default',momentum=False,benchmark_mode='off',stop_mode='family',volume_min=1.1)
 folder=ROOT/'runtime/local-backtest/context-research';items=[];context_id=None
 for path in sorted(folder.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
  try:
   report=verified(path)
   if report.get('schema')=='m5-sens-coverage-v1' and report.get('instrument')==a.instrument:
    items=report['relevant_sources'];context_id=path.stem;break
  except (OSError,ValueError,KeyError,TypeError):continue
 proxy_rows={};proxy_receipts={}
 if a.proxy_variants:
  data=ROOT/'runtime/local-swing-data/cross-asset-research'
  for rule,pattern in [('skip_brent_falling','BZ_F-*.json'),('skip_usdzar_rising','ZAR_X-*.json')]:
   paths=sorted(data.glob(pattern),key=lambda x:x.stat().st_mtime,reverse=True)
   if paths:
    # Cross-asset file names contain a symbol prefix before the content hash.
    raw=paths[0].read_bytes();digest=sha256(raw).hexdigest()
    if not paths[0].stem.endswith(digest):raise ValueError('proxy integrity mismatch')
    content=json.loads(raw);proxy_rows[rule]=content['rows']
    proxy_receipts[rule]={k:content.get(k) for k in ('symbol','product','expected_units','acquired_at','historical_availability')}
    proxy_receipts[rule]['sha256']=digest
  proxy_rows['skip_sector_falling']=[{**r,'current_session_not_completed':False} for r in source['benchmark_rows']]
  proxy_receipts['skip_sector_falling']={'instrument':source.get('benchmark'),'source_lineage_sha256':lineage,
    'historical_availability':'RECONSTRUCTED_NOT_ACTUAL_RECEIPT'}
 split=split_sessions(manifest);results={};proxy_results={}
 for stage in ('train','validation'):
  begin,end=split[stage];m,c=_prefix(manifest,charts,end)
  # Preserve warm-up bars but score only the validation decisions.
  results[stage]=compare(config,m,c,items,decision_start=manifest.sessions[begin].key if stage=='validation' else None)
  if a.proxy_variants:
   proxy_results[stage]={}
   for rule in ('skip_brent_falling','skip_sector_falling','skip_usdzar_rising'):
    proxy_results[stage][rule]=compare(config,m,c,items,decision_start=manifest.sessions[begin].key if stage=='validation' else None,
                                       proxy_rule=rule,proxy_rows=proxy_rows.get(rule,()))
 out={'schema':'m5-matched-context-study-v1','created_at':datetime.now(timezone.utc).isoformat(),
  'instrument':a.instrument,'family':a.family,'input_lineage_sha256':lineage,'context_report_sha256':context_id,
  'experiment_parent':exp['experiment_id'] if a.family=='swing' else None,'split':split,'results':results,'proxy_variants':proxy_results,
  'proxy_receipts':proxy_receipts,'proxy_trial_count':sum(len(v) for v in proxy_results.values()),
  'model_calls':0,'live_execution':False}
 raw=json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=sha256(raw).hexdigest()
 with (folder/(digest+'.json')).open('xb') as f:f.write(raw)
 summary={stage:{'baseline_signals':len(v['baseline']['signals']),'baseline_trades':len(v['baseline']['trades']),
   'candidate_signals':len(v['candidate']['signals']),'candidate_trades':len(v['candidate']['trades']),
   'context_suppressed':sum(x['candidate_state']=='CONTEXT_SUPPRESSED' for x in v['context_checks'])} for stage,v in results.items()}
 variations={stage:{rule:{'trades':len(v['candidate']['trades']),
    'net':round(sum(float(t['net_pnl']) for t in v['candidate']['trades']),2),
    'suppressed':sum(x['candidate_state']=='CONTEXT_SUPPRESSED' for x in v['context_checks'])}
    for rule,v in variants.items()} for stage,variants in proxy_results.items()}
 print(json.dumps({'report_sha256':digest,'instrument':a.instrument,'family':a.family,'stages':summary,'proxy_variants':variations,
  'proxy_trial_count':out['proxy_trial_count'],'live_execution':False}))
if __name__=='__main__':main()
