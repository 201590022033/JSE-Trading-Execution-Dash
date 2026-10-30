import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from application.opportunities.radar_price_capture import capture, radar_instruments, usable_close, latest_close_history
from application.opportunities.public_research import public_share_catalog


class RadarPublicPriceTests(unittest.TestCase):
    def test_same_day_close_excluded_until_after_cutoff(self):
        self.assertFalse(usable_close('2026-10-29', datetime(2026, 10, 29, 15, 19, tzinfo=timezone.utc)))
        self.assertTrue(usable_close('2026-10-29', datetime(2026, 10, 29, 15, 20, tzinfo=timezone.utc)))
        self.assertTrue(usable_close('2026-10-28', datetime(2026, 10, 29, 8, tzinfo=timezone.utc)))

    def test_only_exact_registered_links_and_active_watches(self):
        radar = {'watches': [{'state': 'EXPIRED_UNREVIEWED', 'instrument_ids': ['FSR']},
                             {'state': 'UNCONFIRMED_SOURCE_CANDIDATE', 'instrument_ids': ['SASOL', 'UNKNOWN'], 'record_id': 'watch'}],
                 'source_leads': [{'instrument_ids': ['SASOL'], 'source_id': 'lead'}]}
        self.assertEqual(radar_instruments(radar), [('SASOL', ['watch', 'lead'])])

    def test_success_and_failure_are_independent_and_keep_intraday_row(self):
        catalog = public_share_catalog()
        keys = sorted(list(catalog))[:2]
        radar = {'source_leads': [{'instrument_ids': keys, 'source_id': 'lead'}]}
        class Fetcher:
            def get_chart(self, symbol, period):
                if symbol == catalog[keys[1]]['yahoo_symbol']:
                    raise RuntimeError('source unavailable')
                return {'symbol': symbol, 'currency': 'ZAR', 'interval': '1d', 'bars': [
                    {'timestamp': '2026-10-28', 'close': 10}, {'timestamp': '2026-10-29', 'close': 11}]}
        with tempfile.TemporaryDirectory() as folder:
            result = capture(radar, Fetcher(), folder, clock=lambda: datetime(2026, 10, 29, 10, tzinfo=timezone.utc))
            self.assertEqual([r['state'] for r in result['results']], ['CAPTURED', 'FAILED'])
            record = json.loads(Path(folder, result['results'][0]['file']).read_text())
            self.assertEqual(record['last_completed_session'], '2026-10-28')
            self.assertEqual(len(record['chart']['bars']), 2)
            self.assertFalse(record['raw_provider_bytes_retained'])
            self.assertFalse(record['live_execution'])
            history = latest_close_history(folder, keys[0])
            self.assertEqual(history['rows'][0]['session'], '2026-10-28')
            self.assertEqual(history['rows'][0]['close'], 10)
            self.assertFalse(history['rows'][0]['ohlc_valid'])
            path = Path(folder, result['results'][0]['file'])
            path.write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                latest_close_history(folder, keys[0])

    def test_limit_prioritizes_shares_without_an_existing_capture(self):
        keys = sorted(public_share_catalog())[:2]
        radar = {'source_leads': [{'instrument_ids': keys, 'source_id': 'lead'}]}
        class Fetcher:
            def get_chart(self, symbol, period):
                return {'symbol': symbol, 'currency': 'ZAR', 'interval': '1d',
                        'bars': [{'timestamp': '2026-10-28', 'close': 10}]}
        with tempfile.TemporaryDirectory() as folder:
            clock = lambda: datetime(2026, 10, 29, 10, tzinfo=timezone.utc)
            first = capture(radar, Fetcher(), folder, clock=clock, limit=1)
            second = capture(radar, Fetcher(), folder, clock=clock, limit=1)
            self.assertEqual(first['results'][0]['instrument'], keys[0])
            self.assertEqual(second['results'][0]['instrument'], keys[1])
            self.assertEqual(second['deferred'], 1)


if __name__ == '__main__':
    unittest.main()
