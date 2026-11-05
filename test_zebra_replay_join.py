from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
import json
import hashlib
from pathlib import Path
import tempfile
from scripts.backtest_lab_run import demo, append_public_bars, append_sharedata_bars, add_sharedata_histories, apply_consensus_windows
from application.backtest_lab.strategies import evaluate
from application.backtest_lab.observed_history import from_chart, research_intake_history
from application.opportunities.session_freshness import next_session


class ZebraReplayJoinTests(unittest.TestCase):
    def test_unresolved_conflict_splits_replay_without_bridging(self):
        from application.opportunities.zebra_public_handover import save
        charts, _ = demo(); rows=charts['SOL']
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'IRESS','source_sha256':'b'*64,'acquired_at':'2026-10-30T00:00:00+00:00'}})
        contested=rows[75]['timestamp']
        with tempfile.TemporaryDirectory() as directory:
            save(Path(directory)/'zebra-consensus-SOL.json', {'schema':'zebra-close-consensus-v1','instrument':'SOL',
                 'checked_at':'2026-10-30T00:00:00+00:00',
                 'rows':[{'session':contested,'state':'CONFLICT_AWAITING_THREE','accepted_close':None}]})
            with patch('application.opportunities.session_freshness.next_session',return_value=None):
                charts, result, info=apply_consensus_windows(charts,[manifest],directory)
            self.assertEqual(info['SOL']['excluded_conflicting_sessions'],1)
            self.assertEqual(charts['SOL'][0]['timestamp'],rows[76]['timestamp'])
            self.assertNotIn(contested,[r['timestamp'] for r in charts['SOL']])
            self.assertEqual(len(result),1)

    def test_sharedata_adds_other_registered_share_to_replay(self):
        charts, manifests = demo()
        rows = charts['NPN']
        public=[{'session':r['timestamp'],'close':r['close']} for r in rows]
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); (folder/'raw').mkdir()
            original=b'[]'; raw_hash=hashlib.sha256(original).hexdigest()
            (folder/'raw'/(raw_hash+'.json')).write_bytes(original)
            source=[{'session':r['timestamp'], **{k:r[k] for k in ('open','high','low','close','volume')}} for r in rows]
            item={'schema':'sharedata-chart-capture-v1','provider':'SHAREDATA','symbol':'NPN','currency':'ZAR',
                  'acquired_at':'2026-10-30T00:00:00+00:00','raw_responses':[{'raw_sha256':raw_hash}],'rows':source}
            raw=json.dumps(item).encode(); digest=hashlib.sha256(raw).hexdigest()
            (folder/('NPN-'+digest+'.json')).write_bytes(raw)
            # The demo already has NPN; remove it to test new-instrument intake.
            charts.pop('NPN'); manifests=[m for m in manifests if m.instrument!='NPN']
            with patch('application.opportunities.zebra_instruments.mappings',return_value={'NPN':'NPN'}), \
                 patch('application.opportunities.radar_price_capture.latest_close_history',return_value={'rows':public}), \
                 patch('application.opportunities.session_freshness.next_session',return_value=None):
                charts, manifests=add_sharedata_histories(charts,manifests,folder)
            self.assertIn('NPN',charts)
            self.assertEqual(next(m for m in manifests if m.instrument=='NPN').provider,'SHAREDATA')
            self.assertEqual(len(charts['NPN']),150)

    def test_sharedata_intact_bar_continues_after_matched_closes(self):
        charts, manifests = demo()
        rows = charts.pop('SOL'); charts['SASOL'] = rows
        original = from_chart('SASOL', {'bars':rows, 'provenance':{'provider':'IRESS','source_sha256':'b'*64,'acquired_at':'2026-10-30T00:00:00+00:00'}})
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); (folder/'raw').mkdir()
            raw=b'[]'; source_hash=hashlib.sha256(raw).hexdigest()
            (folder/'raw'/(source_hash+'.json')).write_bytes(raw)
            series=[{'session':r['timestamp'], **{k:r[k] for k in ('open','high','low','close','volume')}} for r in rows[-25:]]
            day=next_session(rows[-1]['timestamp'])
            series.append({'session':day,'open':100,'high':101,'low':99,'close':100,'volume':1000})
            capture={'schema':'sharedata-chart-capture-v1','provider':'SHAREDATA','symbol':'SOL','currency':'ZAR',
                     'acquired_at':'2026-10-30T00:00:00+00:00','raw_responses':[{'raw_sha256':source_hash}],'rows':series}
            payload=json.dumps(capture).encode(); digest=hashlib.sha256(payload).hexdigest()
            (folder/('SOL-'+digest+'.json')).write_bytes(payload)
            charts, out=append_sharedata_bars(charts,[original],folder)
            self.assertEqual(charts['SASOL'][-1]['timestamp'],day)
            self.assertEqual(charts['SASOL'][-1]['_source'],'SHAREDATA')
            self.assertEqual(out[0].supplemental_sources[-1]['capture_sha256'],digest)

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
