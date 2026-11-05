import unittest
from copy import deepcopy
from application.backtest_lab.research_context import sens_item,hermes_items,calendar_item,evaluate
from application.backtest_lab.zebra_field_windows import benchmark_for

class ResearchContextTests(unittest.TestCase):
 def setUp(self):
  self.record={'record_id':'sens-one','body':'Sasol update\nEvidence','source_url':'https://example.com/a',
   'published_at':'2026-11-03T08:00:00Z','received_at':'2026-11-03T09:02:00Z',
   'sens_provenance':{'share_code':'SOL','source_id':'fixture','detail_acquired_at':'2026-11-03T09:00:00Z',
    'detail_received_at':'2026-11-03T09:01:00Z','publication':{'precision':'timestamp','value':'2026-11-03'},'detail_raw_hash':'sha256:abc'}}
 def test_receipts_publication_and_revisions_are_not_backdated(self):
  first=sens_item(self.record);later=deepcopy(self.record)
  later.update(record_id='sens-two',body='Sasol update\nRevised',received_at='2026-11-03T12:02:00Z')
  later['sens_provenance']['detail_acquired_at']='2026-11-03T12:00:00Z'
  later['sens_provenance']['detail_received_at']='2026-11-03T12:01:00Z'
  report=evaluate([first,sens_item(later)],'SASOL','2026-11-03T10:00:00Z')
  self.assertEqual([x['source_id'] for x in report['available']],['sens-one'])
  self.assertEqual(report['annotations'][0]['eligibility'],'AFTER_DECISION')
  self.assertNotEqual(first['content_sha256'],sens_item(later)['content_sha256'])
  self.assertTrue(report['price_only_allowed'])
 def test_unknown_publication_or_acquisition_remains_annotation(self):
  r=deepcopy(self.record);r['published_at']=None;r['sens_provenance']['publication']['precision']='date'
  report=evaluate([sens_item(r)],'SASOL','2026-11-04T00:00:00Z')
  self.assertEqual(report['annotations'][0]['eligibility'],'CLOCK_UNKNOWN')
  self.assertEqual(report['annotations'][0]['publication_date'],'2026-11-03')
  self.assertEqual(evaluate([sens_item(r)],'BTI','2026-11-04T00:00:00Z')['counts']['annotations'],0)
 def test_stock_only_and_broad_benchmark_fallback(self):
  self.assertEqual(benchmark_for({'sector':'Energy'}, {}, '2026-11-03')['basis'],'NO_BENCHMARK_STOCK_ONLY')
  stocks={'ETF_STX40':{'rows':[{'session':'2026-11-03','close':100}]}}
  self.assertEqual(benchmark_for({'sector':'Energy'},stocks,'2026-11-03')['basis'],'BROAD_MARKET_FALLBACK')
  stocks['ETF_STXRES']={'rows':[{'session':'2026-11-03','close':100}]}
  self.assertEqual(benchmark_for({'sector':'Energy'},stocks,'2026-11-03')['instrument'],'ETF_STXRES')
 def test_hermes_direct_issuer_mapping_does_not_invent_acquisition_time(self):
  capture={'capture_id':'c1','received_at':'2026-11-03T11:00:00Z','articles':[
   {'headline':'Sasol reports production','summary':'An update','url':'https://example.com/n',
    'received_at':'2026-11-03T10:00:00Z','timestamp':'2026-11-03T09:00:00Z','timestamp_kind':'published'}]}
  items=hermes_items(capture)
  self.assertEqual(items[0]['instrument'],'SASOL');self.assertIsNone(items[0]['acquired_at'])
  self.assertEqual(evaluate(items,'SASOL','2026-11-04T00:00:00Z')['annotations'][0]['eligibility'],'CLOCK_UNKNOWN')
 def test_context_api_reads_hash_checked_reports_without_model_calls(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from flask import Flask
  from application.backtest_lab.blueprint import create_backtest_lab_blueprint
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'context-research';folder.mkdir()
   body={'schema':'m5-sens-coverage-v1','instrument':'SASOL','created_at':'2026-11-05T10:00:00Z',
    'coverage':{'cases':2},'relevant_sources':[],'experiment_id':'e1','live_execution':False}
   raw=json.dumps(body).encode();digest=hashlib.sha256(raw).hexdigest();path=folder/(digest+'.json');path.write_bytes(raw)
   app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
   listing=client.get('/api/v1/backtest-lab/context-research')
   self.assertEqual(listing.status_code,200);self.assertEqual(listing.headers['Cache-Control'],'no-store')
   self.assertFalse(listing.json['live_execution']);self.assertEqual(len(listing.json['reports']),1)
   self.assertEqual(client.get('/api/v1/backtest-lab/context-research/'+digest).status_code,200)
   path.write_bytes(raw+b' ');self.assertEqual(client.get('/api/v1/backtest-lab/context-research/'+digest).status_code,404)
 def test_macro_calendar_clocks_and_fundamental_tags(self):
  m=calendar_item({'record_id':'m1','title':'CPI','body':'Consumer price inflation release',
   'source_url':'https://example.com/cpi','published_at':'2026-11-03T08:00:00Z',
   'captured_at':'2026-11-03T09:00:00Z','received_at':'2026-11-03T09:01:00Z'})
  self.assertEqual(evaluate([m],'SASOL','2026-11-03T10:00:00Z')['counts']['available'],1)
  self.assertEqual(evaluate([m],'SASOL','2026-11-03T08:30:00Z')['counts']['available'],0)
  r=deepcopy(self.record);r['body']='Sasol results\nRevenue and dividend updates'
  self.assertEqual(sens_item(r)['fundamental_tags'],['results','dividend'])
 def test_proxy_subset_uses_only_prior_completed_sessions(self):
  from application.backtest_lab.proxy_context import prior_return,compare
  rows=[{'session':f'2026-01-0{i}','close':i,'current_session_not_completed':False} for i in range(1,8)]
  rows.append({'session':'2026-01-08','close':999,'current_session_not_completed':False})
  result=prior_return(rows,'2026-01-08');self.assertEqual(result['end_session'],'2026-01-07')
  self.assertAlmostEqual(result['return'],7/2-1)
  artifact={'control':{'signals':[{'id':'s','session':'2026-01-08'}],
   'trades':[{'id':'s','instrument':'SASOL','entry_session':'2026-01-09','exit_session':'2026-01-10','net_pnl':'100'}]}}
  report=compare(artifact,{'BRENT':{'rows':rows}})
  self.assertEqual(report['comparisons']['BRENT']['positive_proxy_filter']['trades'],1)
  self.assertFalse(report['model_context_eligible'])

if __name__=='__main__':unittest.main()
