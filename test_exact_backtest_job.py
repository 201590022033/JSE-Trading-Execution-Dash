"""B03 fixture coverage for local submission, roster replay and verified results."""
from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flask import Flask

from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab import exact_run_job
from application.opportunities.session_freshness import next_session
from application.strategy_radar.roster import run_lane


URL = '/api/v1/backtest-lab/jobs'
REFERENCE = 'CONSTRUCTED_TELECOMMUNICATIONS_EX_MTN'


def observations(count):
    rows = []
    session = '2026-05-04'
    for index in range(count):
        price = 100 + index / 10
        fields = {
            key: {'value': value, 'state': 'SINGLE_SOURCE', 'source': 'FIXTURE',
                  'source_sha256': 'a' * 64, 'acquired_at': session + 'T19:30:00+02:00'}
            for key, value in {'open': price, 'high': price + 1, 'low': price - 1,
                               'close': price + .1, 'volume': 100000 + index}.items()
        }
        rows.append({'session': session, 'fields': fields, **{key: detail['value'] for key, detail in fields.items()}})
        session = next_session(session)
    return {'rows': rows, 'asset_class': 'cash_equity', 'sector': 'Telecommunications'}


def fixture_policy(instrument, instruments, sessions, *, lookback):
    closes = {row['session']: {'close': row['close']} for row in instruments['VOD']['rows']}
    labels = {session: {'instrument': REFERENCE, 'basis': 'CONSTRUCTED_SECTOR_PROXY',
                        'label': 'Fixture telecom proxy excludes MTN', 'members': ['VOD']} for session in sessions}
    return labels, {REFERENCE: closes}


