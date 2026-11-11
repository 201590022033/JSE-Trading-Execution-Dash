import tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from flask import Flask
from unittest.mock import patch
from application.strategy_radar.intraday_adapters import manual_viewpoint_rows,eodhd_intraday_rows,retain
from application.strategy_radar.intraday_store import IntradayCache,merge_bars
from application.strategy_radar.poll_gate import PollGate
from application.strategy_radar.service import RadarService
from application.strategy_radar.api import create_radar_blueprint

NOW=datetime(2026,11,6,15,0,tzinfo=timezone.utc)

class IntradayIntegrationTests(unittest.TestCase):
 def test_manual_unknown_clock_and_exact_volume(self):
  records=manual_viewpoint_rows('ABSPJ',[{'label':'06/11/2026 16:30','open':'22,986','high':'23,100','low':'22,937','close':'23,073'}],NOW)
  parsed=merge_bars(records)
  self.assertEqual(len(parsed['bars']),0)
  self.assertEqual(parsed['unknown_clock_records'][0]['fields']['close'],'230.73')
  self.assertIsNone(parsed['unknown_clock_records'][0]['source_timestamp'])
  with self.assertRaises(ValueError): manual_viewpoint_rows('ABSPJ',[{'label':'x','volume':'1.7M'}],NOW)
  with self.assertRaises(ValueError): manual_viewpoint_rows('ABSPJ',[{'label':'x'}],NOW)
 def test_manual_bad_field_does_not_discard_other_observations(self):
  records=manual_viewpoint_rows('ABSPJ',[{'label':'x','open':'10000','high':'9000','low':'9500','close':'10000'}],NOW)
  parsed=merge_bars(records)['unknown_clock_records'][0]
  self.assertIsNone(parsed['fields']['high'])
  self.assertEqual(parsed['fields']['close'],'100')
  self.assertIn('high',parsed['invalid_fields'])
 def test_eodhd_mapping_unit_clock_and_raw(self):
  start=int(datetime(2026,11,6,8,0,tzinfo=timezone.utc).timestamp())
  payload=[{'timestamp':start,'open':23000,'high':23100,'low':22900,'close':23050,'volume':100}]
  with self.assertRaises(ValueError): eodhd_intraday_rows('ABSPJ','ABG.JSE',payload,NOW,price_unit='ZAR_CENTS',unit_evidence='receipt',verified_mapping={})
  rows=eodhd_intraday_rows('ABSPJ','ABG.JSE',payload,NOW,price_unit='ZAR_CENTS',unit_evidence='receipt',verified_mapping={'ABSPJ':'ABG.JSE'})
  item=merge_bars(rows)['bars'][0]
  self.assertEqual(item['fields']['close']['selected']['value'],'230.5')
  self.assertEqual(item['bar_start'],'2026-11-06T08:00:00+00:00')
  self.assertIn('ABG.JSE',rows[0]['raw_payload'])
 def test_poll_disabled_and_persistent_limit(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'poll.db'; gate=PollGate(path)
   self.assertFalse(gate.reserve('EODHD','ABSPJ',NOW)['allowed'])
   self.assertTrue(gate.reserve('EODHD','ABSPJ',NOW,enabled=True)['allowed'])
   self.assertFalse(PollGate(path).reserve('EODHD','ABSPJ',NOW+timedelta(seconds=299),enabled=True)['allowed'])
   self.assertTrue(gate.reserve('EODHD','ABSPJ',NOW+timedelta(seconds=300),enabled=True)['allowed'])
 def test_eodhd_requires_entitlement_budget_and_reserves_on_attempt(self):
  from application.strategy_radar.eodhd_intraday import EODHDIntradayProvider
  with tempfile.TemporaryDirectory() as tmp:
   gate=PollGate(Path(tmp)/'poll.db'); cache=IntradayCache(Path(tmp)/'bars.db'); calls=[]
   class Response:
    status_code=200
    content=b'[{"timestamp":1793952000,"open":23000,"high":23100,"low":22900,"close":23050,"volume":100}]'
   def transport(url, **kw): calls.append((url,kw)); return Response()
   provider=EODHDIntradayProvider(gate,cache,transport,clock=lambda:NOW)
   args=dict(now=NOW,token='test-key',quota_remaining=10,daily_credit_limit=5,unit='ZAR_CENTS',unit_evidence='receipt',verified_mapping={'ABSPJ':'ABG.JSE'})
   self.assertEqual(provider.capture('ABSPJ','ABG.JSE',**args)['state'],'DISABLED')
   self.assertEqual(provider.capture('ABSPJ','ABG.JSE',enabled=True,**args)['state'],'ENTITLEMENT_UNVERIFIED')
   out=provider.capture('ABSPJ','ABG.JSE',enabled=True,entitlement_verified=True,**args)
   self.assertEqual(out['state'],'CAPTURED')
   self.assertEqual(len(calls),1)
   self.assertEqual(provider.capture('ABSPJ','ABG.JSE',enabled=True,entitlement_verified=True,**args)['state'],'RATE_LIMITED')
   self.assertEqual(len(calls),1)
   args['verified_mapping']['BTI']='BTI.JSE'
   self.assertEqual(provider.capture('BTI','BTI.JSE',enabled=True,entitlement_verified=True,**args)['state'],'BUDGET_EXHAUSTED')
   self.assertEqual(len(calls),1)
   args['now']=NOW-timedelta(days=1); args['daily_credit_limit']=100
   self.assertEqual(provider.capture('BTI','BTI.JSE',enabled=True,entitlement_verified=True,**args)['state'],'BUDGET_EXHAUSTED')
   self.assertEqual(len(calls),1)
   self.assertNotIn('test-key',str(out))

 def test_manual_quote_is_not_live_and_historical_is_not_substituted(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp); app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service)); client=app.test_client()
   body={'instrument':'NPN','symbol':'NPN','unit':'ZAR_CENTS','bid':'74600','ask':'78500','last':'75725'}
   with patch('application.opportunities.zebra_instruments.mappings',return_value={'NPN':'NPN'}):
    self.assertEqual(client.post('/api/v1/strategy-radar/quotes/manual',json=body).status_code,201)
   result=client.get('/api/v1/strategy-radar/quotes/NPN').json
   self.assertEqual(result['fields']['last']['selected']['value'],'757.25')
   self.assertEqual(result['fields']['last']['selected']['kind'],'MANUAL')
   self.assertIsNone(result['fields']['last']['selected']['source_time'])

 def test_api_manual_and_read_with_unverified_clock(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp); app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service)); client=app.test_client()
   body={'instrument':'ABSPJ','symbol':'ABG','unit':'ZAR_CENTS','interval_minutes':30,'rows':[{'label':'06/11/2026 16:30','close':'23,073'}]}
   with patch('application.opportunities.zebra_instruments.mappings',return_value={'ABSPJ':'ABG'}):
    self.assertEqual(client.post('/api/v1/strategy-radar/intraday/manual',json=body).status_code,201)
    body['symbol']='NPN';self.assertEqual(client.post('/api/v1/strategy-radar/intraday/manual',json=body).status_code,422)
   response=client.get('/api/v1/strategy-radar/intraday/ABSPJ')
   self.assertEqual(response.status_code,200)
   self.assertEqual(response.json['unknown_clock_records'][0]['fields']['close'],'230.73')
   self.assertEqual(response.json['bars'],[])

 def test_swing_quote_freshness_is_explicit_and_preserves_delay(self):
  from application.strategy_radar.quote_store import QuoteStore
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp); app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service)); client=app.test_client()
   now=datetime.now(timezone.utc)
   body={'instrument':'NPN','provider':'fixture','kind':'DELAYED','unit':'ZAR',
         'source_time':(now-timedelta(minutes=20)).isoformat(),'received_at':now.isoformat(),
         'delay_seconds':900,'last':'100'}
   QuoteStore(service.folder / 'quotes.sqlite3').put(body)
   self.assertEqual(client.get('/api/v1/strategy-radar/quotes/NPN').json['fields']['last']['selected']['kind'],'STALE')
   swing=client.get('/api/v1/strategy-radar/quotes/NPN?view=swing').json
   self.assertEqual(swing['fields']['last']['selected']['kind'],'DELAYED')
   self.assertEqual(swing['freshness_policy']['max_source_age_seconds'],1800)
   self.assertEqual(client.get('/api/v1/strategy-radar/quotes/NPN?view=invalid').status_code,422)

if __name__=='__main__': unittest.main()
