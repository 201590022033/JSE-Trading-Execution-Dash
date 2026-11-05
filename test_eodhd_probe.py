import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from scripts.capture_eodhd_history import probe, rows_for_unit, unit_check, load_eodhd_history


class EodhdProbeTests(unittest.TestCase):
    @patch('scripts.capture_eodhd_history.sharedata_reference')
    def test_loader_uses_retained_raw_and_rejects_tampering(self, share):
        data=[{'date':f'2026-01-{i:02d}','open':1000,'high':1100,'low':900,'close':1000,'volume':10} for i in range(1,22)]
        raw=json.dumps(data).encode(); digest=sha256(raw).hexdigest()
        share.return_value={'provider':'SHAREDATA','source_sha256':'c'*64,
                            'rows':[{'session':r['date'],'close':'10'} for r in data]}
        receipt={'instrument':'DTC','symbol':'DTC.JSE','state':'CAPTURED_RESEARCH_ONLY',
                 'raw_sha256':digest,'reference_provider':'SHAREDATA','reference_sha256':'c'*64,
                 'price_unit':'ZAR_CENTS','acquired_at':'2026-11-04T12:00:00+00:00'}
        encoded=json.dumps(receipt).encode()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp); (folder/'eodhd/raw').mkdir(parents=True)
            source=folder/'eodhd/raw'/(digest+'.json'); source.write_bytes(raw)
            (folder/'eodhd'/('DTC-'+sha256(encoded).hexdigest()+'.json')).write_bytes(encoded)
            self.assertEqual(len(load_eodhd_history(folder,'DTC','DTC')['rows']),21)
            source.write_bytes(b'[]')
            with self.assertRaises(ValueError): load_eodhd_history(folder,'DTC','DTC')

    @patch('scripts.capture_eodhd_history.latest_close_history', side_effect=ValueError('missing'))
    @patch('scripts.capture_eodhd_history.sharedata_reference')
    def test_unit_check_falls_back_to_sharedata(self, share, yahoo):
        share.return_value = {'provider':'SHAREDATA','source_sha256':'a'*64,
                              'rows':[{'session':f'2026-01-{i:02d}','close':'10'} for i in range(1,22)]}
        data = [{'date':f'2026-01-{i:02d}','close':1000} for i in range(1,22)]
        result = {'cross_checks':{},'price_unit':'UNVERIFIED'}
        unit_check(result,data,Path('.'),'DTC','DTC')
        self.assertEqual(result['price_unit'],'ZAR_CENTS')
        self.assertEqual(result['reference_provider'],'SHAREDATA')

    def test_normalizes_cents_without_fabricating_missing_volume(self):
        raw = json.dumps([{'date':'2026-10-30', 'open':26000, 'high':27000,
                           'low':25000, 'close':26550, 'volume':None}]).encode()
        rows = rows_for_unit(raw, 'ZAR_CENTS', '2026-11-04T12:00:00+00:00')
        self.assertEqual(rows[0]['close'], '265.5')
        self.assertIsNone(rows[0]['volume'])

    @patch('scripts.capture_eodhd_history.mappings', return_value={'SASOL': 'SOL'})
    @patch('scripts.capture_eodhd_history.load_key', return_value=None)
    @patch('requests.get')
    def test_missing_key_makes_no_request(self, get, key, mappings):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(probe('SASOL', root)['state'], 'KEY_NOT_CONFIGURED')
            get.assert_not_called()

    @patch('scripts.capture_eodhd_history.mappings', return_value={'SASOL': 'SOL'})
    @patch('scripts.capture_eodhd_history.load_key', return_value='test-secret-value')
    @patch('requests.get')
    def test_retains_raw_and_never_writes_key(self, get, key, mappings):
        get.return_value.status_code = 200
        get.return_value.content = json.dumps([{'date': '2026-01-02', 'close': 100}]).encode()
        with tempfile.TemporaryDirectory() as root:
            result = probe('SASOL', root)
            self.assertEqual(result['sessions'], 1)
            files = list(Path(root).rglob('*.json'))
            self.assertEqual(len(files), 2)
            self.assertTrue(all(b'test-secret-value' not in f.read_bytes() for f in files))


if __name__ == '__main__':
    unittest.main()
