from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.capture_africa_api import probe,rows_for_unit
from scripts.reconcile_zebra_prices import build
from application.opportunities.africa_api_credentials import save_key


class AfricaAPITests(unittest.TestCase):
    def test_absent_key_makes_no_network_request(self):
        with TemporaryDirectory() as root, patch('scripts.capture_africa_api.mappings',return_value={'BVT':'BVT'}):
            def no_fetch(*args,**kwargs): self.fail('network call with no key')
            result=probe('BVT',root,key_reader=lambda:None,fetch=no_fetch)
        self.assertEqual(result['state'],'KEY_NOT_CONFIGURED')
        self.assertEqual(result['requests'],0)

    def test_rows_keep_optional_bad_values_as_missing(self):
        raw=json.dumps({'data':[{'trade_date':'2026-10-28','open_price':0,'high_price':10100,
                                 'low_price':9900,'close_price':10000,'volume':10}]}).encode()
        rows=rows_for_unit(raw,'ZAR_CENTS','2026-10-30T12:00:00+00:00')
        self.assertIsNone(rows[0]['open']); self.assertEqual(rows[0]['close'],'100')
        self.assertIn('open',rows[0]['invalid_fields'])

    def test_capture_calibrates_unit_and_reconciles_without_storing_secret(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); folder=root/'runtime/local-swing-data/radar-public-prices'; folder.mkdir(parents=True)
            days=[(datetime(2026,9,1)+timedelta(days=i)).date().isoformat() for i in range(25)]
            prices=[100+i for i in range(25)]
            bars=[{'timestamp':d,'close':p} for d,p in zip(days,prices)]
            reference={'instrument':'BVT','provider':'YAHOO','symbol':'BVT.JO','chart':{'bars':bars}}
            refraw=json.dumps(reference).encode(); refhash=sha256(refraw).hexdigest()
            (folder/('BVT-20261030-'+refhash+'.json')).write_bytes(refraw)
            public={'rows':[{'session':d,'close':p} for d,p in zip(days,prices)],
                    'source_sha256':refhash,'acquired_at':'2026-10-30T12:00:00+00:00'}
            identity=json.dumps({'data':{'exchange_code':'JSE','symbol':'BVT'}}).encode()
            history=json.dumps({'data':[{'trade_date':d,'open_price':p*100,'high_price':p*100,
                         'low_price':p*100,'close_price':p*100,'volume':100,'source_code':'example'}
                         for d,p in zip(days,prices)]}).encode()
            def fetch(url,**kwargs):
                self.assertFalse(kwargs['allow_redirects'])
                return SimpleNamespace(status_code=200,content=history if url.endswith('/history') else identity)
            with patch('scripts.capture_africa_api.mappings',return_value={'BVT':'BVT'}), \
                 patch('scripts.capture_africa_api.latest_close_history',return_value=public):
                result=probe('BVT',root,key_reader=lambda:'fake-test-token',fetch=fetch,
                             clock=lambda:datetime(2026,10,30,12,0,tzinfo=timezone.utc))
            self.assertEqual(result['state'],'CAPTURED_UNIT_CROSSCHECKED')
            self.assertEqual(result['unit'],'ZAR_CENTS'); self.assertEqual(result['requests'],2)
            for path in (root/'runtime/local-swing-data/africa-api').rglob('*.json'):
                self.assertNotIn(b'fake-test-token',path.read_bytes())
            with patch('scripts.reconcile_zebra_prices.latest_close_history',return_value=public):
                result=build('BVT','BVT',root)
            self.assertEqual(result['africa_api']['state'],'UNIT_CROSSCHECKED_RESEARCH')
            comparison=json.loads(Path(result['path']).read_text(encoding='utf-8'))
            self.assertEqual(comparison['rows'][0]['fields']['high']['accepted_value'],'100.00')
            self.assertEqual(len(comparison['rows'][0]['votes']['100.00']),2)

    def test_invalid_key_is_not_written(self):
        with self.assertRaises(ValueError): save_key('short')


if __name__=='__main__': unittest.main()
