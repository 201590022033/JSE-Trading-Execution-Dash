import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from flask import Flask
from application.strategy_radar.api import create_radar_blueprint

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
        vod = retained_validation('VOD', 'ETF_STX40')
        self.assertEqual(vod['closed_trades'], 1)
        self.assertEqual(vod['label'], 'W06 comparison: 1 closed VOD breakout/pullback trade '
                         '(3 original-rule trades), below the 30-trade floor. Not validated.')
        self.assertEqual(retained_validation('MTN', 'ETF_STX40')['closed_trades'], 0)
        self.assertEqual(retained_validation('SASOL', 'ETF_STX40')['label'], 'not yet validated (artifact unavailable)')
        self.assertEqual(retained_validation('VOD', 'ETF_STXRES')['label'], 'not yet validated (artifact unavailable)')
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.json'
            path.write_text('{"content_sha256":"wrong"}')
            self.assertEqual(retained_validation('VOD', 'ETF_STX40', path)['label'], 'not yet validated (artifact unavailable)')
            result = breakout_pullback_display(folder, 'MTN', 'ETF_STX40', FINAL_CLOCK)
            self.assertEqual(result['state'], 'NO_DATA')
            self.assertEqual(result['validation']['state'], 'RETROSPECTIVE_COMPARISON')


    def test_evidence_route_accepts_service_without_folder(self):
        app = Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: object()))
        trace = {'strategy_version': '1.1.2', 'timeframe_minutes': None}
        with patch('application.strategy_radar.swing_radar.evaluate_watches', return_value={'VOD': trace}), \
             patch('application.strategy_radar.shadow_service.retained_comparisons', return_value=[]), \
             patch('application.strategy_radar.shadow_service.retained_fill_backtests', return_value=[]):
            response = app.test_client().get('/api/v1/strategy-radar/evidence/VOD?profile=jse_swing_3_5d&view=summary')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['breakout_pullback']['state'], 'NO_DATA')
        self.assertEqual(response.json['breakout_pullback']['validation']['label'],
                         'not yet validated (artifact unavailable)')

    def test_missing_and_corrupt_artifacts_report_unavailable(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'w06.json'
            with patch('application.strategy_radar.breakout_pullback_display.COMPARISON', path):
                for corrupt in (False, True):
                    with self.subTest(corrupt=corrupt):
                        if corrupt:
                            path.write_text('{invalid json')
                        result = breakout_pullback_display(None, 'VOD', 'ETF_STX40', FINAL_CLOCK)
                        self.assertEqual(result['validation']['label'], 'not yet validated (artifact unavailable)')