class ExactBacktestJobTests(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(TemporaryDirectory())
        self.folder = Path(scratch)
        self.service = SimpleNamespace(
            root=self.folder, folder=self.folder / 'roster',
            clock=lambda: datetime(2026, 11, 19, 19, tzinfo=timezone.utc),
        )
        self.service.folder.mkdir()
        app = Flask(__name__)
        app.register_blueprint(create_backtest_lab_blueprint(self.folder, radar_factory=lambda: self.service))
        self.client = app.test_client()
        self.instruments = {key: observations(70) for key in ('MTN', 'VOD')}
        rows = self.instruments['MTN']['rows']
        self.request = dict(
            instrument='MTN', family='H1', strategy_id=exact_run_job.EXACT_IDENTITY[0],
            strategy_version=exact_run_job.EXACT_IDENTITY[1], product='CASH_SHARE', timeframe='1d',
            first_session=rows[0]['session'], last_session=rows[-1]['session'], request_id='test-mtn',
        )
        self.enterContext(patch.object(exact_run_job.benchmarks, 'benchmark_input_keys',
                                      return_value={'MTN', 'VOD'}, create=True))
        self.enterContext(patch.object(exact_run_job.benchmarks, 'research_benchmarks',
                                      side_effect=fixture_policy, create=True))
        self.enterContext(patch.object(exact_run_job, 'load_zebra_screen_data',
                                      return_value={'instruments': self.instruments}))
        self.launch = self.enterContext(patch('application.strategy_radar.roster.start_lane'))
        self.enterContext(patch.dict(os.environ, {'LOCAL_BACKTEST_REPORT_DIR': scratch}))

    def test_mtn_enqueue_poll_replay_publish_and_list(self):
        # Keep the missing Open in source lineage while excluding this session from fills.
        removed = self.instruments['MTN']['rows'][60]
        removed['open'] = None
        removed['fields'].pop('open')
        response = self.client.post(URL, json=self.request)
        self.assertEqual(response.status_code, 202)
        self.launch.assert_called_once_with(self.service, 'backtester')
        job_url = URL + '/' + response.json['job_id']
        self.assertEqual(self.client.get(job_url).json['state'], 'QUEUED')
        original_run_job = exact_run_job.run_job

        def observe_running(service, spec):
            self.assertEqual(self.client.get(job_url).json['state'], 'RUNNING')
            return original_run_job(service, spec)

        with patch.object(exact_run_job, 'run_job', side_effect=observe_running):
            outcome = run_lane(self.service, 'backtester')
        self.assertEqual(outcome['state'], 'COMPLETED', outcome)
        self.assertEqual(self.client.get(job_url).json['state'], 'COMPLETED')
        run_id = outcome['run_id']
        path = self.folder / 'lab' / (run_id + '.json')
        before = path.read_bytes()
        run = self.client.get('/api/v1/backtest-lab/runs/' + run_id).json
        self.assertEqual(run['meta']['data_quality'], 'GAP_TOLERATED')
        self.assertEqual(run['meta']['coverage']['MTN']['observed_sessions'], 69)
        self.assertEqual(run['meta']['coverage']['MTN']['longest_contiguous_sessions'], 60)
        self.assertEqual(run['meta']['sector_benchmarks']['MTN']['instrument'], REFERENCE)
        self.assertTrue(run['meta']['replay_assumptions']['minimum_fee_zar'])
        self.assertIn('SMALL_SAMPLE_FEWER_THAN_30_CLOSED_TRADES', run['meta']['limitations'])
        self.assertFalse(run['live_execution'])
        self.assertEqual(self.client.get('/api/v1/backtest-lab/runs/index').json['runs'][0]['run_id'], run_id)
        self.assertEqual(self.client.post(URL, json=self.request).json['job_id'], response.json['job_id'])
        self.assertEqual(run_lane(self.service, 'backtester')['state'], 'IDLE')
        self.assertEqual(path.read_bytes(), before)

    def test_validates_identity_and_exposes_unavailable_versions(self):
        catalogue = self.client.get(URL).json
        profiles = catalogue['profiles']
        self.assertIn({'instrument': 'SASOL', 'symbol': 'SOL'}, catalogue['instruments'])
        self.assertNotIn('ETF_STX40', {row['instrument'] for row in catalogue['instruments']})
        self.assertEqual({(row['id'], row['version']) for row in profiles if row['available']},
                         exact_run_job.SUPPORTED_IDENTITIES)
        self.assertTrue(all(row['reason'] for row in profiles if not row['available']))
        for replacements, reason in [
            ({'strategy_version': '999'}, 'not registered'),
            ({'product': 'CFD'}, 'no supported cash-share daily replay'),
            ({'timeframe': '5m'}, 'no supported cash-share daily replay'),
            ({'family': 'H2'}, 'H1 selected-share research'),
            ({'last_session': '2027-01-04'}, 'latest completed session'),
            ({'instrument': 'ETF_STX40'}, 'recognized Zebra cash share'),
        ]:
            resp = self.client.post(URL, json={**self.request, **replacements})
            self.assertEqual(resp.status_code, 422, resp.json)
            self.assertIn(reason, resp.json['error'])
        self.assertEqual(self.client.post(URL, json=self.request, headers={'Origin': 'https://example.test'}).status_code, 403)
        self.assertEqual(self.client.post(URL, json=self.request,
                         environ_overrides={'REMOTE_ADDR': '192.0.2.3'}).status_code, 403)
        self.launch.assert_not_called()

    def test_unwatched_sasol_runs_under_the_retained_instrument_identity(self):
        self.instruments['SASOL'] = observations(70)
        history = self.client.get('/api/v1/backtest-lab/replay-history/SASOL')
        self.assertEqual(history.status_code, 200, history.json)
        self.assertEqual(history.json['qualified_sessions'], 70)
        self.assertEqual(history.json['first_session'], self.request['first_session'])
        self.assertEqual(history.json['close_sources'], ['FIXTURE'])
        self.launch.assert_not_called()
        reply = self.client.post(URL, json={**self.request, 'instrument': 'SASOL'})
        self.assertEqual(reply.status_code, 202, reply.json)
        outcome = run_lane(self.service, 'backtester')
        self.assertEqual(outcome['state'], 'COMPLETED', outcome)
        result = self.client.get('/api/v1/backtest-lab/runs/' + outcome['run_id']).json
        self.assertEqual(set(result['meta']['coverage']), {'SASOL'})

    def test_history_preflight_rejects_missing_data_and_non_cash_share(self):
        for share, reason in [('SASOL', 'No eligible retained'), ('ETF_STX40', 'recognized Zebra cash share')]:
            response = self.client.get('/api/v1/backtest-lab/replay-history/' + share)
            self.assertEqual(response.status_code, 422)
            self.assertIn(reason, response.json['error'])
        self.launch.assert_not_called()

    def test_supported_component_and_lab_paths_keep_exact_identities(self):
        for index, identity in enumerate(sorted(exact_run_job.SUPPORTED_IDENTITIES - {exact_run_job.EXACT_IDENTITY})):
            with self.subTest(identity=identity):
                reply = self.client.post(URL, json={**self.request, 'strategy_id': identity[0],
                                                    'strategy_version': identity[1], 'request_id': f'test-{index}'})
                self.assertEqual(reply.status_code, 202, reply.json)
                outcome = run_lane(self.service, 'backtester')
                self.assertEqual(outcome['state'], 'COMPLETED', outcome)
                detail = self.client.get('/api/v1/backtest-lab/runs/' + outcome['run_id'])
                self.assertEqual(detail.status_code, 200)
                result = detail.json['strategies'][0]
                self.assertEqual((result['strategy_profile_id'], result['strategy_profile_version']), identity)
                self.assertEqual(result['timeframe'], '1d')

    def test_explicit_missing_policy_and_worker_failure_are_explained(self):
        with patch.object(exact_run_job.benchmarks, 'research_benchmarks', None):
            entries = self.client.get(URL).json['profiles']
            current = next(row for row in entries if (row['id'], row['version']) == exact_run_job.EXACT_IDENTITY)
            self.assertFalse(current['available'])
            self.assertIn('B04', current['reason'])
            self.assertEqual(self.client.post(URL, json=self.request).status_code, 422)
        job = self.client.post(URL, json=self.request).json['job_id']
        with patch.object(exact_run_job, 'load_zebra_screen_data', return_value={'instruments': {}}):
            outcome = run_lane(self.service, 'backtester')
        self.assertEqual(outcome['state'], 'FAILED')
        self.assertIn('No eligible retained Zebra cash-share history', self.client.get(URL + '/' + job).json['error'])

    def test_range_with_no_qualified_bars_fails_without_saving_a_result(self):
        reply = self.client.post(URL, json={**self.request, 'first_session': '2026-11-02',
                                           'last_session': '2026-11-03'})
        self.assertEqual(reply.status_code, 202, reply.json)
        self.assertEqual(run_lane(self.service, 'backtester')['state'], 'FAILED')
        self.assertIn('No qualified retained daily OHLCV bars',
                      self.client.get(URL + '/' + reply.json['job_id']).json['error'])
        self.assertEqual(list(self.folder.rglob('*.json')), [])
