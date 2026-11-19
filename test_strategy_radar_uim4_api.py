import unittest
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint


class DailyEvidenceApiTests(unittest.TestCase):
    def test_daily_evidence_envelope_rebuilds_exact_profile(self):
        app = Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: object()))
        trace = {'instrument': 'ABC', 'strategy_id': 'jse_swing_3_5d',
                 'strategy_version': '1.1.0', 'timeframe_minutes': None}
        with patch('application.strategy_radar.swing_radar.evaluate_watches', return_value={'ABC': trace}), \
             patch('application.strategy_radar.shadow_service.retained_comparisons', return_value=[]), \
             patch('application.strategy_radar.shadow_service.retained_fill_backtests', return_value=[]):
            client = app.test_client()
            response = client.get('/api/v1/strategy-radar/evidence/ABC?profile=jse_swing_3_5d')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['strategy_version'], '1.1.0')
            self.assertIsNone(response.json['timeframe_minutes'])
            self.assertEqual(response.json['product'], 'CASH_SHARE')
            self.assertEqual(client.get('/api/v1/strategy-radar/evidence/OTHER?profile=jse_swing_3_5d').status_code, 404)

    def test_saved_review_matches_exact_version_and_benchmark(self):
        from application.strategy_radar.exact_daily_review import retained_review

        key = ('VOD', 'jse_swing_3_5d', '1.1.2', None)
        saved = retained_review(*key, 'ETF_STX40')
        self.assertEqual(saved['state'], 'INSUFFICIENT_POINT_IN_TIME_INPUT')
        self.assertEqual(saved['retrospective_comparison']['state'], 'DESCRIPTIVE_REPLAY')
        self.assertIsNone(retained_review(*key, 'ETF_STXRES'))
        self.assertIsNone(retained_review('VOD', key[1], '1.1.0', None, 'ETF_STX40'))

    def test_disputed_zebra_selection_keeps_original_receipt_clock(self):
        from datetime import datetime
        from application.strategy_radar.exact_daily_review import _qualified

        selected = {'state': 'CONFLICT_NO_CONSENSUS', 'source': 'SHAREDATA', 'source_sha256': 'a'*64,
                    'value': 100, 'acquired_at': '2026-11-19T05:00:00+00:00'}
        clock = datetime.fromisoformat
        close = clock('2026-11-18T15:00:00+00:00')
        late = clock('2026-11-19T05:00:00+00:00')
        self.assertEqual(_qualified(selected, close, late, allow_zero=True), ('ZEBRA_SELECTED_DISPUTED', late))
        self.assertEqual(_qualified(selected, close, close, allow_zero=True), ('UNQUALIFIED_RECEIPT', None))
