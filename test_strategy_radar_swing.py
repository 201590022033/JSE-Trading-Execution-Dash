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
            fields={k:{'value':v, 'state':'AGREEMENT', 'source':'FIXTURE', 'acquired_at':'2026-11-09T10:00:00+00:00'} for k,v in values.items()}
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
        self.assertEqual(result['strategy_version'],'1.1.2')
        self.assertEqual(result['component_evaluation_version'],'zebra-component-windows-v2')
        self.assertEqual(result['rules'][0]['state'],'PASS')
        self.assertEqual(result['rules'][-1]['state'],'UNKNOWN')
        self.assertTrue(result['research_only'])
        self.assertFalse(result['live_signal'])

    def test_conflict_and_future_receipt_do_not_pass(self):
        for row in self.rows:
            row['fields']['volume']['state']='CONFLICT_NO_CONSENSUS'
            row['fields']['volume']['source_sha256']='a'*64
            row['fields']['volume']['alternatives']=[{'value':999,'source':'OTHER','acquired_at':'2026-11-09T10:00:00+00:00'}]
        self.write()
        result=self.result()
        self.assertTrue(result['data_quality']['provisional'])
        self.assertGreater(result['data_quality']['conflict_count'],0)
        self.assertTrue(any(row['field']=='volume' and row['source']=='FIXTURE' and row['state']=='CONFLICT_NO_CONSENSUS' for row in result['data_quality']['fields']))
        selected=next(row for row in result['data_quality']['fields'] if row['field']=='volume')
        self.assertEqual((selected['value'],selected['source_sha256'],selected['alternatives'][0]['value']),(1000.0,'a'*64,999))
        self.rows[-1]['fields']['close']['acquired_at']='2026-11-10T10:00:00+00:00'
        self.write()
        result=self.result()
        self.assertTrue(result['data_quality']['stale'])
        self.assertEqual(result['session'],'2026-11-05')

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

    def test_stale_and_missing_sessions_do_not_compress_gaps(self):
        self.rows.pop()
        self.write(latest='2026-11-05')
        result=self.result()
        self.assertTrue(result['data_quality']['stale'])
        self.assertEqual(result['rules'][0]['state'],'PASS')
        self.assertEqual(result['evaluated_at'],NOW.isoformat())
        self.assertNotEqual(result['calculation_clock'],result['evaluated_at'])
        self.assertIn('not a point-in-time',result['data_quality']['limitation'])
        self.rows.pop(-3)
        self.write(latest='2026-11-05')
        self.assertEqual(self.result()['state'],'UNKNOWN')

    def test_missing_high_does_not_suppress_close_based_rules(self):
        for row in self.rows:
            row['fields']['high']['state']='MISSING'
        self.write()
        result=self.result()
        self.assertTrue(result['data_quality']['partial'])
        self.assertEqual(result['rules'][0]['state'],'PASS')
        self.assertNotEqual(result['rules'][3]['state'],'UNKNOWN')
        self.assertEqual(result['rules'][1]['state'],'UNKNOWN')

    def test_old_missing_ohlc_does_not_block_recent_rule_windows(self):
        self.rows[0]['fields']['open']['state']='MISSING'
        self.rows[1]['fields']['high']['state']='MISSING'
        self.write()
        result=self.result()
        self.assertTrue(result['data_quality']['partial'])
        self.assertEqual(result['component_evaluation_version'],'zebra-component-windows-v2')
        self.assertEqual(set(result['component_window_rules']),{'breakout20','ema20_reclaim'})
        self.assertNotEqual(result['rules'][1]['state'],'UNKNOWN')
        self.assertNotEqual(result['rules'][2]['state'],'UNKNOWN')

    def test_unreviewed_calendar_keeps_latest_observation_without_inventing_continuity(self):
        result=evaluate_watches(self.service,now=datetime(2027,2,1,tzinfo=timezone.utc))['MTN']
        self.assertEqual(result['data_quality']['state'],'CALENDAR_UNVERIFIED')
        self.assertIsNone(result['data_quality']['stale'])
        self.assertEqual(result['session'],'2026-11-06')
        self.assertEqual(result['source_bars'],1)

    def test_bad_field_clock_does_not_discard_other_fields(self):
        self.rows[-1]['fields']['high']['acquired_at']='not-a-time'
        self.write()
        result=self.result()
        self.assertTrue(result['data_quality']['partial'])
        self.assertEqual(result['session'],'2026-11-06')
        self.assertEqual(result['rules'][0]['state'],'PASS')
        self.assertFalse(any(field['session']=='2026-11-06' and field['field']=='high' for field in result['data_quality']['fields']))

    def test_conflict_alternatives_exclude_future_and_unqualified_receipts(self):
        detail=self.rows[-1]['fields']['volume']
        detail.update(state='CONFLICT_NO_CONSENSUS', alternatives=[
            {'value':1001,'source':'VALID','acquired_at':'2026-11-09T11:00:00+00:00'},
            {'value':1002,'source':'FUTURE','acquired_at':'2026-11-10T11:00:00+00:00'},
            {'value':1003,'source':'NO_CLOCK'},
            {'value':1004,'source':'NAIVE','acquired_at':'2026-11-09T11:00:00'},
            {'value':1005,'source':'BEFORE_CLOSE','acquired_at':'2026-11-06T14:59:59+00:00'},
        ])
        self.write()
        result=self.result()
        selected=next(p for p in result['data_quality']['fields'] if p['session']=='2026-11-06' and p['field']=='volume')
        self.assertEqual([p['source'] for p in selected['alternatives']],['VALID'])
        self.assertEqual(selected['omitted_alternatives'],4)
        self.assertEqual(result['data_quality']['omitted_alternatives'],4)
        self.assertTrue(result['data_quality']['provisional'])

    def test_ambiguous_older_session_is_gap_not_global_block(self):
        duplicated=self.rows[4]
        self.rows.insert(5,duplicated)
        self.write(latest='2026-11-05')
        result=self.result()
        self.assertIn(duplicated['session'],result['data_quality']['ambiguous_sessions'])
        self.assertTrue(result['data_quality']['metadata_session_mismatch'])
        self.assertEqual(result['session'],'2026-11-06')
        self.assertGreaterEqual(result['source_bars'],50)
        self.assertEqual(result['rules'][0]['state'],'PASS')

if __name__ == '__main__': unittest.main()
