import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint
from application.strategy_radar.shadow_service import retained_comparisons, retained_fill_backtests

TRACE={'instrument':'ABC','strategy_id':'intraday_5m_research_v1','strategy_version':'1.0.0',
       'timeframe_minutes':5,'evaluated_at':'2026-11-07T00:00:00+00:00','state':'UNKNOWN',
       'rules':[{'id':'volume','state':'UNKNOWN','reason':'missing'}],'limitations':['RESEARCH_ONLY']}

class RadarContextTests(unittest.TestCase):
 def setUp(self):
  app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda: object())); self.client=app.test_client()
  self.body={'instrument':'ABC','strategy_id':'intraday_5m_research_v1','strategy_version':'1.0.0','timeframe_minutes':5,'product':'CFD','role':'risk','question':'What is missing?'}
 @patch('application.strategy_radar.shadow_service.evaluate_watch',return_value=TRACE)
 @patch('application.backtest_lab.blueprint.desk_advice',return_value=('Research only','fixture'))
 def test_explicit_desk_rebuilds_context_and_checks_identity(self,advisor,evaluate):
  prompt=self.client.post('/api/v1/strategy-radar/desk',json={**self.body,'prompt_only':True})
  self.assertEqual(prompt.status_code,200); advisor.assert_not_called()
  self.assertEqual(prompt.json['context']['instrument'],'ABC'); self.assertEqual(prompt.json['context']['product'],'CFD')
  self.assertIn('shadow trace',prompt.json['prompt'])
  invalid=self.client.post('/api/v1/strategy-radar/desk',json={**self.body,'strategy_version':'wrong'})
  self.assertEqual(invalid.status_code,409); advisor.assert_not_called()
  answered=self.client.post('/api/v1/strategy-radar/desk',json=self.body)
  self.assertEqual(answered.status_code,200); advisor.assert_called_once()
  self.assertEqual(answered.json['context']['strategy_version'],'1.0.0')
  self.assertEqual(self.client.post('/api/v1/strategy-radar/desk',json=self.body,headers={'Origin':'https://other.example'}).status_code,403)
 @patch('application.strategy_radar.swing_radar.evaluate_watches')
 @patch('application.backtest_lab.blueprint.desk_advice',return_value=('Research only','fixture'))
 def test_daily_desk_rebuilds_trace_and_rejects_wrong_identity(self,advisor,evaluate):
  trace={'instrument':'ABC','strategy_id':'jse_swing_3_5d','strategy_version':'1.1.0',
         'timeframe_minutes':None,'evaluated_at':'2026-11-10T05:00:00+00:00','state':'WATCHING',
         'session':'2026-11-06','rules':[{'id':'ema','state':'PASS'}],
         'data_quality':{'stale':True,'provisional':True,'fields':[{'secret':'unbounded'}]}}
  evaluate.return_value={'ABC':trace}
  body={**self.body,'strategy_id':'jse_swing_3_5d','strategy_version':'1.1.0','timeframe_minutes':None,'product':'CASH_SHARE',
        'rules':[{'id':'forged','state':'PASS'}]}
  result=self.client.post('/api/v1/strategy-radar/desk',json={**body,'prompt_only':True})
  self.assertEqual(result.status_code,200); advisor.assert_not_called()
  self.assertEqual(result.json['context']['rules'],trace['rules'])
  self.assertTrue(result.json['context']['data_quality']['stale'])
  self.assertNotIn('fields',result.json['context']['data_quality'])
  self.assertIn('not a point-in-time backtest',result.json['prompt'])
  self.assertEqual(self.client.post('/api/v1/strategy-radar/desk',json={**body,'timeframe_minutes':5}).status_code,409)
  self.assertEqual(self.client.post('/api/v1/strategy-radar/desk',json={**body,'strategy_version':'wrong'}).status_code,409)
  self.assertEqual(self.client.post('/api/v1/strategy-radar/desk',json={**body,'instrument':'OTHER'}).status_code,404)
  advisor.assert_not_called()
  self.assertEqual(self.client.post('/api/v1/strategy-radar/desk',json=body).status_code,200)
  advisor.assert_called_once()
 def test_retained_evidence_is_hash_checked_and_version_matched(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'shadow-replays'; folder.mkdir()
   report={'instrument':'ABC','strategy_id':'intraday_5m_research_v1','strategy_version':'1.0.0','timeframe_minutes':5,'replay_as_of':'2026-11-07T00:00:00Z','round_trip_cost_bps':'10',
           'candidate':{'sample_count':2,'mean_net_bps':'-5'},'baseline':{'sample_count':4,'mean_net_bps':'-10'},'unknown_clock_record_indices':[2],
           'limitations':['HYPOTHETICAL_NEXT_BAR_NOT_A_FILL']}
   raw=(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode(); path=folder/(sha256(raw).hexdigest()+'.json');path.write_bytes(raw)
   service=SimpleNamespace(folder=Path(tmp))
   evidence=retained_comparisons(service,'ABC','intraday_5m_research_v1','1.0.0'); self.assertEqual(evidence[0]['description'],'LESS_NEGATIVE_THAN_BASELINE')
   self.assertEqual(evidence[0]['candidate']['sample_count'],2); self.assertEqual(evidence[0]['unknown_clock_count'],1)
   self.assertEqual(retained_comparisons(service,'ABC','intraday_5m_research_v1','2'),[])
   path.write_bytes(raw+b' ');self.assertEqual(retained_comparisons(service,'ABC','intraday_5m_research_v1','1.0.0'),[])

 def test_backtest_matches_exact_share_and_profile_and_exposes_loss(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'lab';folder.mkdir();(folder/('a'*64+'.json')).write_text('{}')
   def strategy(name,profile,version,net):
    return {'id':name,'name':name,'strategy_profile_id':profile,'strategy_profile_version':version,'timeframe_minutes':5,
            'run':{'trades':[{'instrument':'ABC','net_pnl':net,'entry_session':'2026-01-02','exit_session':'2026-01-05'},{'instrument':'OTHER','net_pnl':'999'}]}}
   run={'meta':{'grade':'REAL','cost_basis':'scenario','limitations':['ASSUMED_FILL'],'created_at':'2026-01-01','source_receipts':[{'instrument':'ABC','product':'cash_equity'}]},
        'strategies':[strategy('one','p','1','-10'),strategy('two','p','1','-5'),strategy('wrong','p','2','100')]}
   with patch('application.backtest_lab.blueprint._read',return_value=run), patch('domain.strategy.DEFAULT_STRATEGY_REGISTRY.resolve',return_value=object()), patch.dict('application.strategy_radar.shadow_service.PROFILES',{'p':{'timeframe_minutes':5}}):
    result=retained_fill_backtests('ABC','p','1',root=tmp)
    self.assertEqual(result[0]['label'],'LEAST_LOSS');self.assertEqual(result[0]['contender']['name'],'two')
    self.assertEqual(result[0]['contender']['sample_count'],1);self.assertEqual(result[0]['candidate_count'],2)
    self.assertEqual(result[0]['contender']['first_entry_session'],'2026-01-02')
    self.assertEqual(result[0]['contender']['last_exit_session'],'2026-01-05')
    self.assertEqual(retained_fill_backtests('MISSING','p','1',root=tmp),[])
    for strategy_row in run['strategies']: strategy_row.pop('timeframe_minutes')
    self.assertEqual(retained_fill_backtests('ABC','p','1',root=tmp),[])
    run['meta']['grade']='SYNTHETIC';self.assertEqual(retained_fill_backtests('ABC','p','1',root=tmp),[])

 def test_daily_evidence_requires_explicit_daily_timeframe(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'lab';folder.mkdir();(folder/('a'*64+'.json')).write_text('{}')
   strategy={'id':'s','name':'Swing','strategy_profile_id':'jse_swing_3_5d','strategy_profile_version':'1.1.0',
             'run':{'trades':[{'instrument':'ABC','entry_session':'2026-01-02','exit_session':'2026-01-05','net_pnl':'1'}]}}
   run={'meta':{'grade':'REAL','cost_basis':'scenario','limitations':['ASSUMED_FILL'],'source_receipts':[{'instrument':'ABC','product':'cash_equity'}]},'strategies':[strategy]}
   with patch('application.backtest_lab.blueprint._read',return_value=run):
    self.assertEqual(retained_fill_backtests('ABC','jse_swing_3_5d','1.1.0',root=tmp),[])
    strategy['timeframe']='1d'
    result=retained_fill_backtests('ABC','jse_swing_3_5d','1.1.0',root=tmp)
    self.assertEqual(result[0]['contender']['sample_count'],1)
    self.assertEqual(retained_fill_backtests('OTHER','jse_swing_3_5d','1.1.0',root=tmp),[])

 def test_unregistered_shadow_profile_skips_frozen_run_reads(self):
  with tempfile.TemporaryDirectory() as tmp, patch('application.backtest_lab.blueprint._read') as read:
   folder=Path(tmp)/'lab'; folder.mkdir(); (folder/('a'*64+'.json')).write_text('{}')
   self.assertEqual(retained_fill_backtests('ABC','intraday_5m_research_v1','1.0.0',root=tmp),[])
   read.assert_not_called()
