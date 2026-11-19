import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from application.strategy_radar.roster import enqueue, run_lane, status


class LaneTests(unittest.TestCase):
    def test_local_api_job_status_through_isolated_worker(self):
        from flask import Flask
        from application.strategy_radar.api import create_radar_blueprint
        with tempfile.TemporaryDirectory() as folder:
            service = SimpleNamespace(folder=Path(folder))
            app = Flask(__name__)
            app.register_blueprint(create_radar_blueprint(lambda: service))
            client = app.test_client()
            with patch('application.strategy_radar.roster.start_lane') as start:
                response = client.post('/api/v1/strategy-radar/work-roster', json={
                    'lane': 'backtester', 'instrument': 'MTN', 'request_id': 'fixture'})
            self.assertEqual(response.status_code, 202)
            start.assert_called_once_with(service, 'backtester')
            run_lane(service, 'backtester', invoke=lambda *a, **k: SimpleNamespace(returncode=0))
            job = client.get('/api/v1/strategy-radar/work-roster').get_json()['jobs'][0]
            self.assertEqual((job['lane'], job['instrument'], job['state']),
                             ('backtester', 'MTN', 'COMPLETED'))

    def test_status_identifies_lanes_and_retry_without_exposing_results(self):
        with tempfile.TemporaryDirectory() as folder:
            service = SimpleNamespace(folder=Path(folder))
            enqueue(service, 'backtester', instrument='MTN', request_id='visibility')
            run_lane(service, 'backtester', invoke=lambda *a, **k: SimpleNamespace(returncode=1))
            enqueue(service, 'sens')
            run_lane(service, 'sens', invoke=lambda *a, **k: SimpleNamespace(returncode=1))
            jobs = {job['lane']: job for job in status(service)['jobs']}
            self.assertEqual(jobs['backtester']['instrument'], 'MTN')
            self.assertFalse(jobs['backtester']['retry_available'])
            self.assertTrue(jobs['sens']['retry_available'])
            self.assertEqual(jobs['sens']['max_attempts'], 3)
            self.assertEqual(jobs['sens']['returncode'], 1)
            self.assertNotIn('result', jobs['sens'])

    def test_explicit_backtester_is_not_repeated_and_requests_no_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            service=SimpleNamespace(folder=Path(folder)); calls=[]
            enqueue(service,'backtester',instrument='MTN',request_id='owner-request')
            def invoke(command,**kwargs):
                calls.append(command)
                return SimpleNamespace(returncode=0)
            self.assertEqual(run_lane(service,'backtester',invoke=invoke)['state'],'COMPLETED')
            self.assertEqual(run_lane(service,'backtester',invoke=invoke)['state'],'IDLE')
            self.assertNotIn('--cloud',calls[0])
            self.assertEqual(calls[0][-2:],['--cycles','1'])

    def test_sens_receipt_does_not_claim_zero_model_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            service=SimpleNamespace(folder=Path(folder))
            enqueue(service,'sens')
            result=run_lane(service,'sens',invoke=lambda *a,**k:SimpleNamespace(returncode=0))
            self.assertIsNone(result['model_calls_requested'])
            self.assertEqual(result['model_call_accounting'],'SEE_MACRO_EXPECTATION_RECEIPTS')

    def test_sens_uses_tick_and_failed_backtest_is_not_auto_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            service=SimpleNamespace(folder=Path(folder)); calls=[]
            def invoke(command,**kwargs):
                calls.append(command); return SimpleNamespace(returncode=1)
            enqueue(service,'sens')
            self.assertEqual(run_lane(service,'sens',invoke=invoke)['state'],'FAILED')
            self.assertEqual(calls[0][-1],'tick')
            self.assertEqual(Path(calls[0][1]).name,'sens_runtime_bridge.py')
            enqueue(service,'backtester',instrument='MTN',request_id='failed')
            self.assertEqual(run_lane(service,'backtester',invoke=invoke)['state'],'FAILED')
            self.assertEqual(run_lane(service,'backtester',invoke=invoke)['state'],'IDLE')
