import unittest
from dataclasses import replace
from datetime import datetime,timezone
from unittest.mock import patch
from application.backtest_lab.components import Components,evaluate,signal_for

class ComponentTests(unittest.TestCase):
 def setUp(self):
  self.row={'timestamp':'2026-03-02','open':99,'high':102,'low':98,'close':101,'volume':None}
  self.snap={'state':'PARTIAL','last_close':101,'values':{'ema20':100,'rsi14_wilder':55,'relative_volume20':None,
    'relative_return20':None,'atr14_wilder':2,'prior_low10':90},
    'geometry':{'stop':90},'conditions':{'ema_uptrend':True,'breakout20':True,'ema20_reclaim':False,'outperforming_benchmark20':None}}
 def check(self,c):
  with patch('application.backtest_lab.components.snapshot',return_value=self.snap) as called:
   result=evaluate(c,'SOL',0,{'SOL':[self.row]})
   self.assertIsNone(called.call_args.kwargs['benchmark_chart'])
   self.assertIsNone(called.call_args.args[0]['bars'][0]['volume'])
   return result
 def test_missing_is_unknown_and_disabled_is_real_control(self):
  base=Components(); trace,_=self.check(base)
  self.assertEqual(next(x['state'] for x in trace if x['c']=='Volume'),'UNKNOWN')
  c=replace(base,volume_mode='off',benchmark_mode='off');trace,_=self.check(c)
  self.assertTrue(all(x['ok'] for x in trace)); self.assertIsNone(next(x['v'] for x in trace if x['c']=='Volume'))
 def test_entry_variants_and_geometry_are_independent(self):
  b=replace(Components(),volume_mode='off',benchmark_mode='off')
  for mode,expected in [('breakout_or_reclaim',True),('breakout',True),('reclaim',False),('trend_only',True)]:
   trace,_=self.check(replace(b,entry=mode));self.assertEqual(next(x['ok'] for x in trace if x['c']=='Entry'),expected)
  self.assertEqual(self.check(replace(b,stop_mode='structure'))[1],90)
  self.assertEqual(self.check(replace(b,stop_mode='atr',atr_multiple=2))[1],97)
  self.assertAlmostEqual(self.check(replace(b,stop_mode='percent',stop_pct=.05))[1],95.95)
 def test_engine_signal_receives_exit_and_risk_parameters(self):
  b=Components();c=replace(b,horizon=5,target_r=1.5,trail='ATR',trail_k=2,risk_budget=6000,max_notional=50000)
  s=signal_for(c,'SOL','2026-03-02',datetime(2026,3,3,tzinfo=timezone.utc),90)
  self.assertEqual((s.horizon,float(s.target_r),s.trail,float(s.trail_k),int(s.risk_budget),int(s.max_notional)),(5,1.5,'ATR',2,6000,50000))
  self.assertNotEqual(b.config_hash,c.config_hash)
 def test_rejects_unsupported_or_misattributed_components(self):
  for kw in ({'family':'box'},{'horizon':7},{'profile_id':'box_breakout_daily_research'},{'stop_mode':'EMA21'}):
   with self.assertRaises((ValueError,KeyError)):Components(**kw)
 def test_existing_family_rules_are_reused_and_volume_can_be_disabled(self):
  from application.opportunities.session_freshness import next_session
  from application.backtest_lab.zebra_field_windows import evaluate_mixed
  day='2026-01-02';rows=[]
  for i in range(60):
   close=100+i*.08 if i<59 else 110
   rows.append({'timestamp':day,'open':close-.1,'high':close+.2,'low':close-.2,
                'close':close,'volume':2000 if i==59 else 1000,'_source':'YAHOO'})
   day=next_session(day)
  for family,profile in [('box','box_breakout_daily_research'),('vcp','vcp_daily_research'),('pull','pullback_daily_research')]:
   config=Components(family=family,profile_id=profile,profile_version='1.0.0',entry='family_default',
                     momentum=False,benchmark_mode='off',stop_mode='family',volume_mode='off')
   trace,stop=evaluate(config,'SOL',59,{'SOL':rows})
   old,old_stop=evaluate_mixed(family,'SOL',59,{'SOL':rows})
   self.assertEqual(stop,old_stop)
   self.assertEqual([x['c'] for x in trace],[x['c'] for x in old])
   self.assertTrue(next(x['ok'] for x in trace if x['c'] in ('Volume','Volume surge')))
   from application.backtest_lab.components import _family_without_volume
   price_only,price_stop=_family_without_volume(family,rows)
   self.assertEqual(price_stop,old_stop)
   self.assertEqual([(x['c'],x['v'],x['ok']) for x in price_only if x['c']!='Volume'],
                    [(x['c'],x['v'],x['ok']) for x in old if x['c']!='Volume'])
   missing=[dict(row,volume=None) for row in rows]
   trace,stop=evaluate(config,'SOL',59,{'SOL':missing})
   self.assertEqual(stop,old_stop)
   self.assertIsNone(next(x['v'] for x in trace if x['c']=='Volume'))
   self.assertTrue(next(x['ok'] for x in trace if x['c']=='Volume'))
   for entry in ('trigger_only','trend_only'):
    trace,_=evaluate(replace(config,entry=entry,momentum=True),'SOL',59,{'SOL':rows})
    self.assertTrue(any('entry condition disabled' in x['t'] for x in trace))
    self.assertTrue(any(x['c']=='Momentum' for x in trace))
 def test_real_snapshot_replay_is_repeatable_and_rejects_a_gap(self):
  from application.opportunities.session_freshness import next_session
  from application.backtest_lab.observed_history import from_chart
  from application.backtest_lab.component_replay import run_components
  day='2026-01-02';rows=[]
  for i in range(70):
   close=100+i*.08
   rows.append({'timestamp':day,'open':close-.1,'high':close+.2,'low':close-.2,'close':close,'volume':1000})
   day=next_session(day)
  provenance={'provider':'TEST','source_sha256':'a'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}
  manifest=from_chart('SOL',{'bars':rows,'provenance':provenance})
  config=Components(volume_mode='off',benchmark_mode='off')
  result=run_components(config,manifest,{'SOL':rows})
  self.assertEqual(result,run_components(config,manifest,{'SOL':rows}))
  self.assertEqual(len(result['observations']),70)
  self.assertIn('components.py',result['code_sha256'])
  damaged=rows[:20]+rows[21:]
  broken=from_chart('SOL',{'bars':damaged,'provenance':provenance})
  with self.assertRaisesRegex(ValueError,'contiguous'):run_components(config,broken,{'SOL':damaged})
 def test_frozen_component_api_rejects_tampered_study(self):
  import json,hashlib,tempfile
  from pathlib import Path
  from flask import Flask
  from application.backtest_lab.blueprint import create_backtest_lab_blueprint
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'component-research';folder.mkdir()
   body={'schema':'bounded-component-diagnostic-v1','live_execution':False,'window':['2026-01-02','2026-03-20'],
         'trial_count':1,'trials':[{'name':'baseline','result':{'instrument':'SOL'}}]}
   raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
   path=folder/(digest+'.json');path.write_bytes(raw)
   app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
   listing=client.get('/api/v1/backtest-lab/component-studies')
   self.assertEqual(listing.status_code,200);self.assertFalse(listing.json['live_execution'])
   self.assertEqual(listing.headers['Cache-Control'],'no-store');self.assertEqual(listing.json['studies'][0]['study_id'],digest)
   self.assertEqual(client.get('/api/v1/backtest-lab/component-studies/'+digest).status_code,200)
   path.write_bytes(raw+b' ')
   self.assertEqual(client.get('/api/v1/backtest-lab/component-studies/'+digest).status_code,404)
 def test_versioned_engine_trailing_activation_and_next_session(self):
  from decimal import Decimal as D
  from dataclasses import replace
  from research.fixtures.daily_oracle import fixture
  from domain.backtest.component_engine import Signal,replay,Costs
  m=fixture([(100,101,99,100),(100,103,99,102),(102,130,91,115),(116,117,108,110),(110,111,100,105)])
  s=Signal('s1',m.instrument,'0',m.sessions[0].close_at,D(90),D(1100),D(120),
           trail='ATR',atr_period=1,trail_k=D('.1'),target_r=None)
  def run(x):return replay((m,),(x,),as_of=m.sessions[4].close_at,initial_cash=2000,costs=Costs(minimum_fee=2))
  low=run(s);high=run(replace(s,trail_activation_r=D(2)))
  self.assertIn('TRAIL_NEXT_SESSION',[x['state'] for x in low['decisions']])
  self.assertNotIn('TRAIL_NEXT_SESSION',[x['state'] for x in high['decisions']])
  self.assertEqual(low['trades'][0]['exit_session'],'3')
  self.assertEqual(low['trades'][0]['exit'],'111.1')
 def test_versioned_default_preserves_prior_engine_results(self):
  from decimal import Decimal as D
  from research.fixtures.daily_oracle import fixture
  from domain.backtest.engine import Signal as OldSignal,replay as old_replay,Costs as OldCosts
  from domain.backtest.component_engine import Signal,replay,Costs
  m=fixture();args=('s1',m.instrument,'0',m.sessions[0].close_at,D(90),D(1100),D(120))
  old=old_replay((m,),(OldSignal(*args),),as_of=m.sessions[4].close_at,initial_cash=2000,costs=OldCosts(minimum_fee=2))
  new=replay((m,),(Signal(*args),),as_of=m.sessions[4].close_at,initial_cash=2000,costs=Costs(minimum_fee=2))
  for field in ('cash','trades','decisions','equity','ledger'):self.assertEqual(old[field],new[field])
 def test_versioned_engine_horizon_and_sizing_change_outcomes(self):
  from decimal import Decimal as D
  from dataclasses import replace
  from research.fixtures.daily_oracle import fixture
  from domain.backtest.component_engine import Signal,replay
  prices=[(100,101,99,100)]+[(102+i,104+i,101+i,102+i) for i in range(8)]
  m=fixture(prices);s=Signal('s',m.instrument,'0',m.sessions[0].close_at,D(90),D(1100),D(120),target_r=None)
  def run(x):return replay((m,),(x,),as_of=m.sessions[len(m.bars)-1].close_at,initial_cash=2000)
  for horizon in (3,4,5):self.assertEqual(run(replace(s,horizon=horizon))['trades'][0]['held'],horizon)
  small=run(replace(s,risk_budget=D(30)))['trades'][0]
  large=run(s)['trades'][0]
  self.assertLess(D(small['quantity']),D(large['quantity']))
  bars=m.bars[:2]+(replace(m.bars[2],open=D(102),high=D(121),low=D(95),close=D(105)),)+m.bars[3:]
  target_manifest=replace(m,bars=bars)
  def with_target(target):return replay((target_manifest,),(replace(s,target_r=D(target)),),as_of=target_manifest.sessions[len(target_manifest.bars)-1].close_at,initial_cash=2000)
  self.assertEqual(with_target('1.5')['trades'][0]['reason'],'TARGET')
  self.assertNotEqual(with_target('2')['trades'][0]['reason'],'TARGET')
 def test_versioned_engine_ema_exit_and_ambiguous_stop(self):
  from decimal import Decimal as D
  from dataclasses import replace
  from datetime import timedelta
  from research.fixtures.daily_oracle import fixture
  from domain.backtest.component_engine import Signal,replay
  from domain.backtest.data import Session,Bar,Manifest
  bars=[(100,101,99,100)]*22+[(102,103,99,102),(102,103,94,95),(95,96,94,95),(95,96,94,95)]
  start=datetime(2026,1,1,tzinfo=timezone.utc)
  sessions=tuple(Session(str(i),start+timedelta(days=i,hours=7),start+timedelta(days=i,hours=15)) for i in range(len(bars)))
  observations=tuple(Bar(str(i),sessions[i].close_at,*(D(v) for v in row),D(1000)) for i,row in enumerate(bars))
  m=Manifest('TOY','EQUITY','ZAR','TEST',start,'RAW','TRADED_SHARES','TEST',True,'SYNTHETIC','TEST','NONE_VERIFIED','1',sessions,observations)
  s=Signal('e',m.instrument,'21',m.sessions[21].close_at,D(90),D(1100),D(120),horizon=5,target_r=None,exit_mode='EMA21_CLOSE')
  r=replay((m,),(s,),as_of=m.sessions[len(m.bars)-1].close_at,initial_cash=2000)
  self.assertEqual(r['trades'][0]['reason'],'EMA21_CLOSE');self.assertEqual(r['trades'][0]['exit_session'],'23')
  m=fixture();m=replace(m,bars=m.bars[:2]+(replace(m.bars[2],open=D(102),high=D(130),low=D(89),close=D(100)),)+m.bars[3:])
  s=Signal('x',m.instrument,'0',m.sessions[0].close_at,D(90),D(1100),D(120))
  r=replay((m,),(s,),as_of=m.sessions[len(m.bars)-1].close_at,initial_cash=2000)
  self.assertEqual(r['trades'][0]['reason'],'AMBIGUOUS_STOP_FIRST')
if __name__=='__main__':unittest.main()
