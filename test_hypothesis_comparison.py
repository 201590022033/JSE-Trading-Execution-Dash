"""Regression coverage for matched hypotheses and isolated ViewPoint requests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask

from application.backtest_lab import hypothesis_comparison as comparison
from application.backtest_lab import intraday_preparation as intraday
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.exact_run_job import EXACT_IDENTITY, RunUnavailable
from application.opportunities.ost_data import atomic_json
from application.strategy_radar import roster


NOW = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
SPEC = dict(instrument='AGL', profiles=[list(EXACT_IDENTITY)], families=['H1', 'H2', 'H5'],
            first_session=None, last_session=None)


class HypothesisComparisonTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.service = SimpleNamespace(root=Path(self.folder.name), folder=Path(self.folder.name), clock=lambda: NOW)
        catalog = patch.object(comparison.exact, 'replay_instruments', return_value=[dict(instrument='AGL', symbol='AGL')])
        catalog.start()
        self.addCleanup(catalog.stop)

    def test_mapping_and_validation(self):
        policy = comparison.contract('AGL')
        self.assertEqual(policy['recommended'], 'H2')
        rows = {row['id']: row for row in policy['families']}
        self.assertEqual(rows['H2']['references'], ['ETF_STXRES', 'ZAR_X'])
        self.assertIn('no mapped gold', rows['H6']['reason'])
        self.assertEqual(comparison.validate(SPEC, self.service), SPEC)
        for dates in [
            ('2026-11-27', '2026-11-27'), ('2026-11-26', '2026-11-25'), ('2026-11-25', None),
        ]:
            with self.subTest(dates=dates), self.assertRaises(RunUnavailable):
                comparison.validate(dict(SPEC, first_session=dates[0], last_session=dates[1]), self.service)
        self.assertEqual(comparison.validate(dict(SPEC, first_session='2026-11-26',
                                                   last_session='2026-11-26'), self.service)['last_session'],
                         '2026-11-26')

    def test_sources_prefer_iress_and_preserve_the_other_fields(self):
        primary = dict(source='IRESS', value=12, acquired_at='2026-11-26T23:00:00+00:00',
                       received_at='2026-11-26T23:05:00+00:00', source_sha256='b' * 64)
        previous = dict(source='YAHOO', value=13, acquired_at='2026-11-26T22:00:00+00:00',
                        source_sha256='a' * 64, state='THREE_PROVIDER_AGREEMENT', alternatives=[primary])
        items = {'AGL': {'rows': [dict(close=13, fields={'close': previous})]}}
        row = comparison._iress_first(items)['AGL']['rows'][0]
        self.assertEqual(row['close'], 12)
        self.assertEqual(row['fields']['close']['received_at'], primary['received_at'])
        self.assertEqual(row['fields']['close']['alternatives'][0]['source'], 'YAHOO')
        self.assertEqual(row['fields']['close']['state'], 'CONFLICT_NO_CONSENSUS')

    def test_missing_family_does_not_prevent_supported_cells(self):
        days = [(NOW.date() - timedelta(days=i)).isoformat() for i in range(190, 0, -1)]
        bars = [dict(timestamp=day, _source='IRESS', open=10, high=11, low=9, close=10, volume=10) for day in days]
        instruments = {'AGL': {'rows': [], 'asset_class': 'cash_equity'}}
        assignments = {day: {'instrument': 'ETF_STX40', 'label': 'STX40'} for day in days}
        with (patch.object(comparison, 'load_zebra_screen_data', return_value={'instruments': instruments}),
              patch.object(comparison, '_benchmark_inputs', return_value=(assignments, {})),
              patch.object(comparison.exact, '_inputs', return_value=(bars, {d: {} for d in days}, set()))):
            plan, _ = comparison.prepare(self.service, SPEC)
        states = {cell['family']: cell for cell in plan['cells']}
        self.assertGreater(plan['qualified_sessions'], 0)
        self.assertEqual(states['H1']['state'], 'READY')
        self.assertIn('ETF_STXRES, ZAR_X', states['H2']['reason'])
        self.assertIn('macro-impulse runner', states['H5']['reason'])

    def test_context_uses_prior_observations_and_blocks_a_failed_gate(self):
        days = [f'2026-11-{i:02}' for i in range(1, 10)]
        series = {day: float(i + 1) for i, day in enumerate(days)}
        earlier = comparison._prior_returns(series, ['2026-11-08'])
        self.assertEqual(earlier['2026-11-08']['last'], '2026-11-07')
        failed = {'2026-11-08': {**earlier['2026-11-08'], 'return': -0.1}}
        result = comparison._context('H2', {'references': ['ETF_STXRES', 'ZAR_X']}, '2026-11-08',
                                     {'ETF_STXRES': earlier, 'ZAR_X': failed})
        self.assertFalse(result['ok'])
        self.assertIn('ZAR_X -10.00%', result['v'])

    def test_gold_and_telecom_contracts_use_their_own_references(self):
        self.assertEqual(comparison.references('H6', 'GFI'), ('GC_F', 'ZAR_X'))
        self.assertEqual(comparison.references('H7', 'MTN'), ('VOD',))
        day = '2026-11-10'
        result = comparison._context('H6', {}, day, {
            'GOLD_ALIGNED': {day: {'return': 0.02}},
            'GOLD_ZAR_ALIGNED': {day: {'return': -0.01}},
        })
        self.assertFalse(result['ok'])
        result = comparison._context('H7', {'references': ['VOD']}, day, {'VOD': {day: {'return': 0.01}}})
        self.assertTrue(result['ok'])

    def test_reference_hole_splits_an_older_observed_window(self):
        observed = ['2025-11-03', '2025-11-04', '2025-11-05']
        self.assertEqual(comparison._segments([observed[0], observed[2]], observed),
                         [[observed[0]], [observed[2]]])

    def test_comparison_job_deduplicates_the_same_preview(self):
        with self.assertRaisesRegex(RunUnavailable, 'Review the retained data'):
            roster.enqueue_exact(self.service, SPEC)
        request = dict(SPEC, preview_id='a' * 64)
        first = roster.enqueue_exact(self.service, request)
        second = roster.enqueue_exact(self.service, dict(request, families=['H5', 'H2', 'H1']))
        self.assertEqual(first, second)
        self.assertEqual(roster.exact_status(self.service, first)['state'], 'QUEUED')
        self.assertNotEqual(first, roster.enqueue_exact(self.service, dict(request, preview_id='b' * 64)))
        with (patch.dict('os.environ', {'LOCAL_BACKTEST_REPORT_DIR': str(self.service.folder)}),
              patch.object(comparison, 'prepare', return_value=({'preview_id': 'c' * 64}, None)),
              self.assertRaisesRegex(RunUnavailable, 'changed after review')):
            comparison.run_job(self.service, request)

    def test_fake_queue_receipts_and_actual_coverage_gate(self):
        target = intraday.target(self.service, 'AGL', '2026-11-26')
        past = intraday.target(self.service, 'AGL', '2026-11-25')
        queue = self.service.folder / 'viewpoint-requests'
        queue.mkdir()
        (queue / 'heartbeat').write_text(str(monotonic()), encoding='utf-8')
        pending, receipt, progress = intraday._paths(self.service, target)
        rows = []

        def read(*_):
            return rows

        self.assertEqual(intraday.submit(self.service, past, read_records=read)['state'],
                         'UNSUPPORTED_HISTORICAL_WINDOW')
        self.assertFalse(pending.exists())
        for _ in range(2):
            self.assertEqual(intraday.submit(self.service, target, read_records=read)['state'], 'PENDING_DOWNLOAD')
        self.assertEqual(len(list(queue.glob('*.json'))), 1)
        for stage in ('DOWNLOADING', 'IMPORTING'):
            atomic_json(progress, {'state': stage})
            self.assertEqual(intraday.status(self.service, target, read_records=read)['state'], stage)
        atomic_json(receipt, {'state': 'OST_SIGN_IN_OR_CHART_SETUP_REQUIRED'})
        self.assertEqual(intraday.status(self.service, target, read_records=read)['state'], 'SIGN_IN_REQUIRED')
        self.assertEqual(intraday.submit(self.service, target, retry=True, read_records=read)['state'], 'PENDING_DOWNLOAD')
        atomic_json(receipt, {'state': 'CHECKED', 'instruments': {'AGL': 'IMPORTED'}})
        self.assertEqual(intraday.status(self.service, target, read_records=read)['state'], 'PARTIAL_EXPORT')
        start = datetime(2026, 11, 26, 7, tzinfo=timezone.utc)
        for index in range(96):
            bar_start = start + timedelta(minutes=5 * index)
            rows.append(dict(instrument='AGL', source=intraday.VIEWPOINT_SOURCE, interval_minutes=5,
                             clock_semantics='START', availability='HISTORICAL', unit='ZAR',
                             source_timestamp=bar_start.isoformat(), bar_start=bar_start.isoformat(),
                             bar_end=(bar_start + timedelta(minutes=5)).isoformat(), received_at=NOW.isoformat(),
                             fields=dict(open=10, high=11, low=9, close=10, volume=100)))
        self.assertEqual(intraday.status(self.service, target, read_records=read)['state'], 'READY')

    def test_manual_export_validates_identity_interval_and_coverage_before_write(self):
        target = intraday.target(self.service, 'AGL', '2026-11-26')
        filename = 'AGL.JSE (20261126070000000 _ 20261127070000000).csv'
        rows = b'Date,Open,High,Low,Close,Volume\n2026-11-26T07:00:00Z,1000,1100,900,1050,100\n'
        raw = rows + b'2026-11-26T07:05:00Z,1000,1100,900,1050,100\n'
        with self.assertRaisesRegex(RunUnavailable, 'native ViewPoint export filename'):
            intraday.manual(self.service, target, raw, filename.replace('AGL', 'BHP'), save=False)
        with self.assertRaisesRegex(RunUnavailable, 'consecutive five-minute'):
            intraday.manual(self.service, target, raw.replace(b'07:05', b'07:30'), filename, save=False)
        preview = intraday.manual(self.service, target, raw, filename, save=False)
        self.assertEqual(preview['validated_bars'], 2)
        self.assertFalse((self.service.folder / 'intraday.sqlite3').exists())
        stored = intraday.manual(self.service, target, raw, filename, save=True)
        self.assertEqual(stored['state'], 'PARTIAL_EXPORT')
        self.assertEqual(stored['imported_bars'], 2)

    def test_daily_export_preview_checks_native_symbol_without_writing(self):
        app = Flask(__name__)
        app.register_blueprint(create_backtest_lab_blueprint(self.service.folder, radar_factory=lambda: self.service))
        client = app.test_client()
        url = '/api/v1/backtest-lab/daily-export-preview'
        packet = dict(provider='IRESS', instrument_id='AGL', origin_symbol='AGL.JSE',
                      acquired_at=NOW.isoformat(), instrument_confirmed=True,
                      csv='Date,Open,High,Low,Close,Volume\n26/11/2026,1000,1100,900,1050,100\n')
        headers = {'Origin': 'http://localhost'}
        rejected = client.post(url, json={**packet, 'origin_symbol': 'BHP.JSE'}, headers=headers)
        self.assertEqual(rejected.status_code, 422)
        result = client.post(url, json=packet, headers=headers)
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['sessions'], ['2026-11-26'])
        self.assertEqual(list(self.service.folder.iterdir()), [])
