import tempfile
import unittest
from datetime import datetime, timezone

from application.opportunities.radar_price_capture import capture, latest_close_history


class ETFContextCaptureTest(unittest.TestCase):
    def test_benchmark_and_sectors_are_retained_as_distinct_research_sources(self):
        ids = ['ETF_STX40', 'ETF_STXFIN', 'ETF_STXRES', 'ETF_STXIND']
        class Fetcher:
            def get_chart(self, symbol, period):
                return {'symbol': symbol, 'currency': 'ZAR', 'interval': '1d',
                        'bars': [{'timestamp': '2026-11-02', 'open': 10, 'high': 11,
                                  'low': 9, 'close': 10, 'volume': 100}]}
        with tempfile.TemporaryDirectory() as folder:
            result = capture({'source_leads': [{'instrument_ids': ids}]}, Fetcher(), folder,
                             clock=lambda: datetime(2026, 11, 3, 8, tzinfo=timezone.utc), limit=4)
            self.assertEqual(result['state'], 'COMPLETE')
            self.assertEqual({x['instrument'] for x in result['results']}, set(ids))
            for instrument in ids:
                history = latest_close_history(folder, instrument)
                self.assertEqual(history['rows'][0]['session'], '2026-11-02')
                self.assertEqual(history['provider'], 'YAHOO')
                self.assertFalse(history['live_execution'])
