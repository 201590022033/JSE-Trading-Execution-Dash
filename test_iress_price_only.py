from datetime import datetime, timezone
import os
import tempfile
import unittest
from pathlib import Path

from application.opportunities.iress_price_only import parse, register, latest

UTC = timezone.utc
RAW = (b'Date,Open,High,Low,Close,Volume\n'
       b'30-Oct-2026,29000,29100,28000,28500,2m\n'
       b'29-Oct-2026,29090,29090,28006,28604,2m\n')


def test_completed_as_at_receipt_never_promotes_live_row():
    acquired = datetime(2026, 10, 30, 9, tzinfo=UTC)
    data = parse(RAW, 'SOL.JSE', acquired, datetime(2026, 11, 2, tzinfo=UTC))
    assert len(data['bars']) == 1
    assert data['bars'][0] == {'timestamp': '2026-10-29', 'open': 290.9, 'high': 290.9,
                                'low': 280.06, 'close': 286.04, 'volume': None}
    assert data['volume_basis'] == 'ROUNDED_SOURCE_VOLUME_NOT_IMPORTED'
    assert data['live_execution'] is False


def test_archive_revalidates_bytes_and_identity():
    with tempfile.TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        path = tmp_path / 'Time Series (SOL.JSE)_sample.csv'
        path.write_bytes(RAW)
        acquired = datetime(2026, 10, 30, 9, tzinfo=UTC)
        os.utime(path, (acquired.timestamp(), acquired.timestamp()))
        now = datetime(2026, 10, 30, 10, tzinfo=UTC)
        result = register(path, tmp_path, now)
        assert latest(tmp_path, now) == result
        raw = tmp_path / 'price-only' / 'raw' / (result['source_sha256'] + '.csv')
        raw.write_bytes(RAW + b'changed')
        assert latest(tmp_path, now) is None


def test_rejects_rounded_prices_and_wrong_symbol():
    now = datetime(2026, 10, 30, 10, tzinfo=UTC)
    with unittest.TestCase().assertRaises(ValueError):
        parse(RAW.replace(b'29090', b'29.1k'), 'SOL.JSE', now, now)
    with unittest.TestCase().assertRaises(ValueError):
        parse(RAW, 'OTHER.JSE', now, now)


def test_price_only_zebra_never_backdates():
    import hashlib
    import json
    from scripts.zebra_handover import handover
    panel = {'schema': 'research-feature-panel/1', 'rows': [], 'availability': 'reconstructed', 'summary': {}}
    panel['panel_id'] = 'sha256:' + hashlib.sha256(json.dumps(panel, sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True).encode()).hexdigest()
    data = parse(RAW, 'SOL.JSE', datetime(2026, 10, 30, 9, tzinfo=UTC), datetime(2026, 10, 30, 10, tzinfo=UTC))
    extension = {'bars': data['bars'], 'provenance': {k: data[k] for k in ('provider', 'origin_symbol', 'source_sha256', 'acquired_at')}}
    result = handover(panel, extension)
    assert result['rows'][0]['available_at'] == data['acquired_at']
    assert result['rows'][0]['source'] == 'iress_time_series'


def test_bad_ohlc_is_reported_without_discarding_good_rows():
    now = datetime(2026, 10, 30, 10, tzinfo=UTC)
    data = parse(RAW + b'28-Oct-2026,0,0,0,29000,0\n', 'SOL.JSE', now, now)
    assert data['excluded_rows'] == [{'session': '2026-10-28', 'reason': 'INVALID_OR_ZERO_OHLC'}]
    assert len(data['bars']) == 1


class PriceOnlyTests(unittest.TestCase):
    def test_receipt_cutoff(self): test_completed_as_at_receipt_never_promotes_live_row()
    def test_archive(self): test_archive_revalidates_bytes_and_identity()
    def test_exact_prices(self): test_rejects_rounded_prices_and_wrong_symbol()
    def test_handover_time(self): test_price_only_zebra_never_backdates()
    def test_invalid_rows(self): test_bad_ohlc_is_reported_without_discarding_good_rows()
    def test_local_endpoint(self):
        from flask import Flask
        from application.opportunities.ost_data_api import create_ost_blueprint
        with tempfile.TemporaryDirectory() as directory:
            app = Flask(__name__)
            app.register_blueprint(create_ost_blueprint(lambda: None, Path(directory)))
            client = app.test_client()
            response = client.get('/api/v1/ost/price-only/SASOL')
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            source = Path(directory) / 'Time Series (SOL.JSE)_sample.csv'
            source.write_bytes(RAW)
            acquired = datetime(2026, 10, 30, 9, tzinfo=UTC)
            os.utime(source, (acquired.timestamp(), acquired.timestamp()))
            register(source, Path(directory), datetime(2026, 10, 30, 10, tzinfo=UTC))
            # Endpoint uses real clock; patch it to avoid coupling to test date.
            from unittest.mock import patch
            with patch('application.opportunities.ost_data_api.datetime') as clock:
                clock.now.return_value = datetime(2026, 10, 30, 10, tzinfo=UTC)
                response = client.get('/api/v1/ost/price-only/SASOL')
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json['live_execution'])
            self.assertIsNone(response.json['chart']['bars'][-1]['volume'])


if __name__ == '__main__':
    unittest.main()
