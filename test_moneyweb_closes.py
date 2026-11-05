import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.import_moneyweb_closes import normalize, register
from scripts.reconcile_zebra_prices import build


class MoneywebCloseImportTests(unittest.TestCase):
    def setUp(self):
        self.received=datetime(2026,10,30,16,0,tzinfo=timezone.utc)
        self.rows=[{'session':(datetime(2026,9,1)+timedelta(days=i)).date().isoformat(),
                    'close':str(100+i)} for i in range(25)]
        self.raw=('Date,Close cents\n'+''.join(f"{row['session']},{int(row['close'])*100}\n" for row in self.rows)).encode()

    def test_units_and_live_row_are_explicit(self):
        rows,excluded=normalize(self.raw+b'2026-10-31,20000\n',date_column='Date',close_column='Close cents',
            unit='ZAR_CENTS',date_format='%Y-%m-%d',received_at=self.received.isoformat())
        self.assertEqual(rows,self.rows); self.assertEqual(excluded,1)

    def test_duplicate_and_missing_columns_are_rejected(self):
        kwargs=dict(date_column='Date',close_column='Close cents',unit='ZAR_CENTS',date_format='%Y-%m-%d',received_at=self.received.isoformat())
        with self.assertRaises(ValueError): normalize(self.raw+self.raw.splitlines(keepends=True)[1],**kwargs)
        with self.assertRaises(ValueError): normalize(self.raw,**{**kwargs,'close_column':'Unknown'})

    def test_import_reconciles_only_after_cross_source_match(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'export.csv'; source.write_bytes(self.raw)
            with patch('scripts.import_moneyweb_closes.mappings',return_value={'SASOL':'SOL'}):
                capture=register(source,instrument='SASOL',symbol='SOL',source_url='https://www.moneyweb.co.za/tools-and-data/',
                    date_column='Date',close_column='Close cents',unit='ZAR_CENTS',root=root,clock=lambda:self.received)
            self.assertEqual(capture['sessions'],25)
            moneyweb=json.loads(Path(capture['path']).read_text(encoding='utf-8'))
            self.assertIsNone(moneyweb['downloaded_at'])
            yahoo={'rows':[{'session':r['session'],'close':float(r['close'])} for r in self.rows],
                   'source_sha256':'a'*64,'acquired_at':self.received.isoformat()}
            with patch('scripts.reconcile_zebra_prices.latest_close_history',return_value=yahoo):
                result=build('SOL','SASOL',root)
            self.assertEqual(result['moneyweb']['state'],'CROSS_SOURCE_MATCHED_OPERATOR_SUPPLIED')
            comparison=json.loads(Path(result['path']).read_text(encoding='utf-8'))
            self.assertEqual(comparison['rows'][0]['votes']['100.00'],['MONEYWEB','YAHOO'])
            self.assertEqual(comparison['rows'][0]['observations'][0]['provider'],'YAHOO')

    def test_unmatched_and_modified_export_does_not_vote(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'export.csv'; source.write_bytes(self.raw)
            with patch('scripts.import_moneyweb_closes.mappings',return_value={'SASOL':'SOL'}):
                receipt=register(source,instrument='SASOL',symbol='SOL',source_url='https://www.moneyweb.co.za/',
                    date_column='Date',close_column='Close cents',unit='ZAR_CENTS',root=root,clock=lambda:self.received)
            yahoo={'rows':[{'session':r['session'],'close':float(r['close'])+50} for r in self.rows],
                   'source_sha256':'a'*64,'acquired_at':self.received.isoformat()}
            with patch('scripts.reconcile_zebra_prices.latest_close_history',return_value=yahoo):
                result=build('SOL','SASOL',root)
                self.assertEqual(result['moneyweb']['state'],'PENDING_IDENTITY_REVIEW')
                (root/'runtime/local-swing-data/moneyweb-prices/raw'/(receipt['raw_sha256']+'.csv')).write_bytes(b'changed')
                result=build('SOL','SASOL',root)
                self.assertEqual(result['moneyweb']['state'],'INVALID_CAPTURE_NOT_COUNTED')


if __name__=='__main__': unittest.main()
