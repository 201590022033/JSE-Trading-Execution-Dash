import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, call

from application.strategy_radar.intraday_store import IntradayCache
from application.strategy_radar.prepared_context import PreparedContextStore, build_packet
from application.strategy_radar.service import RadarService


NOW = datetime(2026, 11, 12, 8, 14, tzinfo=timezone.utc)


class PreparedContextTests(unittest.TestCase):
    def test_new_top5_membership_prepares_a_local_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = [NOW]
            service = RadarService(tmp, clock=lambda: clock[0],
                                   prewarm=lambda keys, **kwargs: {'watches': {}})
            service._prepare_after_change = Mock()
            snapshot = {
                'schema': 'zebra-research-screen-v1',
                'generated_at': '2026-11-12T08:13:00+00:00',
                'opportunities': [{'research_key': f'SHARE{i}', 'sector': 'sector'}
                                  for i in range(1, 6)],
            }
            service.reconcile(snapshot, start_worker=False)
            clock[0] = NOW + timedelta(seconds=30)
            reordered = {**snapshot, 'generated_at': '2026-11-12T08:13:30+00:00',
                         'opportunities': list(reversed(snapshot['opportunities']))}
            service.reconcile(reordered, start_worker=False)
            self.assertEqual(service._prepare_after_change.call_args_list,
                             [call('TOP5_CHANGED'), call('TOP5_CHANGED')])

    def test_pin_change_refreshes_current_choice_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp, clock=lambda: NOW)
            service.store.reconcile([{'instrument': 'MTN', 'strategy_id': 'daily',
                                      'strategy_version': '1.0'}], NOW)
            service._prepare_after_change = Mock()
            service.set_pin('MTN', True)
            service._prepare_after_change.assert_called_once_with('PIN_CHANGED')

    def test_existing_watches_get_one_initial_context_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp, clock=lambda: NOW)
            service.store.reconcile([{'instrument': 'MTN', 'strategy_id': 'daily',
                                      'strategy_version': '1.0'}], NOW)
            service._prepare_after_change = Mock(return_value={'state': 'PREPARED'})
            self.assertEqual(service.ensure_prepared_context()['state'], 'PREPARED')
            service._prepare_after_change.assert_called_once_with('INITIAL_SNAPSHOT')

    def test_packet_captures_current_choices_and_retained_evidence_with_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp, clock=lambda: NOW)
            choices = [{'instrument': f'SHARE{i}', 'strategy_id': 'daily',
                        'strategy_version': '1.0', 'sector': 'sector'}
                       for i in range(1, 6)]
            service.store.reconcile(choices, NOW)
            pin = service.store.select({'instrument': 'PIN', 'strategy_id': 'daily',
                                        'strategy_version': '1.0', 'sector': 'sector'}, NOW)
            service.store.set_flag('PIN', 'pinned', True, NOW)
            daily_cache = service.folder / 'daily-cache'
            daily_cache.mkdir()
            (daily_cache / 'SHARE1.json').write_text(json.dumps({
                'as_of': NOW.isoformat(), 'daily': {'latest_session': '2026-11-11'},
            }), encoding='utf-8')
            cache = IntradayCache(service.folder / 'intraday.sqlite3')
            cache.put({
                'instrument': 'SHARE1', 'source': 'IRESS_VIEWPOINT_TABLE_CSV',
                'interval_minutes': 5, 'clock_semantics': 'START',
                'source_timestamp': '2026-11-12T08:00:00+00:00',
                'bar_start': '2026-11-12T08:00:00+00:00',
                'bar_end': '2026-11-12T08:05:00+00:00',
                'received_at': '2026-11-12T08:06:00+00:00',
                'availability': 'MANUAL', 'unit': 'ZAR_CENTS',
                'fields': {'open': '10000', 'high': '10100', 'low': '9900',
                           'close': '10050', 'volume': '10'},
            }, evidence=True)
            report = {'items': [{'headline': f'News {i}', 'source': 'fixture',
                                 'published_at': '2026-11-12T08:00:00+00:00'}
                                for i in range(25)]}
            event = {'source_freshness': 'CURRENT_CAPTURE',
                     'sens_discovery': {'sources': [{'source_id': 'sens1',
                         'headline': 'SENS notice', 'source_url': 'https://example.test/sens',
                         'available_at': NOW.isoformat(),
                         'provenance': {'raw_sha256': 'a' * 64}}]},
                     'calendar_upcoming': [{'record_id': 'event1', 'title': 'MPC',
                                            'source_quote': 'Retained exact citation',
                                            'instrument_ids': ['MTN']}]}
            packet = build_packet(service, reason='VIEWPOINT_CSV_IMPORT', now=NOW,
                                  news_report=report,
                                  news_status={'state': 'AVAILABLE',
                                               'last_success': NOW.isoformat()},
                                  event_status=event, imported_instrument='SHARE1')
            self.assertEqual(len(packet['choices']), 6)
            self.assertEqual(packet['choices'][-1]['instrument'], 'PIN')
            self.assertEqual(packet['choices'][0]['intraday']['available_bars'], 1)
            self.assertEqual(
                packet['choices'][0]['intraday']['bars'][0]['fields']['close']['selected']['selection_policy'],
                'VIEWPOINT_PREFERRED',
            )
            self.assertEqual(packet['choices'][0]['daily_as_of'], NOW.isoformat())
            self.assertEqual(packet['choices'][0]['daily_latest_session'], '2026-11-11')
            self.assertEqual(packet['imported_evidence']['instrument'], 'SHARE1')
            self.assertEqual(len(packet['news']['items']), 20)
            self.assertEqual(packet['sens']['items'][0]['source_id'], 'sens1')
            self.assertEqual(packet['sens']['items'][0]['url'], 'https://example.test/sens')
            self.assertEqual(packet['calendar_events'][0]['record_id'], 'event1')
            self.assertEqual(packet['execution'], {'provider_calls': 0, 'model_calls': 0,
                                                    'backtest_runs': 0, 'live_execution': False})
            saved = PreparedContextStore(service.folder / 'prepared-context.sqlite3')
            receipt = saved.save(packet)
            self.assertEqual(saved.latest()['id'], receipt['id'])
            self.assertEqual(saved.latest()['packet']['trigger'], 'VIEWPOINT_CSV_IMPORT')

    def test_packet_rejects_unknown_triggers_and_naive_clocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp)
            with self.assertRaises(ValueError):
                build_packet(service, reason='PROVIDER_REFRESH', now=NOW)
            with self.assertRaises(ValueError):
                build_packet(service, reason='NEWS_CAPTURE', now=datetime(2026, 11, 12))

    def test_failed_preparation_is_retained_and_reported(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            service = RadarService(tmp, clock=lambda: NOW)
            with patch('dashboard_feeds.feeds.peek_news',
                       return_value={'state': 'NOT_LOADED', 'data': None}):
                with self.assertRaises(ValueError):
                    service.prepare_context('INVALID_TRIGGER', event_status={}, now=NOW)
            result = PreparedContextStore(service.folder / 'prepared-context.sqlite3').latest()
            self.assertEqual(result['state'], 'UNAVAILABLE')
            self.assertEqual(result['packet']['error_type'], 'ValueError')


if __name__ == '__main__':
    unittest.main()
