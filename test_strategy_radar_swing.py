import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint
from application.strategy_radar.swing_radar import evaluate_watches
from application.opportunities.session_freshness import HOLIDAYS_2026

NOW = datetime(2026, 11, 9, 13, tzinfo=timezone.utc)

class SwingRadarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        (self.folder / 'daily-cache').mkdir()
        self.service = SimpleNamespace(folder=self.folder, store=SimpleNamespace(list_watches=lambda: [
            {'instrument':'MTN', 'benchmark':'ETF_STX40'}]))
        days = []
        day = datetime(2026, 11, 6, tzinfo=timezone.utc)
        while len(days) < 70:
            if day.weekday() < 5 and day.date().isoformat() not in HOLIDAYS_2026:
                days.append(day.date().isoformat())
            day -= timedelta(days=1)
        self.rows=[]
        for index, session in enumerate(reversed(days)):
            close=100 + index * 0.2
            values={'open':close, 'high':close+1, 'low':close-1, 'close':close, 'volume':1000}
            fields={k:{'value':v, 'state':'AGREEMENT', 'acquired_at':'2026-11-09T10:00:00+00:00'} for k,v in values.items()}
            self.rows.append({'session':session, 'fields':fields})
        self.write()

    def write(self, latest='2026-11-06'):
        data={'daily':{'latest_session':latest, 'history':{'rows':self.rows}}}
        (self.folder/'daily-cache'/'MTN.json').write_text(json.dumps(data), encoding='utf-8')

    def result(self):
        return evaluate_watches(self.service, now=NOW)['MTN']

    def test_real_daily_rules_work_without_intraday(self):
        result=self.result()
        self.assertEqual(result['session'],'2026-11-06')
        self.assertEqual(result['rules'][0]['state'],'PASS')
        self.assertEqual(result['rules'][-1]['state'],'UNKNOWN')
        self.assertTrue(result['research_only'])
        self.assertFalse(result['live_signal'])

    def test_conflict_and_future_receipt_do_not_pass(self):
        for row in self.rows:
            row['fields']['volume']['state']='CONFLICT_NO_CONSENSUS'
        self.write()
        self.assertEqual(self.result()['rules'][4]['state'],'UNKNOWN')
        self.rows[-1]['fields']['close']['acquired_at']='2026-11-10T10:00:00+00:00'
        self.write()
        self.assertEqual(self.result()['state'],'UNKNOWN')

    def test_endpoint_is_local_and_returns_results(self):
        app=Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: self.service))
        client=app.test_client()
        with patch('application.strategy_radar.swing_radar.evaluate_watches', return_value={'MTN': {'passed': 2}}):
            response=client.get('/api/v1/strategy-radar/swing')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['evaluations']['MTN']['passed'], 2)
            self.assertFalse(response.json['live_execution'])
            self.assertEqual(client.get('/api/v1/strategy-radar/swing', environ_base={'REMOTE_ADDR':'192.0.2.1'}).status_code, 403)

    def test_stale_and_missing_sessions_fail_closed(self):
        self.write(latest='2026-11-05')
        self.assertEqual(self.result()['state'],'UNKNOWN')
        self.rows.pop(-3)
        self.write()
        self.assertEqual(self.result()['state'],'UNKNOWN')

if __name__ == '__main__': unittest.main()
