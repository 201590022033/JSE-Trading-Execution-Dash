import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from application.backtest_lab.observed_history import from_chart
from application.opportunities.zebra_public_handover import save
from scripts.backtest_lab_run import apply_consensus_windows, append_public_bars, demo
from application.opportunities.session_freshness import next_session


class ZebraDisagreementResearchTests(unittest.TestCase):
    def test_research_handover_preserves_mismatch_and_uses_observed_new_bar(self):
        charts, manifests = demo()
        rows = charts['SOL']
        manifest = from_chart('SOL', {'bars': rows, 'provenance': {'provider': 'IRESS',
            'source_sha256': 'b'*64, 'acquired_at': '2026-10-30T00:00:00+00:00'}})
        data = [{'session':r['timestamp'], 'close':r['close'], 'open':r['open'], 'high':r['high'],
                 'low':r['low'], 'volume':r['volume'], 'ohlc_valid':True} for r in rows[-25:]]
        data[0]['close'] += 1
        day = next_session(rows[-1]['timestamp'])
        data.append({'session':day, 'close':100, 'open':100, 'high':101, 'low':99, 'volume':1000, 'ohlc_valid':True})
        capture = {'rows':data, 'source_sha256':'a'*64, 'acquired_at':'2026-10-30T00:00:00+00:00'}
        with patch('application.opportunities.radar_price_capture.latest_close_history', return_value=capture):
            charts, out = append_public_bars(charts, [manifest], '.', allow_disagreements=True)
        self.assertEqual(charts['SOL'][-1]['timestamp'], day)
        self.assertEqual(out[0].supplemental_sources[-1]['recent_mismatches'], 1)

    def test_disagreement_remains_in_research_window_and_is_reported(self):
        charts, _ = demo()
        rows = charts['SOL']
        manifest = from_chart('SOL', {'bars': rows, 'provenance': {'provider': 'IRESS',
            'source_sha256': 'b'*64, 'acquired_at': '2026-10-30T00:00:00+00:00'}})
        day = rows[75]['timestamp']
        with tempfile.TemporaryDirectory() as folder:
            save(Path(folder)/'zebra-consensus-SOL.json', {'schema':'zebra-close-consensus-v1',
                'instrument':'SOL', 'checked_at':'2026-10-30T00:00:00+00:00',
                'rows':[{'session':day,'state':'CONFLICT_AWAITING_THREE','accepted_close':None}]})
            with patch('application.opportunities.session_freshness.next_session', return_value=None):
                charts, manifests, info = apply_consensus_windows(charts, [manifest], folder, allow_disagreements=True)
        self.assertEqual(len(charts['SOL']), len(rows))
        self.assertEqual(info['SOL']['conflicting_sessions'], 1)
        self.assertEqual(info['SOL']['differences'][0]['session'], day)
        self.assertEqual(info['SOL']['excluded_conflicting_sessions'], 0)
        self.assertEqual(len(manifests), 1)


if __name__ == '__main__': unittest.main()
