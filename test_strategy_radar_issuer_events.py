import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import research_calendar as cal
from application.strategy_radar.issuer_events import issuer_events

NOW = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)


class IssuerEventsTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)

    def event(self, quote, instruments=('SASOL',), key='test-sasol'):
        source = cal.import_source(self.repo, {'source_url':'https://issuer.example/calendar',
            'title':'Calendar', 'body':quote, 'captured_at':(NOW-timedelta(hours=2)).isoformat(),
            'published_at':(NOW-timedelta(days=1)).isoformat(), 'provenance':'Operator capture'}, NOW)
        event = cal.propose_event(self.repo, {'event_key':key, 'title':'Results',
            'instrument_ids':list(instruments), 'source_receipt_id':source['record_id'],
            'source_quote':quote, 'event_date':'2026-10-22', 'timezone':'Africa/Johannesburg'}, NOW)
        return event

    def view(self, key='SASOL', product='CASH_SHARE'):
        return issuer_events(self.repo, key, product, now=NOW)

    def test_confirmed_source_and_clocks_remain_distinct(self):
        event = self.event('Sasol update on 22 October 2026.')
        self.assertEqual(self.view()['events'][0]['state'], 'EXPECTED_UNCONFIRMED')
        cal.confirm_event(self.repo, event['record_id'], 'reviewer', NOW, origin='AI_PRIMARY_SOURCE_REVIEW')
        with patch.object(self.repo, 'save_paper_record', side_effect=AssertionError('read wrote')):
            result = self.view()
        item = result['events'][0]
        self.assertEqual(result['state'], 'AVAILABLE')
        self.assertEqual(item['state'], 'DATE_REVIEWED')
        self.assertEqual(item['review_origin'], 'AI_PRIMARY_SOURCE_REVIEW')
        self.assertEqual(item['reviewed_at'], NOW.isoformat())
        self.assertEqual(item['published_at'], (NOW-timedelta(days=1)).isoformat())
        self.assertEqual(item['captured_at'], (NOW-timedelta(hours=2)).isoformat())
        self.assertEqual(item['source_received_at'], NOW.isoformat())
        self.assertEqual(item['time_precision'], 'DATE_ONLY_RELEASE_TIME_UNKNOWN')
        self.assertIsNone(item['anchor_at'])
        self.assertFalse(item['independent_publisher_verification'])

    def test_no_bare_ticker_sector_or_mismatched_issuer_attribution(self):
        self.event('SAS ticker sector update 22 October 2026.', key='ticker-only')
        self.assertEqual(self.view()['state'], 'NO_MATCH')
        self.event('MTN market update 22 October 2026.', instruments=('MTN',), key='mtn-ticker')
        self.assertEqual(self.view('MTN')['state'], 'NO_MATCH')
        self.assertEqual(self.view('VOD')['state'], 'NO_MATCH')

    def test_unknown_product_mapping_and_failed_read_fail_closed(self):
        self.assertEqual(self.view(product='CFD')['reason'], 'PRODUCT_UNSUPPORTED')
        self.assertEqual(self.view('NOT_A_SHARE')['reason'], 'ISSUER_MAPPING_UNAVAILABLE')
        with patch.object(cal, 'status', side_effect=RuntimeError('offline')):
            self.assertEqual(self.view()['state'], 'UNAVAILABLE')

    def test_cancelled_and_past_are_not_upcoming(self):
        event = self.event('Sasol update on 22 October 2026.')
        cal.confirm_event(self.repo, event['record_id'], 'reviewer', NOW)
        cal.cancel_event(self.repo, event['record_id'], 'reviewer', 'cancelled', NOW)
        self.assertEqual(self.view()['state'], 'NO_MATCH')

    def test_malformed_source_does_not_become_no_events(self):
        self.event('Sasol update on 22 October 2026.')
        with patch.object(cal, '_source', side_effect=ValueError('bad hash')):
            result = self.view()
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertEqual(result['unverifiable_count'], 1)

    def test_date_only_today_preserved_then_past_excluded(self):
        event = self.event('Sasol update on 22 October 2026.')
        today = datetime(2026, 10, 22, 10, tzinfo=timezone.utc)
        tomorrow = today + timedelta(days=1)
        self.assertEqual(issuer_events(self.repo, 'SASOL', 'CASH_SHARE', now=today)['events'][0]['state'], 'EXPECTED_UNCONFIRMED')
        self.assertEqual(issuer_events(self.repo, 'SASOL', 'CASH_SHARE', now=tomorrow)['state'], 'NO_MATCH')
        cal.confirm_event(self.repo, event['record_id'], 'reviewer', NOW)
        current = issuer_events(self.repo, 'SASOL', 'CASH_SHARE', now=today)
        self.assertEqual(current['events'][0]['state'], 'DATE_REVIEWED')
        self.assertIsNone(current['events'][0]['anchor_at'])
        self.assertEqual(issuer_events(self.repo, 'SASOL', 'CASH_SHARE', now=tomorrow)['state'], 'NO_MATCH')

    def test_source_backed_exact_time_is_not_date_only(self):
        quote = 'Sasol meeting 22 October 2026 at 2026-10-22T10:00:00+02:00.'
        source = cal.import_source(self.repo, {'source_url':'https://issuer.example/calendar',
            'title':'Calendar', 'body':quote, 'captured_at':NOW.isoformat(), 'provenance':'Operator capture'}, NOW)
        event = cal.propose_event(self.repo, {'event_key':'exact-meeting', 'title':'Meeting',
            'instrument_ids':['SASOL'], 'source_receipt_id':source['record_id'], 'source_quote':quote,
            'starts_at':'2026-10-22T10:00:00+02:00', 'timezone':'Africa/Johannesburg'}, NOW)
        cal.confirm_event(self.repo, event['record_id'], 'reviewer', NOW)
        item = self.view()['events'][0]
        self.assertEqual(item['time_precision'], 'EXACT_SOURCE_TIME')
        self.assertEqual(item['anchor_at'], '2026-10-22T08:00:00+00:00')
        self.assertEqual(issuer_events(self.repo, 'SASOL', 'CASH_SHARE', now=datetime(2026,10,22,9,tzinfo=timezone.utc))['state'], 'NO_MATCH')

    def test_old_unconfirmed_revision_is_not_a_current_event(self):
        quote = 'Sasol update 22 October 2026; revised to 23 October 2026.'
        event = self.event(quote)
        revised = cal.propose_event(self.repo, {'event_key':event['event_key'], 'title':'Revised update',
            'instrument_ids':['SASOL'], 'source_receipt_id':event['source_receipt_id'],
            'source_quote':quote, 'event_date':'2026-10-23', 'timezone':'Africa/Johannesburg',
            'supersedes_event_id':event['record_id']}, NOW)
        items = self.view()['events']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['event_id'], revised['record_id'])
        self.assertEqual(items[0]['supersedes_event_id'], event['record_id'])


if __name__ == '__main__':
    unittest.main()
