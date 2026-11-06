import tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.trade_tape import capture

class TapeTests(unittest.TestCase):
    def test_observed_prints_preserve_multiplicity_and_units(self):
        rows=[{'traded_at':'2026-11-06T10:36:00+02:00','quantity':2,'price_cents':23100}]*2
        with tempfile.TemporaryDirectory() as d:
            _,p=capture('ABSPJ',rows,source='user-supplied OST table',captured_at='2026-11-06T11:00:00+02:00',root=d)
        self.assertEqual(p['summary']['shares'],4);self.assertEqual(p['summary']['notional_zar'],'924')
        self.assertEqual(len(p['rows']),2);self.assertIn('NO_TRADE_IDS',p['limitations'])

    def test_future_and_naive_times_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):capture('X',[{'traded_at':'2026-11-07T00:00:00+02:00','quantity':1,'price_cents':1}],source='x',captured_at='2026-11-06T11:00:00+02:00',root=d)

    def test_expired_ost_research_replay_uses_zebra_not_broker_upload(self):
        from scripts.collect_swing_data import refresh_zebra_lab_replay
        with patch('subprocess.run',return_value=SimpleNamespace(stdout='{"run_id":"x"}')) as run:
            self.assertEqual(refresh_zebra_lab_replay()['run_id'],'x')
        command=run.call_args.args[0]
        self.assertIn('SASOL',command);self.assertIn('BTI',command)
        self.assertFalse(any('upload' in x for x in command))

    def test_tape_endpoint_lists_retained_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'lab').mkdir()
            capture('ABSPJ',[{'traded_at':'2026-11-06T10:36:00+02:00','quantity':2,'price_cents':23100}],
                    source='user supplied',captured_at='2026-11-06T11:00:00+02:00',root=root/'trade-tape')
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root))
            response=app.test_client().get('/api/v1/backtest-lab/trade-tape')
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertEqual(response.json['snapshots'][0]['summary']['shares'],2)
            self.assertFalse(response.json['live_execution'])
