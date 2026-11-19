"""Collector regressions without broker access or a signed-in browser."""
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
from types import SimpleNamespace
from contextlib import closing
import json
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from application.strategy_radar import viewpoint_collector as collector


class DownloadEvent:
    """Model an event that can arrive even when the click times out."""
    def __init__(self, download=None):
        self.download = download

    @property
    def value(self):
        if self.download is None:
            raise PlaywrightTimeoutError('No download event arrived')
        return self.download

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.value
        return False


class ViewPointCollectorTests(unittest.TestCase):
    def test_setup_enables_browser_sandbox(self):
        with TemporaryDirectory() as folder:
            service = SimpleNamespace(folder=Path(folder))
            playwright = MagicMock()
            browser = playwright.__enter__.return_value
            context = browser.chromium.launch_persistent_context.return_value
            context.pages = [MagicMock()]
            with patch('application.strategy_radar.service.RadarService', return_value=service), \
                    patch('playwright.sync_api.sync_playwright', return_value=playwright), \
                    patch.object(collector, 'process_lock'), \
                    patch.object(collector, '_wait_for_ost_launch', return_value=False), \
                    patch('builtins.print'):
                self.assertEqual(collector.setup(), 1)
            self.assertTrue(browser.chromium.launch_persistent_context.call_args.kwargs['chromium_sandbox'])
            context.close.assert_called_once_with()

    def test_normal_activation_does_not_send_duplicate_keyboard_input(self):
        control = MagicMock()
        collector._activate(control)
        control.click.assert_called_once_with(no_wait_after=True)
        control.focus.assert_not_called()
        control.press.assert_not_called()

    def test_click_timeout_falls_back_to_focused_keyboard_activation(self):
        control = MagicMock()
        control.click.side_effect = PlaywrightTimeoutError('Click timed out')
        collector._activate(control, key='Space')
        control.focus.assert_called_once_with()
        control.press.assert_called_once_with('Space', no_wait_after=True)

    def test_download_event_survives_click_timeout_without_second_activation(self):
        page, dialog = MagicMock(), MagicMock()
        download = MagicMock()
        page.expect_download.return_value = DownloadEvent(download)
        button = dialog.get_by_role.return_value
        button.click.side_effect = PlaywrightTimeoutError('Navigation wait timed out')

        self.assertIs(collector._download_table(page, dialog), download)
        button.press.assert_not_called()
        self.assertEqual(page.expect_download.call_count, 1)

    def test_missing_download_uses_one_keyboard_retry(self):
        page, dialog = MagicMock(), MagicMock()
        download = MagicMock()
        page.expect_download.side_effect = [DownloadEvent(), DownloadEvent(download)]
        button = dialog.get_by_role.return_value
        button.click.side_effect = PlaywrightTimeoutError('Click timed out')

        self.assertIs(collector._download_table(page, dialog), download)
        button.focus.assert_called_once_with()
        button.press.assert_called_once_with('Enter', no_wait_after=True)
        self.assertEqual(page.expect_download.call_count, 2)

    def test_absent_download_fails_instead_of_claiming_an_export(self):
        page, dialog = MagicMock(), MagicMock()
        page.expect_download.side_effect = [DownloadEvent(), DownloadEvent()]
        dialog.get_by_role.return_value.click.side_effect = PlaywrightTimeoutError('Click timed out')

        with self.assertRaises(PlaywrightTimeoutError):
            collector._download_table(page, dialog)
        self.assertEqual(page.expect_download.call_count, 2)

    def export_page(self):
        page, dialog, chart = MagicMock(), MagicMock(), MagicMock()
        dialog.is_visible.return_value = False
        dialog.get_by_role.return_value.count.return_value = 1
        chart.is_visible.return_value = True

        def role(role_name, **kwargs):
            if role_name == 'dialog':
                return dialog
            if role_name == 'img':
                return chart
            return MagicMock()

        page.get_by_role.side_effect = role
        return page

    def test_native_filename_and_guid_storage_path_preserve_csv_bytes(self):
        with TemporaryDirectory() as folder:
            artifact = Path(folder) / '85409101-01d5-424d-846a-0d7bde804e8d'
            raw = b'"Date","Open","High","Low","Close","Volume"\n'
            artifact.write_bytes(raw)
            download = MagicMock()
            download.suggested_filename = 'MTN.JSE (20261113171000000 _ 20261112105000000).csv'
            download.path.return_value = artifact
            with patch.object(collector, '_download_table', return_value=download):
                name, retained = collector._export(self.export_page(), 'MTN.JSE')
            self.assertEqual(name, download.suggested_filename)
            self.assertEqual(retained, raw)

    def test_export_rejects_another_symbols_native_filename(self):
        download = MagicMock()
        download.suggested_filename = 'VOD.JSE (20261113171000000 _ 20261112105000000).csv'
        with patch.object(collector, '_download_table', return_value=download):
            with self.assertRaises(collector.ExportFailure) as raised:
                collector._export(self.export_page(), 'MTN.JSE')
        self.assertEqual(raised.exception.detail['stage'], 'verify native filename')
        download.path.assert_not_called()

    def test_successful_collection_retains_raw_bytes_and_native_lineage(self):
        raw = (b'"Date","Open","High","Low","Close","Volume"\n'
               b'"2026-11-13T14:40:00.000Z","23450","23460","23440","23455","12345"\n')
        name = 'MTN.JSE (20261113164000000 _ 20261113164000000).csv'
        with TemporaryDirectory() as folder:
            service = SimpleNamespace(folder=Path(folder) / 'strategy-radar')
            subject = collector.ViewPointCollector(service)
            with patch.object(collector, 'mappings', return_value={'MTN': 'MTN'}), \
                    patch.object(collector, '_export', return_value=(name, raw)):
                result = subject.export_watches(self.export_page(), [{'instrument': 'MTN'}])
                repeated = subject.export_watches(self.export_page(), [{'instrument': 'MTN'}])
            rows = collector.IntradayCache(service.folder / 'intraday.sqlite3').read('MTN')
            self.assertEqual(result['instruments'], {'MTN': 'IMPORTED'})
            self.assertEqual(repeated['instruments'], {'MTN': 'ALREADY_RETAINED'})
            self.assertEqual(len(rows), 1)
            digest = sha256(raw).hexdigest()
            self.assertEqual(rows[0]['source_raw_sha256'], digest)
            self.assertEqual(rows[0]['interval_minutes'], 5)
            self.assertEqual(rows[0]['fields']['volume'], '12345')
            self.assertEqual(json.loads(rows[0]['raw_payload'])['file_name'], name)
            self.assertEqual(result['evidence']['MTN']['sha256'], digest)
            self.assertEqual(repeated['evidence']['MTN']['received_at'], result['evidence']['MTN']['received_at'])
            self.assertEqual(result['evidence']['MTN']['latest_bar_end'], '2026-11-13T14:45:00+00:00')
            with closing(sqlite3.connect(service.folder / 'intraday.sqlite3')) as database:
                self.assertEqual(database.execute('SELECT data FROM raw_responses WHERE digest=?',
                                                 (digest,)).fetchone()[0], raw)

    def test_same_export_promotes_only_newly_completed_bar(self):
        from datetime import datetime, timezone

        raw = (b'Date,Open,High,Low,Close,Volume\n'
               b'2026-11-13T14:40:00.000Z,23450,23460,23440,23455,12345\n'
               b'2026-11-13T14:45:00.000Z,23455,23465,23440,23460,12345\n')
        name = 'MTN.JSE (20261113164500000 _ 20261113164000000).csv'
        with TemporaryDirectory() as folder:
            subject = collector.ViewPointCollector(SimpleNamespace(folder=Path(folder)))
            with patch.object(collector, 'mappings', return_value={'MTN': 'MTN'}), \
                    patch.object(collector, '_export', return_value=(name, raw)), \
                    patch.object(collector, 'datetime') as clock:
                clock.now.side_effect = [datetime(2026, 11, 13, 14, minute, tzinfo=timezone.utc)
                                         for minute in (46, 51, 51)]
                for expected in ('IMPORTED', 'IMPORTED', 'ALREADY_RETAINED'):
                    result = subject.export_watches(self.export_page(), [{'instrument': 'MTN'}])
                    self.assertEqual(result['instruments']['MTN'], expected)
            rows = collector.IntradayCache(subject.service.folder / 'intraday.sqlite3').read('MTN')
            self.assertEqual(len(rows), 3)
            self.assertEqual(sum(not row['provisional'] for row in rows), 2)

    def test_retention_failure_does_not_prevent_benchmark_collection(self):
        raw = (b'"Date","Open","High","Low","Close","Volume"\n'
               b'"2026-11-13T14:40:00.000Z","23450","23460","23440","23455","12345"\n')
        with TemporaryDirectory() as folder:
            subject = collector.ViewPointCollector(SimpleNamespace(folder=Path(folder)))
            cache = MagicMock()
            cache.read.return_value = []
            cache.put_batch.side_effect = [sqlite3.OperationalError('database is locked'), ['retained']]
            def export(page, symbol):
                return f'{symbol} (20261113164000000 _ 20261113164000000).csv', raw
            with patch.object(collector, 'mappings', return_value={'MTN': 'MTN', 'ETF_STX40': 'STX40'}), \
                    patch.object(collector, '_export', side_effect=export), \
                    patch.object(collector, 'IntradayCache', return_value=cache), \
                    patch('builtins.print'):
                result = subject.export_watches(self.export_page(),
                    [{'instrument': 'MTN', 'benchmark': 'ETF_STX40'}])
            self.assertEqual(result['state'], 'CHECKED')
            self.assertEqual(result['instruments'], {'MTN': 'EXPORT_UNAVAILABLE', 'ETF_STX40': 'IMPORTED'})
            self.assertEqual(result['errors']['MTN']['stage'], 'retain evidence')
            self.assertEqual(result['errors']['MTN']['error'], 'OperationalError')
            self.assertEqual(cache.put_batch.call_count, 2)

    def collect_responses(self, responses):
        """Run the actual queue client against immediate local fake responses."""
        requests = []
        with TemporaryDirectory() as folder:
            subject = collector.ViewPointCollector(SimpleNamespace(folder=Path(folder)))
            subject.profile.mkdir()
            (subject.profile / 'Local State').write_text('{}', encoding='utf-8')
            queue = Path(folder) / 'viewpoint-requests'
            queue.mkdir()
            (queue / 'heartbeat').write_text('1000', encoding='utf-8')
            pending = iter(responses)

            def deliver(path, payload):
                requests.append(payload['watches'])
                path.write_text(json.dumps(payload), encoding='utf-8')
                path.with_suffix('.result').write_text(json.dumps(next(pending)), encoding='utf-8')

            with patch.object(collector, 'monotonic', return_value=1000), \
                    patch.object(collector, 'atomic_json', side_effect=deliver), \
                    patch.object(collector, 'sleep') as wait:
                result = subject.collect([{'instrument': 'MTN', 'benchmark': 'ETF_STX40'}])
            wait.assert_not_called()
            self.assertEqual([path.name for path in queue.iterdir()], ['heartbeat'])
        return result, requests

    def test_symbol_timeout_retries_only_failed_benchmark_and_preserves_success(self):
        first = {'state': 'CHECKED',
                 'instruments': {'MTN': 'IMPORTED', 'ETF_STX40': 'EXPORT_UNAVAILABLE'},
                 'errors': {'ETF_STX40': {'stage': 'verify five minute symbol', 'error': 'TimeoutError'}},
                 'evidence': {'MTN': {'sha256': 'mtn-hash'}}}
        second = {'state': 'CHECKED', 'instruments': {'ETF_STX40': 'IMPORTED'},
                  'errors': {}, 'evidence': {'ETF_STX40': {'sha256': 'benchmark-hash'}}}
        result, requests = self.collect_responses([first, second])
        self.assertEqual(requests, [[{'instrument': 'MTN', 'benchmark': 'ETF_STX40'}],
                                    [{'instrument': 'ETF_STX40'}]])
        self.assertEqual(result['instruments'], {'MTN': 'IMPORTED', 'ETF_STX40': 'IMPORTED'})
        self.assertEqual(result['evidence'], {'MTN': {'sha256': 'mtn-hash'},
                                              'ETF_STX40': {'sha256': 'benchmark-hash'}})
        self.assertEqual(result['errors'], {})
        self.assertEqual(result['attempts'], [first, second])

    def test_download_and_database_failures_do_not_retry(self):
        for stage, error in [('download table', 'TimeoutError'), ('retain evidence', 'OperationalError')]:
            with self.subTest(stage=stage):
                first = {'state': 'CHECKED', 'instruments': {'MTN': 'EXPORT_UNAVAILABLE'},
                         'errors': {'MTN': {'stage': stage, 'error': error}}, 'evidence': {}}
                result, requests = self.collect_responses([first])
                self.assertEqual(result, first)
                self.assertEqual(len(requests), 1)

    def test_failed_symbol_retry_retains_first_error_evidence_and_cleans_queue(self):
        first = {'state': 'CHECKED',
                 'instruments': {'MTN': 'IMPORTED', 'ETF_STX40': 'EXPORT_UNAVAILABLE'},
                 'errors': {'ETF_STX40': {'stage': 'verify five minute symbol', 'error': 'TimeoutError'}},
                 'evidence': {'MTN': {'sha256': 'mtn-hash'}}}
        second = {'state': 'COLLECTOR_TIMEOUT', 'instruments': {}}
        result, requests = self.collect_responses([first, second])
        self.assertEqual(len(requests), 2)
        self.assertEqual(result['retry_state'], 'COLLECTOR_TIMEOUT')
        self.assertEqual(result['instruments'], first['instruments'])
        self.assertEqual(result['evidence'], first['evidence'])
        self.assertEqual(result['errors'], first['errors'])
        self.assertEqual(result['attempts'], [first, second])

    def test_multiple_symbol_failures_recover_sequentially_after_reselect_timeout(self):
        symbol_error = {'stage': 'verify five minute symbol', 'error': 'TimeoutError'}
        first = {'state': 'CHECKED',
                 'instruments': {'MTN': 'EXPORT_UNAVAILABLE', 'ETF_STX40': 'EXPORT_UNAVAILABLE'},
                 'errors': {'MTN': symbol_error, 'ETF_STX40': symbol_error}, 'evidence': {}}
        reselect = {'state': 'CHECKED', 'instruments': {'MTN': 'EXPORT_UNAVAILABLE'},
                    'errors': {'MTN': symbol_error}, 'evidence': {}}
        mtn = {'state': 'CHECKED', 'instruments': {'MTN': 'IMPORTED'},
               'errors': {}, 'evidence': {'MTN': {'sha256': 'mtn-hash'}}}
        benchmark = {'state': 'CHECKED', 'instruments': {'ETF_STX40': 'ALREADY_RETAINED'},
                     'errors': {}, 'evidence': {'ETF_STX40': {'sha256': 'benchmark-hash'}}}

        result, requests = self.collect_responses([first, reselect, mtn, benchmark])
        self.assertEqual(requests, [[{'instrument': 'MTN', 'benchmark': 'ETF_STX40'}],
                                    [{'instrument': 'MTN'}], [{'instrument': 'MTN'}],
                                    [{'instrument': 'ETF_STX40'}]])
        self.assertEqual(result['instruments'], {'MTN': 'IMPORTED', 'ETF_STX40': 'ALREADY_RETAINED'})
        self.assertEqual(result['errors'], {})
        self.assertEqual(result['evidence'], {'MTN': {'sha256': 'mtn-hash'},
                                              'ETF_STX40': {'sha256': 'benchmark-hash'}})
        self.assertEqual(result['attempts'], [first, reselect, mtn, benchmark])


if __name__ == '__main__':
    unittest.main()
