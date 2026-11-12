import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask
from application.strategy_radar.service import RadarService
from application.strategy_radar.api import create_radar_blueprint

NOW = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)

def prewarm(keys, **kwargs):
    return {'as_of': NOW.isoformat(), 'watches': {key: {'instrument': key, 'state': 'AVAILABLE', 'sessions': 1,
        'coverage': {'close': 1, 'volume': 0}, 'history': {'rows': [{'close': 10, 'volume': None}]},
        'sources': {'OST': {'state': 'NO_RETAINED_FIELD'}, 'YAHOO': {'state': 'RETAINED_HISTORICAL_FIELDS'}}} for key in keys}}

def refresh(keys, **kwargs):
    return {'started_at': NOW.isoformat(), 'finished_at': NOW.isoformat(), 'receipt': 'receipt.json',
            'results': {key: {'YAHOO': {'state': 'CAPTURED'}, 'SHAREDATA': {'state': 'FAILED'},
                               'OST': {'state': 'MANUAL_CAPTURE_AUTOMATION_UNVERIFIED'}} for key in keys}}

def snapshot(*keys):
    return {'schema':'zebra-research-screen-v1', 'generated_at':NOW.isoformat(), 'opportunities':[{'research_key': key, 'sector': 'Energy'} for key in keys]}

class RadarIntegrationTests(unittest.TestCase):
    def test_reconcile_cache_queue_restart_and_read_is_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp, prewarm=prewarm, refresh=refresh, clock=lambda:NOW)
            service.reconcile(snapshot('SASOL', 'BTI'), start_worker=False)
            self.assertTrue((Path(tmp)/'runtime/local-swing-data/strategy-radar/daily-cache/SASOL.json').exists())
            before = service.status()
            self.assertEqual(before['watches'][0]['refresh']['state'], 'QUEUED')
            self.assertEqual(before['watches'][0]['daily']['coverage']['volume'], 0)
            service._drain()
            status = service.status(include_history=True)
            watch = next(w for w in status['watches'] if w['instrument'] == 'SASOL')
            self.assertEqual(watch['refresh']['receipt']['sources']['SHAREDATA']['state'], 'FAILED')
            self.assertEqual(watch['daily']['history']['rows'][0]['close'], 10)
            self.assertEqual(watch['benchmark'], 'ETF_STXRES')
            events = len(service.store.history())
            service.reconcile(snapshot('SASOL', 'BTI'), start_worker=False)
            self.assertEqual(len(service.store.history()), events)
            stale = snapshot('BTI')
            stale['generated_at'] = '2026-11-05T10:00:00+00:00'
            with self.assertRaises(ValueError): service.reconcile(stale, start_worker=False)
            self.assertEqual(len(service.store.history()), events)
            resumed = RadarService(tmp, prewarm=prewarm, refresh=refresh, clock=lambda:NOW)
            self.assertEqual(len(resumed.status()['watches']), 2)
            self.assertEqual(resumed.status()['watches'][0]['refresh']['state'], 'ATTEMPTED')

    def test_local_api_does_not_run_refresh_and_rejects_cross_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            def forbidden(*args, **kwargs): raise AssertionError('read must not refresh')
            service = RadarService(tmp, prewarm=prewarm, refresh=forbidden, clock=lambda:NOW)
            service.reconcile(snapshot('SASOL'), start_worker=False)
            app = Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda:service))
            client = app.test_client()
            self.assertEqual(client.get('/api/v1/strategy-radar/watches').status_code, 200)
            self.assertEqual(client.get('/api/v1/strategy-radar/watches/SASOL/history').json['watch']['daily']['history']['rows'][0]['close'], 10)
            path = '/api/v1/strategy-radar/watches/SASOL/pin'
            self.assertEqual(client.post(path, json={'pinned':True}, headers={'Origin':'https://elsewhere.example'}).status_code, 403)
            self.assertEqual(client.post(path, json={'pinned':True}).status_code, 200)
            self.assertTrue(service.store.get('SASOL')['pinned'])
            service.store.reconcile([{'instrument':'BTI'}],NOW.replace(minute=1))
            blocked = client.post('/api/v1/strategy-radar/watches/BTI/pin',json={'pinned':True})
            self.assertEqual(blocked.status_code,422)
            self.assertIn('SASOL is already pinned',blocked.json['error'])
            self.assertTrue(service.store.get('SASOL')['pinned'])
            self.assertFalse(service.store.get('BTI')['pinned'])
            self.assertEqual(client.post(path,json={'pinned':False}).status_code,200)
            self.assertEqual(client.post('/api/v1/strategy-radar/watches/BTI/pin',json={'pinned':True}).status_code,200)

if __name__ == '__main__': unittest.main()
