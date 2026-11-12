import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from application.data_freshness import (
    build_dashboard_freshness,
    daily_session_clock,
    intraday_clock,
    quote_clock,
)


NOW = datetime(2026, 11, 12, 8, 14, tzinfo=timezone.utc)


class DataFreshnessTests(unittest.TestCase):
    def test_viewpoint_clock_uses_existing_two_interval_stale_rule(self):
        row = {
            'instrument': 'MTN', 'interval_minutes': 5, 'clock_semantics': 'START',
            'provisional': False, 'bar_end': '2026-11-12T08:10:00+00:00',
        }
        source = intraday_clock('viewpoint', 'ViewPoint bars', [row], 'MTN', 5, NOW)
        self.assertEqual(source['state'], 'FRESH')
        self.assertEqual(source['expires_at'], '2026-11-12T08:20:00+00:00')
        stale = intraday_clock('viewpoint', 'ViewPoint bars', [row], 'MTN', 5,
                               datetime(2026, 11, 12, 8, 20, 1, tzinfo=timezone.utc))
        self.assertEqual(stale['state'], 'STALE')
        self.assertEqual(intraday_clock('viewpoint', 'ViewPoint bars', [], 'MTN', 5, NOW)['state'], 'UNKNOWN')

    def test_quote_clock_uses_source_time_not_receipt_time(self):
        quote = {'source_time': '2026-11-12T08:09:00+00:00',
                 'received_at': '2026-11-12T08:13:59+00:00'}
        source = quote_clock('quote', 'Manual quote', quote, 'MTN', NOW)
        self.assertEqual(source['state'], 'FRESH')
        self.assertEqual(source['expires_at'], '2026-11-12T08:14:00+00:00')
        unknown = quote_clock('quote', 'Manual quote', {'received_at': NOW.isoformat()}, 'MTN', NOW)
        self.assertEqual(unknown['state'], 'UNKNOWN')
        self.assertIsNone(unknown['expires_at'])

    def test_daily_clock_uses_reviewed_next_session_rule(self):
        source = daily_session_clock('daily', 'Daily', '2026-11-11', '2026-11-11')
        self.assertEqual(source['state'], 'FRESH')
        self.assertEqual(source['expires_at'], '2026-11-13T00:00:00+00:00')
        self.assertEqual(daily_session_clock('daily', 'Daily', '2026-11-10', '2026-11-11')['state'], 'STALE')
        self.assertIsNone(daily_session_clock('daily', 'Daily', '2027-01-01', '2027-01-04')['expires_at'])

    def test_dashboard_groups_manual_and_historical_sources_without_fake_expiry(self):
        result = build_dashboard_freshness(
            NOW,
            news_feed={'state': 'AVAILABLE', 'last_success': '2026-11-12T07:00:00+00:00'},
            screen_status={'expected_session': '2026-11-11'},
            screen_items=[{'research_key': 'MTN', 'latest_session': '2026-11-11'}],
            daily_imports={'coverage': [], 'current_members': []},
            radar_inputs=[{'instrument': 'MTN', 'bars': [], 'quote': {}}],
            event_radar={'source_freshness': 'CURRENT_CAPTURE',
                         'latest_capture': {'received_at': '2026-11-12T07:00:00+00:00'},
                         'sens_discovery': {'sources': []}},
        )
        news = next(item for item in result['areas']['market-ai'] if item['id'] == 'public-news')
        self.assertEqual(news['state'], 'FRESH')
        self.assertEqual(news['expires_at'], '2026-11-13T07:00:00+00:00')
        history = next(item for item in result['areas']['backtest-lab'] if item['id'] == 'backtest-history')
        self.assertEqual(history['state'], 'HISTORICAL_NO_EXPIRY')
        self.assertIsNone(history['expires_at'])
        bars = next(item for item in result['areas']['market-overview'] if item['id'] == 'viewpoint-5m:MTN')
        self.assertEqual(bars['action'], 'manual-source')
        sessions = {item['id'] for item in result['areas']['system']
                    if item['state'] == 'MANUAL_ONLY'}
        self.assertTrue({'ost-session', 'viewpoint-session'} <= sessions)

    def test_freshness_api_is_local_and_does_not_start_news_refresh(self):
        import app as application

        class Repository:
            closed = False

            def close(self):
                self.closed = True

        class Store:
            def list_watches(self):
                return []

        with TemporaryDirectory() as tmp:
            radar = SimpleNamespace(store=Store(), folder=Path(tmp))
            repository = Repository()
            with (
                patch.object(application, 'strategy_radar_service', return_value=radar),
                patch.object(application, 'zebra_research_screen', None),
                patch.object(application, 'runtime_repository', return_value=repository),
                patch('application.opportunities.research_data_requests.status',
                      return_value={'coverage': [], 'current_members': []}),
                patch('market_intelligence.anticipatory_radar.status',
                      return_value={'source_freshness': 'STALE_OR_UNAVAILABLE',
                                    'sens_discovery': {'sources': []}}),
                patch('dashboard_feeds.feeds.peek_news',
                      return_value={'state': 'NOT_LOADED', 'last_success': None}) as peek,
                patch('dashboard_feeds.feeds.news', side_effect=AssertionError('status must not scan')) as scan,
            ):
                client = application.app.test_client()
                response = client.get('/api/v1/data-freshness')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['schema'], 'dashboard-source-freshness-v1')
                self.assertIn('backtest-lab', response.json['areas'])
                prepared = next(item for item in response.json['areas']['backtest-lab']
                                if item['id'] == 'prepared-research-context')
                self.assertEqual(prepared['state'], 'NOT_PREPARED')
                self.assertIsNone(prepared['expires_at'])
                self.assertTrue(repository.closed)
                peek.assert_called_once()
                scan.assert_not_called()
                remote = client.get('/api/v1/data-freshness', environ_base={'REMOTE_ADDR': '203.0.113.1'})
                self.assertEqual(remote.status_code, 403)


if __name__ == '__main__':
    unittest.main()
