from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from application.strategy_radar.receipt_prewarm import refresh_from_receipt


class ReceiptPrewarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'runtime/local-swing-data/strategy-radar'
        self.folder.mkdir(parents=True)
        with closing(sqlite3.connect(self.folder / 'watches.sqlite3')) as db, db:
            db.execute('CREATE TABLE radar_watch (instrument TEXT, benchmark TEXT, state TEXT)')
            db.execute("INSERT INTO radar_watch VALUES ('VOD','ETF_STX40','WATCHING')")
        self.receipt = self.root / 'receipt.json'
        self.clock = datetime(2026, 11, 27, 8, tzinfo=timezone.utc)
        self.payload = {'schema':'zebra-source-refresh-v1', 'finished_at':'2026-11-27T07:30:00+00:00',
                        'research_only':True, 'live_execution':False,
                        'results':[{'instrument':'VOD','capture':{'state':'CAPTURED'}},
                                   {'instrument':'ETF_STX40','capture':{'state':'CAPTURED'}}]}
        self.receipt.write_text(json.dumps(self.payload))
        self.calls = []

    def loader(self, keys, **kwargs):
        self.calls.append(keys)
        return {'as_of':self.clock.isoformat(), 'watches':{
            key:{'state':'AVAILABLE','latest_session':'2026-11-26','history':{'rows':[]}} for key in keys}}

    def test_updates_share_and_benchmark_and_preserves_newer_cache(self):
        result = refresh_from_receipt(self.root, self.receipt, loader=self.loader, now=self.clock)
        self.assertEqual(set(result), {'VOD','ETF_STX40'})
        cache = self.folder / 'daily-cache/VOD.json'
        cache.write_text(json.dumps({'daily':{'latest_session':'2026-11-27'}}))
        refresh_from_receipt(self.root, self.receipt, loader=self.loader, now=self.clock)
        self.assertEqual(json.loads(cache.read_bytes())['daily']['latest_session'], '2026-11-27')

    def test_failed_and_corrupt_receipts_do_not_change_cache(self):
        self.payload['results'] = []
        self.receipt.write_text(json.dumps(self.payload))
        self.assertEqual(refresh_from_receipt(self.root, self.receipt, loader=self.loader, now=self.clock), [])
        self.assertEqual(self.calls, [])
        self.receipt.write_text('{')
        with self.assertRaises(ValueError):
            refresh_from_receipt(self.root, self.receipt, loader=self.loader, now=self.clock)
