"""Offline budget/causality checks; mocks are never native-model evidence."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from scripts import radar_request_comparison as comparison
import test_anticipatory_radar as fixtures

NOW = fixtures.NOW


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        f = fixtures.RadarTests('test_idle_and_ram_gates_make_zero_calls')
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.repo, self.folder = f.repo, f.folder
        p = deepcopy(f.p)
        p.update(response_format='HOST_GROUNDED_BOOLEAN_V4', request=comparison.radar.RELEVANCE_REQUEST)
        p['host_candidates'] = [{'candidate_id': 'C' + str(n), 'kind': 'DATED_CANDIDATE',
            'source_id': f.source['record_id'], 'quote': f.body, 'instrument_ids': ['NPN'],
            'calendar_event_id': f.event['record_id'], 'event_date': '2026-10-30'} for n in range(1, 9)]
        p = {k: v for k, v in p.items() if k not in ('record_id', 'schema', 'received_at')}
        self.p = comparison.radar.save(self.repo, 'input', p, p, NOW)
        self.spec = {'label': 'offline-fixture', 'packet_id': self.p['record_id'],
            'subset_ids': ['C1', 'C6'], 'explicit_request': 'Fixture request',
            'explicit_ids': ['C1'], 'broad_ids': ['C' + str(n) for n in range(1, 9)]}
        self.c = comparison.prepare(self.repo, NOW, self.spec)

    def generate(self, packet, *args, **kwargs):
        allowed = [x['candidate_id'] for x in packet['host_candidates']]
        expected = allowed if packet['request'] == comparison.radar.RELEVANCE_REQUEST else ['C1']
        content = json.dumps({'matches': {i: i in expected for i in allowed}})
        return json.dumps({'response': content, 'done': True, 'eval_count': 10}).encode(), content, NOW, NOW

    def run_case(self, case='A', **kwargs):
        options = {'idle': lambda: 600, 'memory': lambda: 8 * comparison.runner.GIB,
            'generator': self.generate, **kwargs}
        with patch.object(comparison.runner, 'utcnow', return_value=NOW):
            return comparison.run_case(self.repo, self.c, case, NOW, self.folder, 'fixture', **options)

    def test_freeze_context_expectations_and_no_generation(self):
        self.assertEqual(comparison.prepare(self.repo, NOW, self.spec), self.c)
        self.assertEqual(comparison.radar.rows(self.repo, 'model-attempt', NOW), [])
        self.assertEqual(self.repo.paper_record(self.p['record_id']), self.p)
        self.assertNotIn('title', self.p['host_candidates'][0])
        self.assertEqual([c['width'] for c in self.c['cases']], [2, 8, 2, 8])
        for case in self.c['cases']:
            self.assertNotIn('expected_ids', case['packet'])
            self.assertNotIn(comparison.ASSESSMENT, case['prompt'])
            props = case['response_schema']['properties']['matches']['properties']
            self.assertTrue(all(p == {'type': 'boolean'} for p in props.values()))

    def test_changed_definition_prompt_or_contract_cannot_spend(self):
        with self.assertRaises(ValueError):
            comparison.prepare(self.repo, NOW, {**self.spec, 'explicit_ids': ['C6']})
        with patch.object(comparison.radar, 'selection_prompt', return_value='changed'), self.assertRaises(ValueError):
            self.run_case()
        self.c['cases'][0]['expected_ids'] = []
        with self.assertRaises(ValueError):
            self.run_case()
        self.assertEqual(comparison.radar.rows(self.repo, 'model-attempt', NOW), [])

    def test_routine_idle_and_memory_gate_before_reservation(self):
        self.assertEqual(self.run_case(idle=lambda: 599)['state'], 'WAITING_FOR_IDLE')
        self.assertEqual(self.run_case(memory=lambda: comparison.runner.GIB)['state'], 'WAITING_FOR_SMALL_MODEL_MEMORY')
        self.assertEqual(comparison.radar.rows(self.repo, 'model-attempt', NOW), [])
        calls = []
        def generate(*args, **kwargs):
            calls.append(kwargs['required_idle_seconds'])
            return self.generate(*args, **kwargs)
        self.run_case(generator=generate)
        self.assertEqual(calls, [None])

    def test_foreground_authority_is_saved_and_scoped_to_four(self):
        def generate(*args, **kwargs):
            self.assertEqual(kwargs['required_idle_seconds'], 0)
            return self.generate(*args, **kwargs)
        self.run_case(idle=lambda: 0, generator=generate,
            foreground_authorization='Explicit offline test authorization')
        auth = comparison.radar.rows(self.repo, 'request-width-authorization', NOW)
        self.assertEqual(len(auth), 1)
        self.assertEqual(auth[0]['contract_id'], self.c['record_id'])
        self.assertEqual(auth[0]['maximum_generation_calls'], 4)

    def test_four_calls_then_replay_cannot_change_daily_slot_hold_or_sources(self):
        radar = comparison.radar
        daily = radar.save(self.repo, 'model-attempt', ['discovery', '2026-10-27'],
            {'mode': 'diagnostic_discovery'}, NOW)
        hold = radar.save(self.repo, 'screening-source-review', 'fixture-hold',
            {'hold_identical_request': True, 'request': radar.RELEVANCE_REQUEST}, NOW)
        for case in 'ABCD':
            self.assertTrue(self.run_case(case)['matches_preregistered_assessment'])
        for case in 'ABCD':
            self.assertEqual(self.run_case(case)['model_calls'], 0)
        with self.assertRaises(ValueError):
            self.run_case('E')
        self.assertEqual(len(radar.rows(self.repo, 'model-attempt', NOW)), 5)
        self.assertEqual(self.repo.paper_record(daily['record_id']), daily)
        self.assertEqual(self.repo.paper_record(hold['record_id']), hold)
        self.assertEqual(self.repo.paper_record(self.p['record_id']), self.p)
        self.assertEqual(radar.rows(self.repo, 'watch', NOW), [])
        result = comparison.report(self.repo, self.c, NOW)
        self.assertEqual(result['reserved_calls'], 4)
        self.assertEqual(result['state'], 'FAILURE_NOT_REPRODUCED_WITH_CONSTANT_CONTEXT_REPAIR')

    def test_failure_is_spent_without_retry(self):
        r = self.run_case(generator=lambda *a, **k: 1 / 0)
        self.assertEqual(r['state'], 'COMPARISON_FAILED_NO_RETRY')
        self.assertEqual(self.run_case()['state'], 'COMPARISON_CASE_ALREADY_SPENT')

    def test_process_interruption_leaves_spent_reservation(self):
        def interrupted(*a, **k):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_case(generator=interrupted)
        self.assertEqual(self.run_case()['model_calls'], 0)
        self.assertFalse(comparison.report(self.repo, self.c, NOW)['complete'])

    def test_native_malformed_boolean_retains_raw_and_counts_failure(self):
        def generate(*a, **k):
            return b'{"response":"bad fixture"}', '{"matches":{"C1":"true","C6":false}}', NOW, NOW
        r = self.run_case(generator=generate)
        self.assertEqual(r['state'], 'COMPARISON_FAILED_NO_RETRY')
        self.assertIn('raw_archive', r)
        self.assertEqual(self.run_case()['model_calls'], 0)

    def test_request_vs_width_conclusion_is_not_invented_from_partial_results(self):
        self.run_case('A', generator=lambda p, *a, **k: (
            b'{}', json.dumps({'matches': {x['candidate_id']: False for x in p['host_candidates']}}), NOW, NOW))
        self.assertEqual(comparison.report(self.repo, self.c, NOW)['state'], 'INCOMPLETE_OR_INTERRUPTED_CAMPAIGN')
        self.run_case('B', generator=lambda p, *a, **k: (
            b'{}', json.dumps({'matches': {x['candidate_id']: False for x in p['host_candidates']}}), NOW, NOW))
        self.run_case('C')
        self.run_case('D')
        self.assertEqual(comparison.report(self.repo, self.c, NOW)['state'], 'REQUEST_FORMULATION_PROBLEM_SUPPORTED')

    def test_broad_size_effect_can_coexist_with_explicit_full_packet_success(self):
        self.run_case('A')
        self.run_case('B', generator=lambda p, *a, **k: (
            b'{}', json.dumps({'matches': {x['candidate_id']: False for x in p['host_candidates']}}), NOW, NOW))
        self.run_case('C')
        self.run_case('D')
        self.assertEqual(comparison.report(self.repo, self.c, NOW)['state'],
            'BROAD_REQUEST_SIZE_SENSITIVITY_EXPLICIT_REQUEST_PASSED_BOTH')

    def test_failed_generation_cannot_be_interpreted_as_semantic_disagreement(self):
        self.run_case('A', generator=lambda *a, **k: 1 / 0)
        self.run_case('B', generator=lambda p, *a, **k: (
            b'{}', json.dumps({'matches': {x['candidate_id']: False for x in p['host_candidates']}}), NOW, NOW))
        self.run_case('C')
        self.run_case('D')
        self.assertEqual(comparison.report(self.repo, self.c, NOW)['state'],
            'NATIVE_RESPONSE_FAILURE_PREVENTS_COMPARISON')


if __name__ == '__main__':
    unittest.main()
