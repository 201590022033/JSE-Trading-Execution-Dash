import unittest
from datetime import datetime, timezone
from decimal import Decimal

from application.strategy_radar.market_status import cached_index_status, market_status, quote_status
from dashboard_feeds import DashboardFeeds
from application.strategy_radar.quotes import QuoteCandidate, QuoteKind, select_quote


def utc(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class MarketStatusTests(unittest.TestCase):
    def test_cash_schedule_is_not_live_exchange_status(self):
        result = market_status(utc('2026-11-09T08:30:00'))
        self.assertEqual(result['schedule']['status'], 'OPEN')
        self.assertEqual(result['operational_status'], 'UNKNOWN')
        self.assertEqual(result['all_share']['status'], 'UNAVAILABLE')
        self.assertIn('ETF is not an index', result['top_40']['reason'])

    def test_calendar_holiday_weekend_and_unreviewed_year(self):
        for stamp in ('2026-11-04T10:00:00', '2026-11-08T10:00:00'):
            self.assertEqual(market_status(utc(stamp))['schedule']['status'], 'CLOSED')
        self.assertEqual(market_status(utc('2027-01-04T10:00:00'))['schedule']['status'], 'UNKNOWN')

    def test_auction_boundaries_not_falsely_closed(self):
        self.assertEqual(market_status(utc('2026-11-09T06:59:59'))['schedule']['status'], 'UNKNOWN')
        self.assertEqual(market_status(utc('2026-11-09T07:00:00'))['schedule']['status'], 'OPEN')
        self.assertEqual(market_status(utc('2026-11-09T14:49:59'))['schedule']['status'], 'OPEN')
        self.assertEqual(market_status(utc('2026-11-09T14:50:00'))['schedule']['status'], 'UNKNOWN')
        with self.assertRaises(ValueError):
            market_status(datetime(2026, 11, 9))

    def test_quote_source_and_receipt_clocks_and_conflicts(self):
        now = utc('2026-11-09T13:00:00')
        def candidate(provider, price):
            return QuoteCandidate('MTN', provider, utc('2026-11-09T12:40:00'), utc('2026-11-09T12:45:00'),
                                  QuoteKind.DELAYED, 'ZAR', last=Decimal(price), delay_seconds=900)
        selected = select_quote('MTN', [candidate('ONE', '210'), candidate('TWO', '211')], now, max_age_seconds=300)
        result = quote_status(selected)
        self.assertEqual(result['fields']['bid']['status'], 'UNAVAILABLE')
        self.assertEqual(result['fields']['last']['status'], 'CONFLICT')
        self.assertEqual(result['fields']['last']['source_age_seconds'], 1200)
        self.assertEqual(result['fields']['last']['receipt_age_seconds'], 900)
        self.assertEqual(result['fields']['last']['unit'], 'ZAR')
        self.assertEqual(quote_status(select_quote('MTN', [candidate('ONE', '210')], now, 300))['fields']['last']['status'], 'STALE')

    def test_unknown_clock_is_not_live(self):
        now = utc('2026-11-09T13:00:00')
        candidate = QuoteCandidate('MTN', 'TEST', None, now, QuoteKind.LIVE, 'ZAR', last=Decimal('100'))
        self.assertEqual(quote_status(select_quote('MTN', [candidate], now))['fields']['last']['status'], 'UNKNOWN')

    def test_cached_index_is_daily_bar_not_quote_and_never_refreshes(self):
        now = utc('2026-11-09T13:00:00')
        feed = DashboardFeeds()
        try:
            self.assertIsNone(feed.peek_cached_chart('^J203.JO', '3mo'))
            feed._entries[('^J203.JO', '3mo')] = {'data': {'price': 114000, 'interval': '1d', 'symbol': '^J203.JO', 'currency': 'points',
                 'timestamp_kind': 'session_date', 'source_timestamp': '2026-11-06T00:00:00+00:00'},
                 'last_success': '2026-11-09T12:00:00+00:00', 'last_attempt': None, 'error': None, 'refreshing': False}
            snapshot = feed.peek_cached_chart('^J203.JO', '3mo')
            result = market_status(now, snapshot)['all_share']
            self.assertEqual(result['status'], 'HISTORICAL_BAR')
            self.assertEqual(result['source_session'], '2026-11-06')
            self.assertIsNone(result['source_time'])
            self.assertIsNone(result['delay_seconds'])
            self.assertEqual(result['receipt_age_seconds'], 3600)
            current = feed.peek_cached_chart('^J203.JO', '3mo')
            current['data']['source_timestamp'] = '2026-11-09T00:00:00+02:00'
            result = cached_index_status(current, now)
            self.assertEqual(result['status'], 'PROVISIONAL_BAR')
            self.assertIn('completion unverified', result['basis'])
            self.assertEqual(cached_index_status(current, utc('2026-11-10T00:00:00'))['status'], 'HISTORICAL_BAR')
            current['data']['source_timestamp'] = '2026-11-08T00:00:00+02:00'
            self.assertEqual(cached_index_status(current, now)['status'], 'UNKNOWN')
            snapshot['data']['price'] = 1
            self.assertEqual(feed.peek_cached_chart('^J203.JO', '3mo')['data']['price'], 114000)
            snapshot['data']['timestamp_kind'] = 'interval_clock_unverified'
            self.assertEqual(cached_index_status(snapshot, now)['status'], 'UNKNOWN')
            snapshot['data']['symbol'] = 'STX40.JO'
            self.assertEqual(cached_index_status(snapshot, now)['status'], 'UNKNOWN')
            snapshot['data']['symbol'] = '^J203.JO'
            snapshot['last_success'] = '2026-11-09T14:00:00+00:00'
            snapshot['data']['timestamp_kind'] = 'session_date'
            self.assertEqual(cached_index_status(snapshot, now)['status'], 'UNKNOWN')
        finally:
            feed._pool.shutdown()


if __name__ == '__main__':
    unittest.main()
