import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from datetime import timedelta

from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from scripts.backtest_lab_real_funnel import measure
from scripts.backtest_lab_run import demo
from application.backtest_lab.observed_history import from_chart


class HistoricalFunnelTests(unittest.TestCase):
    def test_uses_retained_chart_and_counts_cumulative_rules(self):
        rows = [{'timestamp': '2025-01-01'}] * 53
        provenance = {'provider': 'IRESS'}
        dataset = {'observed_at': '2026-10-29T05:30:03+00:00',
                   'charts': {'ETF_STX40': {'bars': rows, 'provenance': {'provider': 'OST'}}}}
        enriched = {**dataset, 'research_charts': {'SASOL': {'bars': rows, 'provenance': provenance}}}
        def rule(_strategy, _instrument, index, _charts):
            return ([{'c': str(j), 'v': 1, 'ok': not (index == 51 and j == 1)} for j in range(6)], 1)
        with patch('scripts.backtest_lab_real_funnel.attach_iress_research', return_value=enriched) as attach, \
             patch('scripts.backtest_lab_real_funnel.verify_ost_benchmark'), \
             patch('scripts.backtest_lab_real_funnel.snapshot', return_value={'state': 'AVAILABLE'}), \
             patch('scripts.backtest_lab_real_funnel.evaluate', side_effect=rule):
            result = measure(dataset, Path('.'))
        self.assertEqual(result['years']['ALL'], {'checked': 3, 'passed': [3, 2, 2, 2, 2, 2], 'signals': 2, 'benchmark_missing': 0})
        self.assertEqual(result['share_source'], provenance)
        self.assertFalse(result['live_execution'])
        self.assertEqual(attach.call_args.args[1].isoformat(), dataset['observed_at'])

    def test_endpoint_absent_and_available_no_store(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Flask(__name__)
            app.register_blueprint(create_backtest_lab_blueprint(directory))
            client = app.test_client()
            response = client.get('/api/v1/backtest-lab/swing-funnel')
            self.assertEqual(response.status_code, 503)
            self.assertFalse(response.json['live_execution'])
            Path(directory, 'lab-swing-funnel.json').write_text(json.dumps({
                'schema': 'backtest-lab-real-funnel-v1', 'live_execution': False}), encoding='utf-8')
            response = client.get('/api/v1/backtest-lab/swing-funnel')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_observed_history_rejects_future_and_invalid_rows(self):
        charts, _ = demo()
        chart = {'bars': charts['SOL'], 'provenance': {'provider': 'IRESS',
                 'source_sha256': 'a'*64, 'acquired_at': '2026-10-29T00:00:00+00:00'}}
        history = from_chart('SASOL', chart)
        self.assertEqual(history.calendar_basis, 'OBSERVED_PROVIDER_SESSIONS_NOT_VERIFIED')
        self.assertIn('UNVERIFIED', history.action_basis)
        latest = history.bars[-1].available_at
        with self.assertRaises(ValueError):
            history.admit(history.sessions[0].key, history.sessions[-1].key, latest - timedelta(seconds=1))
        damaged = replace(history, bars=history.bars[:-1] + (replace(history.bars[-1], high=0),))
        with self.assertRaises(ValueError):
            damaged.admit(damaged.sessions[0].key, damaged.sessions[-1].key, latest)


if __name__ == '__main__':
    unittest.main()
