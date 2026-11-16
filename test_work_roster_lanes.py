import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from application.strategy_radar.roster import enqueue, run_lane


class LaneTests(unittest.TestCase):
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
