"""Offline restore gating and exact local dataset continuity checks."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.local_runtime import configuration, execute, process_lock, worker_ready, verify_database
import test_iress_research_routing as routing_fixture
from persistence.sqlite_repository import SQLiteRepository
from application.opportunities.swing_research import latest_dataset


class LocalRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture = routing_fixture.IRESSRoutingTests()
        fixture.setUp()
        self.payload, self.now = fixture.payload, fixture.now
        self.env = {'DATABASE_URL': 'postgresql://user:private@127.0.0.1:5432/restored',
                    'SWING_DATA_SOURCE': 'LOCAL_UPLOAD', 'SWING_LEARNING_SOURCE': 'LOCAL',
                    'SWING_RESEARCH_ENABLED': '0', 'PAPER_NEWS_ENABLED': '0',
                    'ALPHA_VANTAGE_ENABLED': '0', 'PAPER_IG_SWING_DIAGNOSTICS': '0',
                    'IG_STREAM_ENABLED': '0'}
        self.receipt = {'schema': 'local-restore-acceptance-v1', 'state': 'ACCEPTED',
            'database_identity': {'host': '127.0.0.1', 'port': 5432, 'database': 'restored'},
            'verified_at': self.now.isoformat(), 'source_backup_sha256': 'a'*64,
            'reconciliation_sha256': 'b'*64}

    def bootstrap_receipt(self):
        return {'schema': 'local-bootstrap-acceptance-v1', 'state': 'ACCEPTED',
            'operation': 'FRESH_START', 'database_identity': self.receipt['database_identity'],
            'verified_at': self.now.isoformat(), 'owner_reset_authorized': True,
            'baseline_commit': '07c8e29', 'initialization_manifest_sha256': 'c'*64,
            'account_id': 'local-paper-zar-20261015'}

    def test_explicit_fresh_bootstrap_is_separate_from_restoration(self):
        receipt = self.bootstrap_receipt()
        configuration(self.env, receipt, self.now)
        for change in ({'owner_reset_authorized': False}, {'operation': 'RESTORE'},
                       {'account_id': 'paper-zar-railway'}, {'baseline_commit': 'invalid'},
                       {'initialization_manifest_sha256': 'bad'},
                       {'source_backup_sha256': 'a'*64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                configuration(self.env, {**receipt, **change}, self.now)

    def test_fresh_worker_cannot_use_hosted_account_configuration(self):
        repository, runner = Mock(), Mock()
        with patch('scripts.local_runtime.verify_database'), patch(
                'application.opportunities.paper_host.configured_paper',
                return_value=SimpleNamespace(mode='PAPER', account_id='hosted-account')):
            with self.assertRaises(ValueError):
                execute('worker', self.env, self.bootstrap_receipt(), now=self.now,
                        factory=lambda **_: repository, runner=runner)
        runner.assert_not_called()
        repository.paper_account.assert_not_called()

    def test_fresh_lane_rejects_each_inherited_or_missing_external_switch(self):
        for key in ('SWING_RESEARCH_ENABLED', 'PAPER_NEWS_ENABLED', 'ALPHA_VANTAGE_ENABLED',
                    'PAPER_IG_SWING_DIAGNOSTICS', 'IG_STREAM_ENABLED'):
            for value in ('1', '', 'true'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    configuration({**self.env, key: value}, self.bootstrap_receipt(), self.now)
            missing = dict(self.env)
            missing.pop(key)
            with self.subTest(key=key, missing=True), self.assertRaises(ValueError):
                configuration(missing, self.bootstrap_receipt(), self.now)

    def test_configuration_rejects_remote_sqlite_missing_receipt_and_identity(self):
        for url in ('sqlite:///test.db', '', 'postgresql://user:pw@remote.example/db',
                    'postgresql://user:pw@127.0.0.1/db?host=remote.example'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                configuration({**self.env, 'DATABASE_URL': url}, self.receipt, self.now)
        for change in ({'state': 'PENDING'}, {'database_identity': {}},
                       {'verified_at': (self.now+timedelta(seconds=1)).isoformat()},
                       {'source_backup_sha256': 'bad'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                configuration(self.env, {**self.receipt, **change}, self.now)

    def test_no_repository_before_restore_acceptance_or_actual_identity(self):
        factory = Mock()
        with self.assertRaises(ValueError):
            execute('ingest', self.env, {}, payload=self.payload, now=self.now, factory=factory)
        with patch('scripts.local_runtime.verify_database', side_effect=ValueError('wrong database')):
            with self.assertRaises(ValueError):
                execute('ingest', self.env, self.receipt, payload=self.payload, now=self.now, factory=factory)
        factory.assert_not_called()

    def test_actual_postgres_identity_and_version_checked_read_only(self):
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        connection.cursor.return_value = cursor
        identity = self.receipt['database_identity']
        with patch('psycopg.connect', return_value=connection):
            for row in [('restored', '127.0.0.1', 5432, 180000),
                        ('wrong', '127.0.0.1', 5432, 180000),
                        ('restored', '10.0.0.1', 5432, 180000),
                        ('restored', '127.0.0.1', 5433, 180000),
                        ('restored', '127.0.0.1', 5432, 170000)]:
                cursor.fetchone.return_value = row
                if row == ('restored', '127.0.0.1', 5432, 180000):
                    verify_database(self.env['DATABASE_URL'], identity)
                else:
                    with self.subTest(row=row), self.assertRaises(ValueError):
                        verify_database(self.env['DATABASE_URL'], identity)
        self.assertEqual(cursor.execute.call_args_list[0].args[0], 'SET TRANSACTION READ ONLY')
        self.assertIn('host(inet_server_addr())', cursor.execute.call_args_list[1].args[0])
        self.assertNotIn('inet_server_addr()::text', cursor.execute.call_args_list[1].args[0])

    def test_ingress_preserves_canonical_and_whole_source_open_idempotently(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'fixture.sqlite'
            factory = lambda **_: SQLiteRepository(path)
            with patch('scripts.local_runtime.verify_database'):
                first = execute('ingest', self.env, self.receipt, payload=self.payload, now=self.now, factory=factory)
                second = execute('ingest', self.env, self.receipt, payload=self.payload, now=self.now, factory=factory)
            self.assertEqual(first['dataset_id'], second['dataset_id'])
            repository = SQLiteRepository(path)
            try:
                result = latest_dataset(repository)
                self.assertIsNone(result['charts']['SASOL']['bars'][-1]['open'])
                self.assertEqual(result['research_charts']['SASOL']['bars'][-1]['open'], 259)
                self.assertEqual(result['research_charts']['SASOL']['provenance'],
                                 self.payload['research_charts']['SASOL']['provenance'])
            finally:
                repository.close()

    def test_worker_blocks_stale_missing_open_and_misaligned_inputs(self):
        worker_ready(self.payload, self.now)
        with self.assertRaises(ValueError):
            worker_ready(self.payload, self.now+timedelta(days=5))
        for mutate in ('open', 'benchmark', 'research'):
            payload = deepcopy(self.payload)
            if mutate == 'open': payload['research_charts']['SASOL']['bars'][-1]['open'] = None
            if mutate == 'benchmark': payload['charts']['ETF_STX40']['bars'].pop()
            if mutate == 'research': payload.pop('research_charts')
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                worker_ready(payload, self.now)

    def test_worker_never_creates_new_paper_account(self):
        repository, runner = Mock(), Mock()
        repository.paper_account.return_value = None
        with patch('scripts.local_runtime.verify_database'), patch(
                'application.opportunities.paper_host.configured_paper',
                return_value=SimpleNamespace(mode='PAPER', account_id='existing')):
            with self.assertRaises(ValueError):
                execute('worker', self.env, self.receipt, now=self.now,
                        factory=lambda **_: repository, runner=runner)
        runner.assert_not_called()
        repository.close.assert_called_once()

    def test_accepted_worker_delegates_existing_bounded_runner_only(self):
        repository, runner = Mock(), Mock()
        repository.paper_account.return_value = {'mode': 'PAPER'}
        with patch('scripts.local_runtime.verify_database'), patch(
                'application.opportunities.paper_host.configured_paper',
                return_value=SimpleNamespace(mode='PAPER', account_id='existing')), patch(
                'application.opportunities.swing_research.latest_dataset', return_value=self.payload):
            result = execute('worker', self.env, self.receipt, now=self.now,
                             factory=lambda **_: repository, runner=runner)
        self.assertFalse(result['live_execution'])
        runner.assert_called_once_with(repository=repository, scheduled=True)
        repository.close.assert_called_once()

    def test_process_lock_excludes_overlap_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'lock'
            with process_lock(path):
                with self.assertRaises(OSError):
                    with process_lock(path): pass
            with process_lock(path): pass


if __name__ == '__main__':
    unittest.main()
