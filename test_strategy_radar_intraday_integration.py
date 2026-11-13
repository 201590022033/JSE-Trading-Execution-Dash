import tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from flask import Flask
from unittest.mock import patch
from application.strategy_radar.intraday_adapters import manual_viewpoint_rows,viewpoint_table_csv,eodhd_intraday_rows,retain
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
 def test_viewpoint_closing_print_does_not_discard_regular_bars(self):
  raw=(b'Date,Open,High,Low,Close,Volume\n'
       b'2026-11-05T14:45:00.000Z,23032,23051,22999,23039,35438.00\n'
       b'2026-11-05T15:00:00.000Z,23076,23076,23076,23076,905927\n')
  rows=viewpoint_table_csv(raw,'MTN','MTN.JSE',NOW,file_name='MTN.JSE.csv',
                          accept_operator_conventions=True)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]['bar_start'],'2026-11-05T14:45:00+00:00')
  self.assertEqual(rows[0]['fields']['volume'],'35438')

 def test_viewpoint_csv_normalizes_using_owner_accepted_conventions(self):
  raw=(b'"Date","Open","High","Low","Close","% Change","% Change vs Average","Volume"\n'
       b'"2026-11-06T08:00:00.000Z","23032.00","23051.00","22999.00","23039.00","0.03","0.02","19,944"\n')
  with self.assertRaises(ValueError):
   viewpoint_table_csv(raw,'MTN','MTN.JSE',NOW,file_name='sample.csv')
  rows=viewpoint_table_csv(raw,'MTN','MTN.JSE',NOW,file_name='MTN.JSE sample.csv',
      file_modified_at=NOW-timedelta(minutes=1),interval_minutes=5,
      accept_operator_conventions=True)
  parsed=merge_bars(rows)
  self.assertEqual(len(parsed['bars']),1)
  self.assertEqual(parsed['unknown_clock_records'],[])
  row=parsed['bars'][0]
  self.assertEqual(row['fields']['close']['selected']['value'],'230.39')
  self.assertEqual(row['fields']['volume']['selected']['value'],'19944')
  self.assertEqual(row['bar_start'],'2026-11-06T08:00:00+00:00')
  self.assertEqual(row['bar_end'],'2026-11-06T08:05:00+00:00')
  self.assertEqual(row['fields']['close']['selected']['normalization_basis'],
                   'OPERATOR_ACCEPTED_VIEWPOINT_CSV_CONVENTION_V1')
  payload=__import__('json').loads(rows[0]['raw_payload'])
  self.assertEqual(payload['raw_values']['Close'],'23039.00')
  self.assertEqual(payload['raw_values']['Volume'],'19,944')
  self.assertEqual(payload['qualification']['use_for_scoring'],True)
  self.assertEqual(payload['qualification']['price_unit'],'ZAR_CENTS')
  raw_only=dict(rows[0],bar_start=None,bar_end=None,clock_semantics='UNKNOWN',unit='UNVERIFIED',
                fields={field:None for field in ('open','high','low','close','volume')})
  normalized_with_hash=dict(rows[0],source_raw_sha256='a'*64)
  raw_only['source_raw_sha256']='a'*64
  self.assertEqual(merge_bars([raw_only,normalized_with_hash])['unknown_clock_records'],[])
  with self.assertRaises(ValueError):
   viewpoint_table_csv(raw,'MTN','OTHER',NOW,file_name='sample.csv')
  with self.assertRaises(ValueError):
   viewpoint_table_csv(raw.replace(b'.000Z',b'.000'), 'MTN','MTN.JSE',NOW,file_name='sample.csv')
 def test_operator_normalized_csv_is_available_to_research_shadow(self):
  from application.strategy_radar.intraday_evaluation import evaluate_intraday
  now=datetime(2026,11,6,8,1,tzinfo=timezone.utc)
  raw=(b'"Date","Open","High","Low","Close","% Change","% Change vs Average","Volume"\n'
       b'"2026-11-06T07:40:00.000Z","22900","22920","22890","22910","0.01","0.01","1000"\n'
       b'"2026-11-06T07:45:00.000Z","22910","22930","22900","22920","0.01","0.01","1100"\n'
       b'"2026-11-06T07:50:00.000Z","22920","22940","22910","22930","0.01","0.01","1200"\n'
       b'"2026-11-06T07:55:00.000Z","22930","22960","22920","22950","0.02","0.02","1800"\n')
  rows=viewpoint_table_csv(raw,'MTN','MTN.JSE',now,file_name='MTN.JSE sample.csv',
      interval_minutes=5,accept_operator_conventions=True)
  result=evaluate_intraday('intraday_5m_research_v1','MTN',rows,now)
  self.assertEqual(result['evaluation_mode'],'SHADOW')
  self.assertTrue(result['component_plan']['reference_close'])
  self.assertTrue(all(rule['state'] != 'UNKNOWN' for rule in result['rules'] if rule['mandatory']))
  entry=next(rule for rule in result['rules'] if rule['id']=='entry')
  self.assertEqual(entry['provenance'][0]['normalization_basis'],
                   'OPERATOR_ACCEPTED_VIEWPOINT_CSV_CONVENTION_V1')
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

 def test_api_imports_viewpoint_csv_as_hash_bound_normalized_research_bars(self):
  import hashlib
  from io import BytesIO
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp,clock=lambda:NOW)
   app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service)); client=app.test_client()
   raw=(b'"Date","Open","High","Low","Close","% Change","% Change vs Average","Volume"\n'
        b'"2026-11-06T08:05:00.000Z","23042.00","23061.00","23009.00","23049.00","0.04","0.03","20,004"\n'
        b'"2026-11-06T08:00:00.000Z","23032.00","23051.00","22999.00","23039.00","0.03","0.02","19,944"\n')
   data={'instrument':'MTN','symbol':'MTN.JSE','interval_minutes':'5','accept_operator_conventions':'yes',
         'file_modified_at':'2026-11-06T14:59:00+00:00',
         'file':(BytesIO(raw),'MTN.JSE sample.csv')}
   with patch('application.opportunities.zebra_instruments.mappings',return_value={'MTN':'MTN'}), \
        patch.object(service,'prepare_context',return_value={'state':'PREPARED','id':'context-id'}) as prepare:
    response=client.post('/api/v1/strategy-radar/intraday/viewpoint-csv',data=data,content_type='multipart/form-data')
   self.assertEqual(response.status_code,201,response.json)
   self.assertEqual(response.json['prepared_context']['state'],'PREPARED')
   prepare.assert_called_once_with('VIEWPOINT_CSV_IMPORT',imported_instrument='MTN')
   self.assertEqual(response.json['source_raw_sha256'],hashlib.sha256(raw).hexdigest())
   self.assertTrue(response.json['use_for_scoring'])
   self.assertEqual(response.json['clock_semantics'],'START')
   self.assertEqual(response.json['price_unit'],'ZAR_CENTS')
   result=client.get('/api/v1/strategy-radar/intraday/MTN')
   self.assertEqual(result.status_code,200)
   self.assertEqual(len(result.json['bars']),2)
   self.assertEqual(result.json['unknown_clock_records'],[])
   self.assertEqual([x['bar_start'] for x in result.json['bars']],
                    ['2026-11-06T08:00:00+00:00','2026-11-06T08:05:00+00:00'])
   self.assertEqual(result.json['bars'][0]['fields']['close']['selected']['value'],'230.39')
   invalid={'instrument':'MTN','symbol':'MTN.JSE','interval_minutes':'5',
            'file':(BytesIO(raw),'MTN.JSE sample.csv')}
   with patch('application.opportunities.zebra_instruments.mappings',return_value={'MTN':'MTN'}):
    response=client.post('/api/v1/strategy-radar/intraday/viewpoint-csv',data=invalid,content_type='multipart/form-data')
   self.assertEqual(response.status_code,422)

 def test_viewpoint_ohlc_only_csv_import_retains_missing_volume(self):
  from io import BytesIO
  from application.opportunities.prospective_prices import record_capture
  raw=(b'Date,Open,High,Low,Close\n'
       b'2026-11-05T08:00:00.000Z,23032,23051,22999,23039\n')
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp,clock=lambda:NOW)
   app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service))
   client=app.test_client()
   data={'instrument':'MTN','symbol':'MTN.JSE','interval_minutes':'5',
         'accept_operator_conventions':'yes','file':(BytesIO(raw),'MTN.JSE.csv')}
   with patch('application.opportunities.zebra_instruments.mappings',return_value={'MTN':'MTN'}), \
        patch.object(service,'prepare_context',return_value={'state':'PREPARED'}):
    response=client.post('/api/v1/strategy-radar/intraday/viewpoint-csv',data=data,content_type='multipart/form-data')
   self.assertEqual(response.status_code,201,response.json)
   self.assertEqual(response.json['rows_without_volume'],1)
   self.assertIsNone(response.json['volume_unit'])
   record_capture(service.folder.parent, 'MTN', 'OST', {'bars': [
       {'timestamp':'2026-11-04','close':229,'volume':500},
       {'timestamp':'2026-11-05','close':230.39,'volume':1000},
   ]}, NOW.isoformat(), 'a'*64)
   result=client.get('/api/v1/strategy-radar/intraday/MTN').json
   self.assertEqual([row['session'] for row in result['ost_daily']['paired_sessions']], ['2026-11-05'])
   self.assertEqual(result['ost_daily']['latest']['volume_shares'],1000)
   fields=result['bars'][0]['fields']
   self.assertEqual(fields['close']['selected']['value'],'230.39')
   self.assertIsNone(fields['volume']['selected'])

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
