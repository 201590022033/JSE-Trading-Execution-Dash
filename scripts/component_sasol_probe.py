"""Run a bounded component diagnostic on retained Sasol and sector ETF data."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.opportunities.zebra_screen_data import load_zebra_screen_data
from application.backtest_lab.zebra_field_windows import valid_segments,FIELDS
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.components import Components
from application.backtest_lab.component_replay import run_components

def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);a=p.parse_args()
 data=load_zebra_screen_data(instruments={'SASOL','ETF_STXRES'});stock=data['instruments']['SASOL']
 segments=[s for s in valid_segments(stock['rows'],FIELDS) if len(s)>=52]
 if not segments:raise ValueError('no contiguous Sasol OHLCV window')
 seg=segments[-1];charts={'SASOL':[{'timestamp':r['session'],**{f:r[f] for f in FIELDS}} for r in seg],
 'ETF_STX40':[{'timestamp':r['session'],'close':r['close']} for r in data['instruments'].get('ETF_STXRES',{}).get('rows',[]) if r.get('close') is not None]}
 source=next(v for r in reversed(seg) for v in r.get('fields',{}).values() if isinstance(v,dict) and v.get('source_sha256'))
 m=from_chart('SASOL',{'bars':charts['SASOL'],'provenance':{'provider':'ZEBRA_FIELD_BRANCH','source_sha256':source['source_sha256'],'acquired_at':source['acquired_at']}})
 b=Components();variants=[('baseline',b),('entry_breakout',replace(b,entry='breakout')),
 ('entry_reclaim',replace(b,entry='reclaim')),('volume_off',replace(b,volume_mode='off')),
 ('benchmark_off',replace(b,benchmark_mode='off')),('stop_atr',replace(b,stop_mode='atr')),
 ('horizon4',replace(b,horizon=4)),('horizon5',replace(b,horizon=5)),('trail_atr',replace(b,trail='ATR')),
 ('trail_atr_activation_2r',replace(b,trail='ATR',trail_activation_r=2)),
 ('ema21_or_horizon',replace(b,exit_mode='EMA21_CLOSE'))]
 trials=[]
 for name,config in variants:
  result=run_components(config,m,charts);trials.append({'name':name,'result':result})
  print(json.dumps({'name':name,'signals':len(result['signals']),'trades':len(result['trades']),
   'net':sum(float(x['net_pnl']) for x in result['trades'])}),flush=True)
 payload={'schema':'bounded-component-diagnostic-v1','benchmark':'ETF_STXRES_CURRENT_SECTOR_PROXY',
 'field_lineage':[{f:r.get('fields',{}).get(f) for f in FIELDS} for r in seg],
 'window':[seg[0]['session'],seg[-1]['session']],'limitations':['RECONSTRUCTED_AVAILABILITY','HYPOTHETICAL_COSTS','ONE_INSTRUMENT','NOT_OUT_OF_SAMPLE'],
 'trial_count':len(trials),'trials':trials,'live_execution':False}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=sha256(raw).hexdigest()
 folder=Path(a.output_dir);folder.mkdir(parents=True,exist_ok=True);target=folder/(digest+'.json')
 if target.exists() and target.read_bytes()!=raw:raise ValueError('report collision')
 if not target.exists():
  with target.open('xb') as f:f.write(raw)
 print(json.dumps({'report':str(target),'sha256':digest,'trials':len(trials)}))
if __name__=='__main__':main()
