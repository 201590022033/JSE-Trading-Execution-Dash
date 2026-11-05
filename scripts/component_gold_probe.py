"""Run a small fixed component diagnostic on retained JSE NewGold data."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.backtest_gold_reference import load,ObservedGoldUnits
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.zebra_field_windows import valid_segments
from application.backtest_lab.components import Components
from application.backtest_lab.component_replay import run_components
from domain.backtest.products import GoldListed

def main():
 p=argparse.ArgumentParser();p.add_argument('--gold',required=True);p.add_argument('--benchmark',required=True);p.add_argument('--output-dir',required=True)
 p.add_argument('--families-only',action='store_true');a=p.parse_args()
 gold=load(a.gold,'GLD.JO');bench=load(a.benchmark,'STX40.JO');rows=[]
 for r in gold['rows']:
  if r['current_session_not_completed']:continue
  values={f:(r[f]/100 if f!='volume' and r.get(f) is not None else r.get(f)) for f in ('open','high','low','close','volume')}
  rows.append({'session':r['session'],**values})
 seg=[s for s in valid_segments(rows,('open','high','low','close','volume')) if len(s)>=52][-1]
 charts={'NEWGOLD':[{'timestamp':r['session'],**{f:r[f] for f in ('open','high','low','close','volume')}} for r in seg],
  'ETF_STX40':[{'timestamp':r['session'],'close':r['close']/100} for r in bench['rows'] if not r['current_session_not_completed'] and r.get('close')]}
 base=from_chart('NEWGOLD',{'bars':charts['NEWGOLD'],'provenance':{'provider':'YAHOO','source_sha256':Path(a.gold).stem.split('-')[-1],'acquired_at':gold['acquired_at']}})
 m=ObservedGoldUnits(**{**vars(base),'product':'GOLD_ETF'});adapter=GoldListed('ZAR','ZAR',m.calendar_basis,m.sessions,(),m.instrument)
 b=Components();variants=[('baseline',b),('entry_breakout',replace(b,entry='breakout')),
  ('entry_reclaim',replace(b,entry='reclaim')),('entry_trend',replace(b,entry='trend_only')),
  ('volume_off',replace(b,volume_mode='off')),('benchmark_off',replace(b,benchmark_mode='off')),
  ('stop_atr',replace(b,stop_mode='atr')),('stop_structure',replace(b,stop_mode='structure')),
  ('stop_percent',replace(b,stop_mode='percent')),('horizon4',replace(b,horizon=4)),('horizon5',replace(b,horizon=5)),
  ('target_1_5r',replace(b,target_r=1.5)),('trail_atr',replace(b,trail='ATR')),
  ('trail_structure',replace(b,trail='STRUCTURE')),('risk_half',replace(b,risk_budget=6000)),
  ('trail_atr_activation_2r',replace(b,trail='ATR',trail_activation_r=2)),
  ('ema21_or_horizon',replace(b,exit_mode='EMA21_CLOSE'))]
 if a.families_only:
  variants=[]
  for family,profile,threshold in [('vcp','vcp_daily_research',1.3),('box','box_breakout_daily_research',1.2),('pull','pullback_daily_research',1.1)]:
   candidate=Components(family=family,profile_id=profile,profile_version='1.0.0',entry='family_default',
                        momentum=False,benchmark_mode='off',stop_mode='family',volume_min=threshold)
   variants.extend([(family+'_baseline',candidate),(family+'_volume_off',replace(candidate,volume_mode='off'))])
 trials=[]
 for name,config in variants:
  result=run_components(config,m,charts,adapter=adapter)
  trials.append({'name':name,'result':result})
  print(json.dumps({'name':name,'signals':len(result['signals']),'trades':len(result['trades']),
   'net':sum(float(x['net_pnl']) for x in result['trades'])}),flush=True)
 payload={'schema':'bounded-component-diagnostic-v1','source_hash':Path(a.gold).stem.split('-')[-1],
  'benchmark_hash':Path(a.benchmark).stem.split('-')[-1],'window':[seg[0]['session'],seg[-1]['session']],
  'limitations':['RECONSTRUCTED_AVAILABILITY','HYPOTHETICAL_COSTS','ONE_INSTRUMENT','NOT_OUT_OF_SAMPLE'],
  'trial_count':len(trials),'trials':trials,'live_execution':False}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=sha256(raw).hexdigest()
 folder=Path(a.output_dir);folder.mkdir(parents=True,exist_ok=True);target=folder/(digest+'.json')
 if target.exists() and target.read_bytes()!=raw:raise ValueError('report collision')
 if not target.exists():
  with target.open('xb') as f:f.write(raw)
 print(json.dumps({'report':str(target),'sha256':digest,'trials':len(trials)}))
if __name__=='__main__':main()
