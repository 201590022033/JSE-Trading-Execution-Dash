import unittest
from application.backtest_lab.sasol_timeline import context_at,hypothesis_labels,supplementary_facts,topic_quotes

class SasolTimelineTests(unittest.TestCase):
 def test_missing_context_keeps_available_stock_and_unknown_questions(self):
  rows=[{'session':'2026-01-02','close':100,'fields':{'close':{'provider':'TEST'}}}]
  result=context_at('2026-01-05',rows,[],[],[])
  self.assertEqual(result['stock']['last_on_or_before']['close'],100)
  self.assertTrue(all(x['state']=='UNKNOWN' for x in hypothesis_labels(result)))
 def test_future_proxy_row_is_never_used(self):
  rows=[{'session':f'2026-01-0{i}','close':float(10-i),'current_session_not_completed':False} for i in range(1,8)]
  rows.append({'session':'2026-01-08','close':99999,'current_session_not_completed':False})
  context=context_at('2026-01-08',[],[],rows,[])
  self.assertEqual(context['brent_5_observed_session_return']['end_session'],'2026-01-07')
  self.assertEqual(hypothesis_labels(context)[0]['state'],'YES')
 def test_dividend_value_requires_explicit_unit_and_keeps_quote(self):
  facts=supplementary_facts('Final dividend (Rand per share) 2,00 7,00 (71)%')
  self.assertEqual(len(facts),1);self.assertEqual(facts[0]['value'],2)
  self.assertEqual(facts[0]['period_basis'],'UNKNOWN');self.assertEqual(facts[0]['unit'],'ZAR_per_share')
  self.assertEqual(supplementary_facts('Final dividend was excellent.'),[])
  self.assertEqual(topic_quotes('Production increased. Net debt was reported.')[0]['topic'],'production')
 def test_timeline_api_rejects_modified_report(self):
  import tempfile,json,hashlib
  from pathlib import Path
  from flask import Flask
  from application.backtest_lab.blueprint import create_backtest_lab_blueprint
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'context-research';folder.mkdir()
   data={'schema':'sasol-research-timeline-v1','events':[],'cases':[],'live_execution':False}
   raw=json.dumps(data).encode();digest=hashlib.sha256(raw).hexdigest();path=folder/(digest+'.json');path.write_bytes(raw)
   app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
   good=client.get('/api/v1/backtest-lab/sasol-timeline')
   self.assertEqual(good.status_code,200);self.assertEqual(good.headers['Cache-Control'],'no-store')
   self.assertFalse(good.json['live_execution']);path.write_bytes(raw+b' ')
   self.assertEqual(client.get('/api/v1/backtest-lab/sasol-timeline').status_code,503)

if __name__=='__main__':unittest.main()
