import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from scripts.zebra_handover import handover
from scripts.collect_swing_data import refresh_zebra


def panel():
    row = {'session': '2020-01-03', 'capabilities': {'close': True}, 'cells': {'close': {
        'value': '12.5', 'source': 'ost', 'raw_hash': 'raw', 'row_hash': 'row',
        'available_at': '2020-01-04T00:00:00Z', 'original_acquired_at': '2026-10-21T00:00:00Z'}}}
    body = {'schema': 'research-feature-panel/1', 'rows': [row],
            'availability': 'conditional_reconstructed', 'summary': {'observations': 1}}
    raw = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True).encode()
    return {**body, 'panel_id': 'sha256:'+hashlib.sha256(raw).hexdigest()}


class ZebraHandoverTests(unittest.TestCase):
    def test_old_close_retained_and_source_lineage_survives(self):
        result = handover(panel())
        self.assertEqual(result['rows'][0]['session'], '2020-01-03')
        self.assertEqual(result['rows'][0]['raw_hash'], 'raw')
        self.assertEqual(result['availability'], 'conditional_reconstructed')
        damaged = panel(); damaged['rows'][0]['cells']['close']['value'] = '99'
        with self.assertRaises(ValueError):
            handover(damaged)

    def test_extension_appends_newer_ire_ss_without_rewriting_old_close(self):
        extension = {'provenance': {'provider': 'IRESS', 'origin_symbol': 'SOL.JSE',
                     'source_sha256': 'a'*64, 'acquired_at': '2020-01-07T08:00:00+00:00'},
                     'bars': [{'timestamp': '2020-01-03', 'close': 88},
                              {'timestamp': '2020-01-06', 'close': 14.2}]}
        result = handover(panel(), extension)
        self.assertEqual(result['extension_rows'], 1)
        self.assertEqual([r['close'] for r in result['rows']], ['12.5', '14.2'])
        self.assertEqual(result['rows'][-1]['raw_hash'], 'sha256:'+'a'*64)
        self.assertEqual(result['rows'][-1]['original_acquired_at'], extension['provenance']['acquired_at'])

    def test_read_api_pages_and_rejects_changed_handover(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'zebra-handover.json')
            path.write_text(json.dumps(handover(panel())), encoding='utf-8')
            app = Flask(__name__); app.register_blueprint(create_backtest_lab_blueprint(folder))
            client = app.test_client()
            summary = client.get('/api/v1/backtest-lab/zebra-history')
            self.assertEqual(summary.status_code, 200)
            self.assertEqual(summary.json['observations'], 1)
            page = client.get('/api/v1/backtest-lab/zebra-history/observations?limit=1')
            self.assertEqual(page.json['rows'][0]['close'], '12.5')
            self.assertEqual(client.get('/api/v1/backtest-lab/zebra-history/observations?limit=1001').status_code, 400)
            changed = json.loads(path.read_text()); changed['rows'][0]['close'] = '999'
            path.write_text(json.dumps(changed), encoding='utf-8')
            self.assertEqual(client.get('/api/v1/backtest-lab/zebra-history').status_code, 503)

    def test_unavailable_extension_does_not_erase_prior_handover(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, 'panel.json'); source.write_text(json.dumps(panel()), encoding='utf-8')
            target = Path(folder, 'handover.json'); target.write_text('retained', encoding='utf-8')
            result = refresh_zebra(source, target, Path(folder, 'missing-dataset.json'))
            self.assertEqual(result['state'], 'EXTENSION_UNAVAILABLE_PRIOR_HANDOVER_RETAINED')
            self.assertEqual(target.read_text(encoding='utf-8'), 'retained')


if __name__ == '__main__':
    unittest.main()
