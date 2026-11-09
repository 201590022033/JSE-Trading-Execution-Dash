import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from application.opportunities.zebra_screen_data import merge_captures
from application.strategy_radar.daily import prewarm_daily, refresh_daily


class DailyPrewarmTests(unittest.TestCase):
    def test_partial_mixed_history_and_manual_source_are_independent(self):
        now = datetime(2026, 11, 6, 19, tzinfo=timezone.utc)
        captures = [
            {'instrument': 'SOL', 'provider': 'YAHOO', 'acquired_at': '2026-11-06T18:00:00+00:00',
             'source_sha256': 'a'*64, 'rows': [{'session': '2026-11-05', 'close': 120}]},
            {'instrument': 'SOL', 'provider': 'IRESS', 'acquired_at': '2026-11-06T18:01:00+00:00',
             'source_sha256': 'b'*64, 'rows': [{'session': '2026-11-05', 'volume': 42}]},
        ]
        merged = merge_captures(captures, now=now)
        def loader(**kw):
            self.assertEqual(kw['instruments'], ['SOL', 'BTI'])
            return {'instruments': merged, 'source_diagnostics': {'OST': {'invalid_captures': 1}},
                    'expected_session': '2026-11-05'}
        out = prewarm_daily(['SOL', 'BTI'], now=now, loader=loader)
        sol = out['watches']['SOL']
        self.assertEqual(sol['coverage'], {'open': 0, 'high': 0, 'low': 0, 'close': 1, 'volume': 1})
        self.assertEqual(sol['history']['rows'][0]['fields']['close']['source'], 'YAHOO')
        self.assertEqual(sol['history']['rows'][0]['fields']['volume']['source'], 'IRESS')
        self.assertEqual(sol['sources']['OST']['state'], 'NO_RETAINED_FIELD')
        self.assertEqual(sol['sources']['IRESS']['automatic_feed'], 'UNVERIFIED_MANUAL_CAPTURE')
        self.assertEqual(out['watches']['BTI']['state'], 'NO_RETAINED_HISTORY')
        self.assertTrue(sol['historical_not_quote'])

    def test_provider_failures_are_separate_and_receipted_without_network(self):
        def yahoo(keys, mapping, folder):
            return {'SOL': {'state': 'FAILED', 'error_type': 'TimeoutError'}}
        def sharedata(key, code, folder):
            return {'capture_sha256': 'a'*64, 'acquired_at': '2026-11-06T18:00:00+00:00'}
        with tempfile.TemporaryDirectory() as root, patch('application.opportunities.zebra_instruments.mappings', return_value={'SOL':'SOL'}):
            out = refresh_daily(['SOL'], root=root, yahoo_capture=yahoo, sharedata_capture=sharedata)
            self.assertEqual(out['results']['SOL']['YAHOO']['state'], 'FAILED')
            self.assertEqual(out['results']['SOL']['SHAREDATA']['state'], 'CAPTURED')
            self.assertEqual(out['results']['SOL']['SHAREDATA']['acquired_at'], '2026-11-06T18:00:00+00:00')
            self.assertEqual(out['results']['SOL']['OST']['state'], 'MANUAL_CAPTURE_AUTOMATION_UNVERIFIED')
            with open(out['receipt'], encoding='utf-8') as f:
                self.assertIn('strategy-radar-daily-refresh-v1', f.read())

    def test_refresh_is_bounded_and_empty_prewarm_does_not_load(self):
        with self.assertRaises(ValueError):
            refresh_daily(['AA','AB','AC','AD','AE','AF'])
        out = prewarm_daily([], loader=lambda **kw: self.fail('must not read'))
        self.assertEqual(out['state'], 'EMPTY')


if __name__ == '__main__':
    unittest.main()
