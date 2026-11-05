"""Replay four daily research strategies on captured JSE NewGold units."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.observed_history import ObservedHistory,from_chart
from application.backtest_lab.strategies import PROFILES
from application.backtest_lab.zebra_field_windows import valid_segments,evaluate_mixed
from domain.backtest.engine import Costs,Signal,replay
from domain.backtest.products import GoldListed

class ObservedGoldUnits(ObservedHistory):
 @property
 def activity_basis(self):return 'TRADED_UNITS'
 @property
 def calendar_id(self):return self.calendar_basis

def load(path,expected):
 raw=Path(path).read_bytes();d=json.loads(raw)
 if sha256(raw).hexdigest() not in Path(path).stem or d['symbol']!=expected:raise ValueError('capture identity mismatch')
 if d['identity']['currency']!='ZAc' or d['identity']['exchange']!='JNB':raise ValueError('JSE cents identity required')
 return d

def build(gold,benchmark,segment_index=-1):
 rows=[]
 for r in gold['rows']:
  if r['current_session_not_completed']:continue
  values={f:(r[f]/100 if f!='volume' and r.get(f) is not None else r.get(f)) for f in ('open','high','low','close','volume')}
  rows.append({'session':r['session'],**values})
 segments=[s for s in valid_segments(rows,('open','high','low','close','volume')) if len(s)>=52]
 if not segments:raise ValueError('no complete daily research window')
 seg=segments[segment_index];charts={'NEWGOLD':[{'timestamp':r['session'],**{f:r[f] for f in ('open','high','low','close','volume')},'_source':'YAHOO'} for r in seg]}
 charts['ETF_STX40']=[{'timestamp':r['session'],'close':r['close']/100} for r in benchmark['rows'] if not r['current_session_not_completed'] and r.get('close')]
 base=from_chart('NEWGOLD',{'bars':charts['NEWGOLD'],'provenance':{'provider':'YAHOO','source_sha256':sha256(json.dumps(gold,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),'acquired_at':gold['acquired_at']}})
 m=ObservedGoldUnits(**{**vars(base),'product':'GOLD_ETF'})
 adapter=GoldListed('ZAR','ZAR',m.calendar_basis,m.sessions,(),m.instrument)
 costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
 asof=max(b.available_at for b in m.bars)+timedelta(days=8);results=[]
 for sid,name,profile,version in PROFILES:
  signals=[];traces=[];rejected=[];passed=None;checked=0;conds=[]
  for i in range(50,len(seg)):
   conds,stop=evaluate_mixed(sid,'NEWGOLD',i,charts)
   if not conds:continue
   checked+=1
   if passed is None:passed=[0]*len(conds)
   for j in range(len(conds)):
    if all(c['ok'] for c in conds[:j+1]):passed[j]+=1
   day=seg[i]['session']
   if not all(c['ok'] for c in conds):rejected.append({'inst':'NEWGOLD','session':day,'trace':conds})
   elif stop is not None:
    ident='NEWGOLD-'+day
    signals.append(Signal(ident,'NEWGOLD',day,m.bars[i].available_at+timedelta(seconds=1),Decimal(str(stop)),Decimal(420000),Decimal(12000),horizon=3,target_r=Decimal(2),strategy_profile_id=profile,strategy_profile_version=version))
    traces.append({'id':ident,'inst':'NEWGOLD','session':day,'stop':stop,'trace':conds})
  run=replay([m],signals,as_of=asof,initial_cash=Decimal(1000000),costs=costs,adapters={'NEWGOLD':adapter})
  trades=run['trades'];equity=run['equity'];peak=1000000;dd=0
  for x in equity:
   v=float(x['equity']);peak=max(peak,v);dd=min(dd,v/peak-1)
  net=float(equity[-1]['equity'])-1000000 if equity else 0
  results.append({'id':sid,'name':name,'source':'JSE NewGold units; Yahoo daily capture',
   'desc':'Fixed three-session horizon or 2R; no EMA21-close exit. ETF volume is traded units, not spot gold volume.',
   'strategy_profile_id':profile,'strategy_profile_version':version,'conds':[c['c'] for c in conds],
   'funnel':{'checked':checked,'passed':passed or []},'sum':{'signals':len(signals),'traded':len(trades),
   'win':round(sum(float(t['net_pnl'])>0 for t in trades)/len(trades)*100) if trades else None,
   'net':round(net,2),'mdd':round(dd*100,2),'stocks':int(bool(trades)),
   'verdict':'Incubate: fewer than 30 trades, inconclusive' if len(trades)<30 else 'Watchlist: single vehicle'},
   'engine_config_hash':run['config_hash'],'run':{'signals':traces,'rejected_bars':rejected,'decisions':run['decisions'],'trades':trades,'equity':equity}})
 meta={'grade':'ASSUMPTION_LIMITED','limitations':['JSE_GOLD_UNITS_NOT_SPOT_GOLD','YAHOO_CAPTURE_NOT_RAW_RESPONSE',
  'RECONSTRUCTED_HISTORICAL_AVAILABILITY','PRICE_ADJUSTMENT_AND_CORPORATE_ACTIONS_UNVERIFIED','FULL_FILL_ASSUMPTION',
  'CLOSE_PROXY_NOT_BROKER_FILL','DAILY_INTRABAR_PATH_UNKNOWN','ONE_COMPLETE_CONTIGUOUS_SEGMENT_PER_RUN'],
  'cost_basis':costs.basis,'initial_cash':1000000,'created_at':asof.isoformat(),
  'created_at_basis':'RECONSTRUCTED_REPLAY_AS_OF_NOT_WALL_CLOCK','data_basis':'JSE_NEWGOLD_UNITS_YAHOO_RESEARCH',
  'source_receipts':[{'instrument':'NEWGOLD','product':'GOLD_ETF','provider':'YAHOO','acquired_at':gold['acquired_at'],'source_sha256':sha256(json.dumps(gold,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()},
   {'instrument':'ETF_STX40','provider':'YAHOO','acquired_at':benchmark['acquired_at'],'source_sha256':sha256(json.dumps(benchmark,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}],
  'eligible_segments':[[s[0]['session'],s[-1]['session']] for s in segments],
  'selected_segment_index':segment_index,'live_execution':False}
 bars={'NEWGOLD':[[r['session'],r['open'],r['high'],r['low'],r['close']] for r in seg]}
 identity={'meta':meta,'bars':bars,'strategies':results};digest=sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
 return {**identity,'meta':{**meta,'config_hash':digest}}

def main():
 p=argparse.ArgumentParser();p.add_argument('--gold',required=True);p.add_argument('--benchmark',required=True);p.add_argument('--output-dir',required=True)
 p.add_argument('--segment-index',type=int,default=-1,help='Eligible history segment index, default latest');a=p.parse_args()
 run=build(load(a.gold,'GLD.JO'),load(a.benchmark,'STX40.JO'),a.segment_index);folder=Path(a.output_dir)/'lab';folder.mkdir(parents=True,exist_ok=True)
 target=folder/(run['meta']['config_hash']+'.json');raw=(json.dumps(run,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
 if target.exists() and target.read_bytes()!=raw:raise ValueError('frozen report collision')
 if not target.exists():target.write_bytes(raw)
 print(json.dumps({'run_id':target.stem,'path':str(target),'first':run['bars']['NEWGOLD'][0][0],'last':run['bars']['NEWGOLD'][-1][0],
  'results':{s['id']:{'checked':s['funnel']['checked'],'signals':s['sum']['signals'],'trades':s['sum']['traded'],'net':s['sum']['net']} for s in run['strategies']}}))
if __name__=='__main__':main()
