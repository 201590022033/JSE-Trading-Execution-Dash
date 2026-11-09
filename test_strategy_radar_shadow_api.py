import tempfile, unittest
from pathlib import Path
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint
from application.strategy_radar.service import RadarService
from application.strategy_radar.shadow_service import evaluate_watch,replay_watch
from application.strategy_radar.intraday_store import IntradayCache
from test_strategy_radar_integration import NOW,prewarm,refresh,snapshot
from test_strategy_radar_intraday_store import bar

class ShadowApiTests(unittest.TestCase):
 def test_retained_replay_and_read_only_evaluation(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp,prewarm=prewarm,refresh=refresh,clock=lambda:NOW)
   service.reconcile(snapshot('SOL'),start_worker=False)
   cache=IntradayCache(service.folder/'intraday.sqlite3')
   unknown=bar(clock_semantics='UNKNOWN',bar_start=None,bar_end=None)
   cache.put(unknown,evidence=True)
   evaluated=evaluate_watch(service,'SOL','intraday_5m_research_v1',now=NOW)
   self.assertEqual(evaluated['state'],'UNKNOWN')
   self.assertEqual(evaluated['unknown_clock_records'],1)
   report=replay_watch(service,'SOL','intraday_5m_research_v1',round_trip_cost_bps='10',as_of=NOW)
   self.assertEqual(report['candidate']['sample_count'],0)
   self.assertEqual(report['baseline']['sample_count'],0)
   self.assertEqual(report['unknown_clock_record_indices'],[0])
   path=service.folder/'shadow-replays'/(report['report_sha256']+'.json')
   self.assertTrue(path.exists())
   self.assertEqual(replay_watch(service,'SOL','intraday_5m_research_v1',round_trip_cost_bps='10',as_of=NOW)['report_sha256'],report['report_sha256'])
   app=Flask(__name__);app.register_blueprint(create_radar_blueprint(lambda:service));client=app.test_client()
   self.assertEqual(client.get('/api/v1/strategy-radar/shadow/SOL').status_code,200)
   self.assertEqual(client.get('/api/v1/strategy-radar/shadow/NO_SUCH').status_code,404)
   body={'instrument':'SOL','profile':'intraday_5m_research_v1','round_trip_cost_bps':'10'}
   self.assertEqual(client.post('/api/v1/strategy-radar/shadow/replay',json=body,headers={'Origin':'https://other.example'}).status_code,403)
   self.assertEqual(client.post('/api/v1/strategy-radar/shadow/replay',json=body).status_code,200)
 def test_five_minute_sources_derive_thirty_with_lineage(self):
  from datetime import datetime, timezone
  with tempfile.TemporaryDirectory() as tmp:
   service=RadarService(tmp,prewarm=prewarm,refresh=refresh,clock=lambda:NOW)
   service.reconcile(snapshot('SOL'),start_worker=False)
   cache=IntradayCache(service.folder/'intraday.sqlite3')
   for i in range(24): cache.put(bar(i,availability='DELAYED'))
   at=datetime(2026,11,6,9,1,tzinfo=timezone.utc)
   result=evaluate_watch(service,'SOL','intraday_30m_research_v1',now=at)
   self.assertEqual(result['derived_30m_records'],4)
   self.assertNotEqual(result['rules'][0]['state'],'UNKNOWN')
   evidence=result['rules'][0]['provenance'][0]
   self.assertEqual(evidence['source_timestamp_basis'],'DERIVED_INTERVAL_END_NOT_PROVIDER_CLOCK')
   self.assertEqual(len(evidence['derived_inputs']),6)


if __name__=='__main__':unittest.main()
