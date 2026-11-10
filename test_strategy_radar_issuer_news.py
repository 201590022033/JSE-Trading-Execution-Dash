import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from application.strategy_radar.issuer_news import issuer_news

NOW = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)


def source(body='MTN Group issues trading statement', **changes):
    return {'source_id': 'src1', 'receipt_id': 'receipt1', 'body': body,
            'url': 'https://example.com/article', 'published_at': None,
            'available_at': '2026-11-09T10:00:00+00:00', **changes}


class IssuerNewsTests(unittest.TestCase):
    def read(self, sources, instrument='MTN', product='CASH_SHARE'):
        with patch('application.strategy_radar.issuer_news.anticipatory_radar.sources', return_value=sources):
            return issuer_news(object(), instrument, product, now=NOW)

    def test_exact_name_receipt_and_no_invented_event(self):
        item = self.read([source()])['items'][0]
        self.assertEqual(item['issuer_match'], 'DIRECT_ISSUER_MENTION')
        self.assertEqual(item['observed_at'], '2026-11-09T10:00:00+00:00')
        self.assertIsNone(item['published_at'])
        self.assertIsNone(item['scheduled_event_date'])

    def test_ticker_only_and_wrong_issuer_do_not_match(self):
        result = self.read([source('MTN: unaudited report'), source('Vodacom Group issues trading statement')])
        self.assertEqual(result['state'], 'NO_MATCH')
        self.assertEqual(result['items'], [])

    def test_sens_publication_precision_is_not_fabricated(self):
        result = self.read([source(sens_provenance={'publication': {'precision': 'date', 'value': '2026-11-08'}})])
        self.assertEqual(result['items'][0]['source_kind'], 'RETAINED_SENS')
        self.assertEqual(result['items'][0]['publication_detail']['precision'], 'date')
        self.assertIsNone(result['items'][0]['published_at'])

    def test_old_source_stays_visible_with_window_label(self):
        result = self.read([source(available_at='2026-11-05T10:00:00+00:00')])
        self.assertEqual(result['state'], 'AVAILABLE')
        self.assertEqual(result['items'][0]['source_window'], 'OUTSIDE_SOURCE_WINDOW')

    def test_unknown_product_future_receipt_and_source_failure(self):
        self.assertEqual(self.read([source()], product='CFD')['reason'], 'PRODUCT_UNSUPPORTED')
        self.assertEqual(self.read([source()], instrument='NOT_REGISTERED')['reason'], 'ISSUER_MAPPING_UNAVAILABLE')
        self.assertEqual(self.read([source(available_at='2026-11-10T10:00:00+00:00')])['state'], 'PARTIAL')
        with patch('application.strategy_radar.issuer_news.anticipatory_radar.sources', side_effect=ValueError('bad archive')):
            self.assertEqual(issuer_news(object(), 'MTN', 'CASH_SHARE', now=NOW)['state'], 'UNAVAILABLE')

    def test_calendar_sources_not_duplicated_and_limit(self):
        rows = [source(source_id='calendar-source-1')] + [source(source_id=f'src{i}') for i in range(7)]
        result = self.read(rows)
        self.assertEqual(result['returned_count'], 5)
        self.assertTrue(all(not x['source_id'].startswith('calendar-source-') for x in result['items']))


if __name__ == '__main__':
    unittest.main()
