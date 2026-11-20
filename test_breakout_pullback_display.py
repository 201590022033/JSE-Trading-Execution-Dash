import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from application.strategy_radar.breakout_pullback_display import breakout_pullback_display, retained_validation
from test_breakout_pullback import FINAL_CLOCK, case

class BreakoutPullbackDisplayTests(unittest.TestCase):
    def test_retained_gap_tolerated_state_remains_in_research_lane(self):
        share, benchmark = case()
        del share[60:62]
        with TemporaryDirectory() as folder:
            cache = Path(folder) / 'daily-cache'
            cache.mkdir()
            for key, rows in (('VOD', share), ('ETF_STX40', benchmark)):
                (cache / (key + '.json')).write_text(json.dumps({'daily': {'history': {'rows': rows}}}))
            result = breakout_pullback_display(folder, 'VOD', 'ETF_STX40', FINAL_CLOCK)
        self.assertEqual(result['state'], 'TRIGGERED')
        self.assertEqual(result['data_quality'], 'GAP_TOLERATED')
        self.assertEqual(result['components_total'], 5)
        self.assertEqual(result['rules']['rsi']['state'], 'PASS')
        self.assertTrue(result['stale'])
        self.assertFalse(result['live_execution'])

    def test_validation_is_exact_and_reads_closed_trade_count(self):
        self.assertEqual(retained_validation('VOD', 'ETF_STX40')['closed_trades'], 1)
        self.assertEqual(retained_validation('MTN', 'ETF_STX40')['closed_trades'], 0)
        self.assertEqual(retained_validation('SASOL', 'ETF_STX40')['label'], 'not yet validated')
        self.assertEqual(retained_validation('VOD', 'ETF_STXRES')['label'], 'not yet validated')
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.json'
            path.write_text('{"content_sha256":"wrong"}')
            self.assertEqual(retained_validation('VOD', 'ETF_STX40', path)['label'], 'not yet validated')
            result = breakout_pullback_display(folder, 'MTN', 'ETF_STX40', FINAL_CLOCK)
            self.assertEqual(result['state'], 'NO_DATA')
            self.assertEqual(result['validation']['state'], 'RETROSPECTIVE_COMPARISON')
