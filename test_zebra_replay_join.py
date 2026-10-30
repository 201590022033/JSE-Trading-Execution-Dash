from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
import json
import hashlib
from pathlib import Path
import tempfile
from scripts.backtest_lab_run import demo, append_public_bars
from application.backtest_lab.strategies import evaluate
from application.backtest_lab.observed_history import from_chart, research_intake_history
from application.opportunities.session_freshness import next_session


class ZebraReplayJoinTests(unittest.TestCase):
    def history(self, rows, *, mismatch=False, valid=True):
        data = [{'session':r['timestamp'], 'close':r['close'], 'open':r['open'], 'high':r['high'],
                 'low':r['low'], 'volume':r['volume'], 'ohlc_valid':True} for r in rows[-25:]]
        if mismatch: data[0]['close'] += 1
        last = next_session(rows[-1]['timestamp'])
        data.append({'session':last, 'close':100, 'open':100, 'high':101,
                     'low':99, 'volume':1000, 'ohlc_valid':valid})
        return {'rows':data, 'source_sha256':'a'*64, 'acquired_at':'2026-10-30T00:00:00+00:00'}

    def test_source_switch_requires_consistent_volume_window(self):
        charts, manifests = demo(); original = charts['SOL']
        real = from_chart('SOL', {'bars':original, 'provenance':{'provider':'IRESS', 'source_sha256':'b'*64, 'acquired_at':'2026-10-30T00:00:00+00:00'}})
        # Limit the replay to one instrument to keep this test focused.
        with patch('application.opportunities.radar_price_capture.latest_close_history', return_value=self.history(original)):
            charts, out = append_public_bars(charts, [real], '.')
        self.assertEqual(len(charts['SOL']), len(original)+1)
        self.assertEqual(out[0].provider, 'IRESS+YAHOO')
        trace, _ = evaluate('vcp', 'SOL', len(charts['SOL'])-1, charts)
        self.assertFalse(next(c for c in trace if c['c']=='Source continuity')['ok'])

    def test_mismatch_or_invalid_bar_is_not_spliced(self):
        for case in ('mismatch', 'invalid'):
            charts, manifests = demo(); rows = charts['SOL']
            data = self.history(rows, mismatch=case=='mismatch', valid=case!='invalid')
            with patch('application.opportunities.radar_price_capture.latest_close_history', return_value=data):
                charts, out = append_public_bars(charts, [manifests[0]], '.')
            self.assertEqual(len(charts['SOL']), len(rows))
            self.assertEqual(out[0].provider, 'SYNTHETIC_FIXTURE')

    def test_intake_requires_hash_bound_exact_issuer_and_raw_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'raw').mkdir(); (root/'normalized').mkdir()
            source = b'original source'; digest=hashlib.sha256(source).hexdigest()
            raw_path = root/'raw'/(digest+'.bin'); raw_path.write_bytes(source)
            body={'instrument_id':'BVT','source_id':'iress','symbol':'BVT.JSE',
                  'product':'cash_equity','currency':'ZAR','raw_hash':'sha256:'+digest,
                  'acquired_at':'2026-10-28T07:32:34+00:00','bars':[]}
            raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
            (root/'normalized'/(hashlib.sha256(raw).hexdigest()+'.json')).write_bytes(raw)
            self.assertEqual(research_intake_history('BVT', root)['raw_hash'], 'sha256:'+digest)
            self.assertIsNone(research_intake_history('BTI', root))
            raw_path.write_bytes(b'changed')
            self.assertIsNone(research_intake_history('BVT', root))
