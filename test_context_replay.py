import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from application.backtest_lab.components import Components,signal_for
from application.backtest_lab.context_replay import compare
from application.backtest_lab.research_context import fundamental_facts
from domain.backtest.component_engine import Costs,replay
from research.fixtures.daily_oracle import fixture

class ContextReplayTests(unittest.TestCase):
 def setUp(self):
  from dataclasses import replace
  original=fixture();self.manifest=replace(original,sessions=original.sessions[:len(original.bars)]);self.config=Components();m=self.manifest
  self.signal=signal_for(self.config,m.instrument,'0',m.bars[0].available_at+timedelta(seconds=1),90)
  costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
  result=replay([m],[self.signal],as_of=m.bars[-1].available_at+timedelta(days=8),initial_cash=1000000,costs=costs)
  self.baseline={'observations':[{'session':'0','state':'SIGNAL'}],
    'signals':[{'id':self.signal.id,'session':'0','stop':90}],
    'trades':result['trades'],'decisions':result['decisions'],'equity':result['equity']}
 def event(self,delta):
  stamp=(self.signal.decision_at+timedelta(hours=delta)).isoformat()
  return {'kind':'NEWS','source_id':'event','instrument':self.manifest.instrument,
    'published_at':stamp,'acquired_at':stamp,'source_received_at':stamp,'received_at':stamp}
 def test_missing_context_preserves_exact_replay(self):
  with patch('application.backtest_lab.context_replay.run_components',return_value=self.baseline):
   result=compare(self.config,self.manifest,{},[])
  self.assertEqual(result['candidate']['trades'],self.baseline['trades'])
  self.assertEqual(result['candidate']['decisions'],self.baseline['decisions'])
 def test_earlier_context_suppresses_only_when_available(self):
  with patch('application.backtest_lab.context_replay.run_components',return_value=self.baseline):
   before=compare(self.config,self.manifest,{},[self.event(-1)])
   after=compare(self.config,self.manifest,{},[self.event(1)])
  self.assertEqual(before['context_checks'][0]['candidate_state'],'CONTEXT_SUPPRESSED')
  self.assertEqual(before['candidate']['trades'],[])
  self.assertEqual(after['candidate']['trades'],self.baseline['trades'])
 def test_proxy_rule_changes_replay_without_blocking_missing_context(self):
  with patch('application.backtest_lab.context_replay.run_components',return_value=self.baseline):
   with patch('application.backtest_lab.proxy_context.prior_return',return_value={'return':-.05}):
    falling=compare(self.config,self.manifest,{},[],proxy_rule='skip_brent_falling')
   with patch('application.backtest_lab.proxy_context.prior_return',return_value=None):
    missing=compare(self.config,self.manifest,{},[],proxy_rule='skip_brent_falling')
  self.assertEqual(falling['candidate']['trades'],[])
  self.assertEqual(missing['candidate']['trades'],self.baseline['trades'])
  self.assertIn('PROXY_CAPTURED_LATER_RETROSPECTIVE_NOT_PROSPECTIVE',falling['limitations'])
 def test_fundamental_fact_requires_explicit_quoted_change(self):
  item={'excerpt':'Revenue increased by 12.5% and earnings per share fell by 7 per cent.',
        'source_id':'s','url':'https://example.com','revision_id':'v1'}
  facts=fundamental_facts(item)
  self.assertEqual([x['change_pct'] for x in facts],[12.5,-7])
  self.assertEqual(facts[0]['period'],'UNKNOWN')
  self.assertIn('Revenue increased by 12.5%',facts[0]['quote'])
  self.assertEqual(fundamental_facts({'excerpt':'Revenue was strong.'}),[])
 def test_report_api_is_read_only_and_checks_integrity(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from flask import Flask
  from application.backtest_lab.blueprint import create_backtest_lab_blueprint
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'context-research';folder.mkdir()
   body={'schema':'m5-matched-context-study-v1','instrument':'SOL','created_at':'2026-11-05T10:00:00Z',
         'results':{'train':{'baseline':{'signals':[],'trades':[]},'candidate':{'signals':[],'trades':[]},'context_checks':[]}},'live_execution':False}
   raw=json.dumps(body).encode();digest=hashlib.sha256(raw).hexdigest();path=folder/(digest+'.json');path.write_bytes(raw)
   app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
   listing=client.get('/api/v1/backtest-lab/context-matched')
   self.assertEqual(listing.status_code,200);self.assertEqual(listing.headers['Cache-Control'],'no-store')
   self.assertFalse(listing.json['live_execution']);self.assertEqual(len(listing.json['reports']),1)
   self.assertEqual(client.get('/api/v1/backtest-lab/context-matched/'+digest).status_code,200)
   path.write_bytes(raw+b' ')
   self.assertEqual(client.get('/api/v1/backtest-lab/context-matched/'+digest).status_code,404)

if __name__=='__main__':unittest.main()
