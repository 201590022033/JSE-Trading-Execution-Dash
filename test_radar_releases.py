"""X3 offline lifecycle, fixed parity and current-source boundary acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'packages/jse_intelligence_core/src'))
from application.release_inbox import ReleaseInbox, StorageError, load_profiles
from application.release_inbox.protocol import canonical, digest
from application.radar_releases import CurrentRadarAdapter, RadarError, RadarReleases
from application.radar_releases.kernel import compute, load_release, model_validate
from jse_intelligence_core import keyword_score, RadarReleaseManifest

FIX = ROOT / 'tests/fixtures/radar_evaluator'
EXPECTED = json.loads((FIX / 'expected.json').read_bytes())
CATALOG = {'JSE:SYNTH_BANK': 'Synthetic Bank'}


def read(path):
    return json.loads(path.read_bytes())


class RadarReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clock = patch('application.radar_releases.service.utc_now', return_value='2026-10-20T12:00:00Z').start()
        self.addCleanup(patch.stopall)
        self.inbox = ReleaseInbox(self.root / 'inbox', load_profiles(FIX / 'profiles.json'), allow_test_profiles=True)
        self.acks = {}
        for name in EXPECTED:
            ack = self.inbox.process(FIX / name)
            self.assertEqual(ack['outcome'], 'IMPORTED_INACTIVE', ack)
            self.acks[name] = ack
        self.service = RadarReleases(self.inbox, self.root / 'journal', issuer_catalog=CATALOG, allow_test_releases=True)
        self.snapshot = read(FIX / 'snapshot.json')

    def review(self, name='attention-v1'):
        return read(FIX / (name + '-review.json'))

    def policy(self):
        return dict(source_id='synthetic:source', enabled=True, admissible=True, observed_at=self.clock.return_value)

    def select(self, name='attention-v1', previous=None, effective='2026-10-20T12:00:00Z', rollback=False):
        self.service.accept(self.review(name))
        return self.service.select(self.acks[name]['package_id'], effective_at=effective,
                                   expected_previous=previous, reason='synthetic fixture selection', rollback=rollback)

    def decision(self, snapshot=None, policy=None, role='attention'):
        return self.service.evaluate(snapshot or self.snapshot, policy or self.policy(), role=role)

    def unavailable(self, code, snapshot=None, policy=None, role='attention'):
        result = self.decision(snapshot, policy, role)
        self.assertEqual((result['outcome'], result['reason_code'], result['score']), ('UNAVAILABLE', code, None))
        self.assertFalse(result['policy_input'])
        self.assertIsNone(result['order_intent'])
        return result

    def test_fixed_transport_and_independent_full_parity_oracles(self):
        for name, expected in EXPECTED.items():
            self.assertEqual(self.acks[name]['package_id'], expected['package_id'])
            self.assertEqual(self.acks[name]['manifest_id'], expected['manifest_id'])
            for path, bh in expected['files'].items():
                self.assertEqual(digest((FIX / name / path).read_bytes()), bh)
            _, manifest, model, _, _ = load_release(self.inbox, expected['package_id'], 'synthetic:model', 'synthetic:parity')
            for case in read(FIX / name / 'artifacts/parity.json')['data']['cases']:
                self.assertEqual(compute(model, manifest.role, case['headline'], case['text']), case['expected'])

    def test_import_and_accept_alone_never_select(self):
        self.assertEqual(self.decision()['outcome'], 'NO_RELEASE')
        acceptance = self.service.accept(self.review())
        self.assertEqual(self.service.accept(self.review()), acceptance)
        self.assertEqual(self.decision()['outcome'], 'NO_RELEASE')
        self.assertEqual(self.inbox.get_release(self.acks['attention-v1']['package_id'])['state'], 'INACTIVE')

    def test_explicit_review_required_and_bound_to_manifest_evidence_and_role(self):
        for change, code in [({'approved': False}, 'REVIEW_REQUIRED'), ({'manifest_id': 'wrong'}, 'REVIEW_IDENTITY_MISMATCH'),
                             ({'evidence_ids': ['wrong']}, 'REVIEW_EVIDENCE_MISMATCH'),
                             ({'criteria': 'directional_outcomes'}, 'WRONG_REVIEW_CRITERIA'),
                             ({'source_ids': []}, 'REVIEW_REQUIRED')]:
            with self.subTest(code=code), self.assertRaisesRegex(RadarError, code):
                self.service.accept({**self.review(), **change})
        self.assertEqual(self.service.events(), [])

    def test_unaccepted_and_backdated_selection_rejected(self):
        with self.assertRaisesRegex(RadarError, 'NOT_ACCEPTED'):
            self.service.select(self.acks['attention-v1']['package_id'], effective_at=self.clock.return_value,
                                expected_previous=None, reason='test')
        self.service.accept(self.review())
        with self.assertRaisesRegex(RadarError, 'BACKDATED_SELECTION'):
            self.service.select(self.acks['attention-v1']['package_id'], effective_at='2026-10-20T11:59:59Z',
                                expected_previous=None, reason='test')

    def test_effective_time_boundary_and_same_snapshot_adapter_parity(self):
        selected = self.select(effective='2026-10-20T12:01:00Z')
        self.assertEqual(self.decision()['outcome'], 'NO_RELEASE')
        self.clock.return_value = '2026-10-20T12:01:00Z'
        direct = self.decision()
        projected = CurrentRadarAdapter(self.service).score_current([self.snapshot], {'synthetic:source': self.policy()})
        batch = projected['items'][0]
        self.assertEqual(direct['selection_id'], selected['event_id'])
        self.assertEqual(direct['score'], EXPECTED['attention-v1']['positive_score'])
        for key in ('snapshot_id', 'manifest_id', 'selection_id', 'score', 'features', 'contributions', 'direction', 'outcome'):
            self.assertEqual(direct[key], batch[key])
        self.assertIsNone(direct['direction'])
        self.assertEqual(direct['weight_origin'], 'fixed')
        self.assertTrue(direct['test_only'])
        self.assertFalse(projected['trading_controls'])
        self.assertFalse(projected['changes_strategy'])

    def test_version_switch_rollback_and_reopen_preserve_prior_feedback(self):
        a = self.select()
        first = self.decision()
        b = self.select('attention-v2', a['event_id'], '2026-10-20T12:01:00Z')
        self.clock.return_value = '2026-10-20T12:01:00Z'
        second = self.decision()
        c = self.select('attention-v1', b['event_id'], '2026-10-20T12:02:00Z', rollback=True)
        self.clock.return_value = '2026-10-20T12:02:00Z'
        third = self.decision()
        self.assertEqual([r['score'] for r in (first, second, third)], [.7, .6, .7])
        self.assertEqual([r['release_version'] for r in (first, second, third)], ['0.1.0', '0.2.0', '0.1.0'])
        self.assertEqual(third['selection_id'], c['event_id'])
        before = self.service.events()
        reopened = RadarReleases(self.inbox, self.root / 'journal', issuer_catalog=CATALOG, allow_test_releases=True)
        self.assertEqual(reopened.events(), before)
        self.assertIn(first, before)
        self.assertEqual(first['snapshot'], self.snapshot)

    def test_compare_and_swap_serializes_competing_selectors(self):
        self.service.accept(self.review())
        def choose(_):
            try:
                return self.service.select(self.acks['attention-v1']['package_id'], effective_at=self.clock.return_value,
                                           expected_previous=None, reason='concurrent fixture')['kind']
            except RadarError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(choose, range(2))), ['SELECT', 'SELECTION_CONFLICT'])

    def test_rollback_requires_previously_selected_target_and_monotonic_time(self):
        a = self.select()
        with self.assertRaisesRegex(RadarError, 'NOT_PRIOR_SELECTION'):
            self.select('attention-v2', a['event_id'], '2026-10-20T12:01:00Z', rollback=True)
        with self.assertRaisesRegex(RadarError, 'NON_MONOTONIC_SELECTION'):
            self.select('attention-v2', a['event_id'])

    def test_selection_freezes_review_even_after_later_review(self):
        self.select()
        later = self.review()
        later.update(review_id='synthetic:later', source_ids=['other:source'])
        self.service.accept(later)
        self.assertEqual(self.decision()['reason_code'], 'SCORED')

    def test_test_only_gate_cannot_be_bypassed_by_reopening_journal(self):
        self.select()
        service = RadarReleases(self.inbox, self.root / 'journal', issuer_catalog=CATALOG)
        with self.assertRaisesRegex(RadarError, 'TEST_RELEASE_DISABLED'):
            service.accept(self.review('attention-v2'))
        self.assertEqual(service.evaluate(self.snapshot, self.policy())['reason_code'], 'TEST_RELEASE_DISABLED')

    def test_directional_is_separate_lane_and_never_policy_or_orders(self):
        self.select('directional-v1')
        self.assertEqual(self.decision()['outcome'], 'NO_RELEASE')
        result = self.decision(role='directional')
        self.assertEqual((result['score'], result['direction'], result['policy_input'], result['order_intent']), (.7, 1, False, None))
        with self.assertRaisesRegex(RadarError, 'POLICY_REQUIRES_STRATEGY_RELEASE'):
            self.decision(role='policy')

    def test_unknown_publication_is_attention_only_and_disclosed(self):
        self.select()
        self.select('directional-v1')
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['evidence']['publication'] = dict(value=None, precision='unknown', timezone_state='unknown', basis='unverified')
        attention = self.decision(snapshot)
        self.assertEqual(attention['publication_precision'], 'unknown')
        self.unavailable('PUBLICATION_TIME_UNAVAILABLE', snapshot, role='directional')

    def test_source_pause_admission_and_fresh_policy_required(self):
        self.select()
        for change, code in [({'enabled': False}, 'SOURCE_DISABLED_OR_INADMISSIBLE'),
                             ({'admissible': False}, 'SOURCE_DISABLED_OR_INADMISSIBLE'),
                             ({'enabled': 1}, 'SOURCE_DISABLED_OR_INADMISSIBLE'),
                             ({'observed_at': '2026-10-20T11:58:59Z'}, 'STALE_SOURCE_POLICY'),
                             ({'observed_at': '2026-10-20T12:00:01Z'}, 'STALE_SOURCE_POLICY')]:
            with self.subTest(change=change):
                self.unavailable(code, policy={**self.policy(), **change})
        projected = CurrentRadarAdapter(self.service).score_current([self.snapshot], {})
        self.assertEqual(projected['items'][0]['reason_code'], 'SOURCE_DISABLED_OR_INADMISSIBLE')

    def test_stale_article_cannot_be_refreshed_by_new_receipt(self):
        self.select()
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['evidence']['publication']['value'] = '2026-10-19T11:59:00Z'
        self.unavailable('STALE_OR_FUTURE_SOURCE', snapshot)
        self.clock.return_value = '2026-10-20T13:01:00Z'
        self.unavailable('STALE_OR_FUTURE_SOURCE')

    def test_scope_horizon_source_and_issuer_guards(self):
        self.select()
        self.assertEqual(self.decision({**self.snapshot, 'scope_id': 'other:scope'})['outcome'], 'NO_RELEASE')
        for field, value, code in [('instrument_id', 'JSE:OTHER', 'OUT_OF_SCOPE'),
                                   ('product_type', 'ssf', 'OUT_OF_SCOPE'), ('horizon', 'sessions_5', 'UNSUPPORTED_HORIZON')]:
            with self.subTest(field=field):
                self.unavailable(code, {**self.snapshot, field: value})
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['evidence']['source_id'] = 'other:source'
        self.unavailable('UNSUPPORTED_SOURCE', snapshot)
        document = canonical(dict(schema_version='radar-inert-data/1', data=dict(headline='Bank sector profits rise', text='')))
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['document'] = document
        snapshot['evidence']['content_hash'] = digest(document.encode())
        self.unavailable('NO_DIRECT_ISSUER_MENTION', snapshot)

    def test_byte_binding_and_malformed_packets_fail_before_feedback(self):
        self.select()
        before = self.service.events()
        for field in ('document', 'source_clock', 'provenance'):
            with self.subTest(field=field), self.assertRaisesRegex(RadarError, 'EVIDENCE_BYTES_MISMATCH'):
                self.decision({**self.snapshot, field: self.snapshot[field] + ' '})
        with self.assertRaises(RadarError):
            CurrentRadarAdapter(self.service).score_current([None], {})
        self.assertEqual(before, self.service.events())

    def test_decision_failure_rolls_back_atomically_and_records_are_immutable(self):
        self.select()
        before = self.service.events()
        original = self.service._insert
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('simulated crash before commit')
        with patch.object(self.service, '_insert', side_effect=fail), self.assertRaisesRegex(RuntimeError, 'simulated crash'):
            self.decision()
        self.assertEqual(before, self.service.events())
        with closing(sqlite3.connect(self.service.path)) as con:
            for statement in ('DELETE FROM records', "UPDATE records SET body='{}'"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'immutable radar event'):
                    con.execute(statement)

    def test_inbox_corruption_fails_closed_without_losing_decision(self):
        self.select()
        with patch.object(self.inbox, 'read_file', side_effect=StorageError('integrity failure')):
            self.unavailable('integrity failure')
        self.assertEqual(self.decision()['reason_code'], 'SCORED')

    def test_model_capabilities_and_parity_rejected_before_acceptance(self):
        import shutil
        for mode, code in [('parity', 'PARITY_MISMATCH'), ('feature', 'UNSUPPORTED_FEATURES'), ('schema', 'UNSUPPORTED_MODEL')]:
            package = self.root / mode
            shutil.copytree(FIX / 'attention-v1', package)
            filename = 'parity.json' if mode == 'parity' else 'model.json'
            data = read(package / 'artifacts' / filename)
            if mode == 'parity':
                data['data']['cases'][0]['expected']['score'] = .99
            elif mode == 'feature':
                data['data']['features'][0]['kind'] = 'executable_pickle'
            else:
                data['data']['schema_version'] = 'future-model/99'
            raw = (canonical(data) + '\n').encode()
            (package / 'artifacts' / filename).write_bytes(raw)
            manifest, envelope = read(package / 'manifest.json'), read(package / 'envelope.json')
            ref = 'synthetic:parity' if mode == 'parity' else 'synthetic:model'
            next(r for r in manifest['content_references'] if r['reference_id'] == ref)['content_hash'] = digest(raw)
            next(r for r in envelope['artifacts'] if r['reference_id'] == ref)['byte_hash'] = digest(raw)
            manifest['release_version'] = {'parity': '1.0.0', 'feature': '2.0.0', 'schema': '3.0.0'}[mode]
            raw = (canonical(manifest) + '\n').encode()
            (package / 'manifest.json').write_bytes(raw)
            mid = RadarReleaseManifest.from_dict(manifest).canonical_id
            envelope['expected_manifest_id'] = mid
            envelope['manifest']['byte_hash'] = digest(raw)
            raw = (canonical(envelope) + '\n').encode()
            (package / 'envelope.json').write_bytes(raw)
            (package / 'COMPLETE.json').write_bytes((canonical(dict(schema_version='radar-inbox-complete/1', envelope_hash=digest(raw))) + '\n').encode())
            ack = self.inbox.process(package)
            self.assertEqual(ack['outcome'], 'IMPORTED_INACTIVE', ack)
            review = {**self.review(), 'package_id': ack['package_id'], 'manifest_id': mid}
            with self.subTest(mode=mode), self.assertRaisesRegex(RadarError, code):
                self.service.accept(review)
        self.assertEqual(self.service.events(), [])

    def test_numeric_limits_nonfinite_and_policy_models_reject(self):
        _, _, model, _, _ = load_release(self.inbox, self.acks['attention-v1']['package_id'], 'synthetic:model', 'synthetic:parity')
        for value in (float('nan'), float('inf'), True, 10**1000):
            with self.subTest(value=str(value)[:20]), self.assertRaisesRegex(RadarError, 'INVALID_NUMBER'):
                model_validate({**model, 'intercept': value}, 'attention')
        with self.assertRaisesRegex(RadarError, 'POLICY_REQUIRES_STRATEGY_RELEASE'):
            model_validate(model, 'policy')

    def test_current_projection_does_not_import_runtime_or_change_legacy_score(self):
        before = keyword_score('profits rise')
        self.select()
        CurrentRadarAdapter(self.service).score_current([self.snapshot], {'synthetic:source': self.policy()})
        self.assertEqual(keyword_score('profits rise'), before)
        for path in (ROOT / 'application/radar_releases').glob('*.py'):
            source = path.read_text(encoding='utf-8')
            for forbidden in ('import app', 'import requests', 'import market_intelligence', 'import pickle', 'import joblib', 'import torch', 'import ollama'):
                self.assertNotIn(forbidden, source)

    def test_no_alert_and_unavailable_decisions_are_persisted_feedback(self):
        self.select()
        snapshot = copy.deepcopy(self.snapshot)
        document = canonical(dict(schema_version='radar-inert-data/1', data=dict(headline='Synthetic Bank meeting notice', text='')))
        snapshot['document'] = document
        snapshot['evidence']['content_hash'] = digest(document.encode())
        result = self.decision(snapshot)
        self.assertEqual((result['outcome'], result['score'], result['alert']), ('NO_ALERT', .2, False))
        snapshot['evidence']['reconstruction_state'] = 'unverified'
        self.unavailable('UNAVAILABLE_PROVENANCE', snapshot)
        self.assertIn(result, self.service.events())

    def test_separate_store_required_and_unrecognized_journal_rejected(self):
        with self.assertRaisesRegex(RadarError, 'SEPARATE_JOURNAL_REQUIRED'):
            RadarReleases(self.inbox, self.inbox.root / 'journal', issuer_catalog=CATALOG)
        folder = self.root / 'foreign'
        folder.mkdir()
        with closing(sqlite3.connect(folder / 'radar-journal.sqlite3')) as con:
            con.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(RadarError, 'UNRECOGNIZED_JOURNAL'):
            RadarReleases(self.inbox, folder, issuer_catalog=CATALOG)

    def test_isolated_adapter_with_runtime_model_provider_imports_denied(self):
        code = r'''
import sys, importlib.abc, socket, tempfile, json
from pathlib import Path
sys.path.insert(0, 'packages/jse_intelligence_core/src')
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'app','market_intelligence','requests','ollama','torch','backtrader','vectorbt','psycopg2','sqlalchemy','pickle','joblib'}:
            raise AssertionError('forbidden dependency: '+fullname)
sys.meta_path.insert(0,Deny())
def blocked(*args,**kwargs): raise AssertionError('network forbidden')
socket.create_connection=blocked
socket.socket.connect=blocked
from application.release_inbox import ReleaseInbox,load_profiles
from application.radar_releases import RadarReleases,CurrentRadarAdapter
from unittest.mock import patch
f=Path('tests/fixtures/radar_evaluator')
with tempfile.TemporaryDirectory() as tmp, patch('application.radar_releases.service.utc_now',return_value='2026-10-20T12:00:00Z'):
    root=Path(tmp)
    inbox=ReleaseInbox(root/'inbox',load_profiles(f/'profiles.json'),allow_test_profiles=True)
    assert inbox.process(f/'attention-v1')['outcome']=='IMPORTED_INACTIVE'
    release=RadarReleases(inbox,root/'journal',issuer_catalog={'JSE:SYNTH_BANK':'Synthetic Bank'},allow_test_releases=True)
    review=json.loads((f/'attention-v1-review.json').read_bytes())
    release.accept(review)
    release.select(review['package_id'],effective_at='2026-10-20T12:00:00Z',expected_previous=None,reason='synthetic isolation')
    result=CurrentRadarAdapter(release).score_current([json.loads((f/'snapshot.json').read_bytes())],{'synthetic:source':dict(source_id='synthetic:source',enabled=True,admissible=True,observed_at='2026-10-20T12:00:00Z')})
    assert result['items'][0]['score']==.7
'''
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
