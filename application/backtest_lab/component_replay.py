"""Bounded, deterministic component replays; candidate settings are explicit."""
from datetime import timedelta
from decimal import Decimal
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from application.backtest_lab.components import VERSION,evaluate,signal_for
from domain.backtest.component_engine import Costs,replay


def run_components(config,manifest,charts,*,adapter=None,costs=None,decision_start=None):
 rows=charts[manifest.instrument]
 if len(rows)!=len(manifest.bars):raise ValueError('exact chart/manifest alignment required')
 from application.backtest_lab.zebra_field_windows import valid_segments
 required=('open','high','low','close') if config.volume_mode=='off' else ('open','high','low','close','volume')
 observed=[{**r,'session':r['timestamp'][:10]} for r in rows]
 segments=valid_segments(observed,required)
 if len(segments)!=1 or len(segments[0])!=len(rows):
  raise ValueError('component replay requires one complete contiguous observed segment')
 if any(row['timestamp'][:10]!=bar.session for row,bar in zip(rows,manifest.bars)):
  raise ValueError('session identity mismatch')
 signals=[];traces=[];observations=[]
 for i in range(len(rows)):
  if decision_start is not None and rows[i]['timestamp'][:10]<decision_start:continue
  trace,stop=evaluate(config,manifest.instrument,i,charts)
  state='UNKNOWN' if any(x['state']=='UNKNOWN' for x in trace) else 'SIGNAL' if trace and all(x['ok'] for x in trace) else 'NO_SIGNAL'
  day=rows[i]['timestamp'][:10]
  observations.append({'instrument':manifest.instrument,'session':day,'state':state,'trace':trace})
  if state=='SIGNAL':
   s=signal_for(config,manifest.instrument,day,manifest.bars[i].available_at+timedelta(seconds=1),stop)
   signals.append(s);traces.append({'id':s.id,'inst':manifest.instrument,'session':day,'stop':stop,'trace':trace})
 asof=max(b.available_at for b in manifest.bars)+timedelta(days=8)
 selected_costs=costs or Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
 result=replay([manifest],signals,as_of=asof,initial_cash=Decimal(1000000),costs=selected_costs,
               adapters={manifest.instrument:adapter} if adapter is not None else None)
 component_dir=Path(__file__).resolve().parent
 code_hashes={name:sha256((component_dir/name).read_bytes()).hexdigest() for name in ('components.py','component_replay.py')}
 engine_path=component_dir.parent.parent/'domain'/'backtest'/'component_engine.py'
 code_hashes['component_engine.py']=sha256(engine_path.read_bytes()).hexdigest()
 return {'version':VERSION,'code_sha256':code_hashes,'config':asdict(config),'config_hash':config.config_hash,'decision_start':decision_start,'instrument':manifest.instrument,
         'data_hash':manifest.sha256,'as_of':asof.isoformat(),'observations':observations,'signals':traces,
         'decisions':result['decisions'],'trades':result['trades'],'equity':result['equity'],
         'engine_config_hash':result['config_hash'],'limitations':result['limitations'],
         'cost_basis':result['cost_basis'],'live_execution':False}
