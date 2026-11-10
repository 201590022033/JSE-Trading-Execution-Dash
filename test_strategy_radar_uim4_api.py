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
