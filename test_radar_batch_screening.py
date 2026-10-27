"""Source-specific split/merge, resource budgets, failure and freshness tests."""
from copy import deepcopy
from datetime import timedelta
import json
import unittest
from unittest.mock import patch

import test_anticipatory_radar as fixtures
from market_intelligence import anticipatory_radar as radar, radar_batch_screening as batch, research_calendar as cal
from scripts import radar_batch_screening as worker, calendar_ollama as runner

NOW = fixtures.NOW


class BatchScreeningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RadarTests('test_idle_and_ram_gates_make_zero_calls')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo, self.folder = self.fixture.repo, self.fixture.folder
        self.fixture.qualify_fixture()
        from market_intelligence.hermes import capture_news_snapshot
        capture_news_snapshot(self.repo, self.fixture.feed(), NOW)
        base = radar.selection_packet(self.repo, NOW, relevance=True)
        self.news = next(c for c in base['host_candidates'] if c['kind'] == 'CONDITIONAL_WATCH')
        self.calendar = next(c for c in base['host_candidates'] if c.get('calendar_event_id'))
        content = {k: deepcopy(v) for k, v in base.items() if k not in ('record_id', 'schema', 'received_at')}
        content['host_candidates'] = [{**deepcopy(self.calendar if i % 2 == 0 else self.news), 'candidate_id': 'C' + str(i + 1)} for i in range(8)]
        self.packet = radar.save(self.repo, 'input', ['batch-test'], content, NOW)
        self.plan = batch.prepare(self.repo, NOW, self.packet, identity='batch-test')

    def generate(self, p, *args, **kwargs):
        items = {x['candidate_id']: {'match': True,
            'type': 'scheduled' if x.get('title') else 'news'} for x in p['items']}
        content = json.dumps({'items': items})
        return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW

    def run_case(self, index=0, **kwargs):
        opts = {'idle': lambda: 601, 'memory': lambda: 8 * runner.GIB, 'generator': self.generate, **kwargs}
        with patch.object(runner, 'utcnow', return_value=NOW):
            return worker.run_case(self.repo, self.plan, index, NOW, self.folder, 'fixture', **opts)

    def test_frozen_parent_source_specific_tasks_and_two_item_limit(self):
        self.assertEqual([len(b['items']) for b in self.plan['batches']], [2, 2, 2, 2])
        self.assertTrue(all('question' in x for b in self.plan['batches'] for x in b['items']))
        self.assertEqual(batch.prepare(self.repo, NOW, self.packet, identity='batch-test'), self.plan)
        tasks = batch.tasks_for_packet(self.packet)
        tasks[0]['question'] = 'A changed question?'
        with self.assertRaises(ValueError):
            batch.prepare(self.repo, NOW, self.packet, identity='batch-test', tasks=tasks)
        self.assertEqual(radar.rows(self.repo, 'model-attempt', NOW), [])

    def test_schema_allows_both_boolean_values_for_every_candidate(self):
        schema = batch.response_schema(['C1', 'C2'])
        for value in schema['properties']['items']['properties'].values():
            self.assertEqual(value['properties']['match'], {'type': 'boolean'})
        with self.assertRaises(ValueError):
            batch.response_schema(['C1', 'C2', 'C3'])

    def test_only_explicit_complete_future_dates_are_shown(self):
        text = 'Results on 30 October 2026. Another date is 2026-11-02; next Thursday is uncertain.'
        self.assertEqual(radar.explicit_future_dates(text, NOW), ['2026-10-30', '2026-11-02'])
        self.assertEqual(radar.explicit_future_dates('Results on 31 October; next year is unknown.', NOW), [])
        self.assertEqual(radar.explicit_future_dates('Results were 20 October 2026.', NOW), [])
        lead = radar.status(self.repo, NOW)['source_leads'][0]
        self.assertEqual(lead['mentioned_future_dates'], ['2026-10-30'])
        self.assertIsNone(lead['event_date'])

    def test_daily_tasks_cannot_override_host_grounded_questions(self):
        tasks = batch.tasks_for_packet(self.packet)
        tasks[0]['question'] = 'Does this unrelated issuer have an earnings release?'
        with self.assertRaises(ValueError):
            batch.prepare(self.repo, NOW, self.packet, identity='forged-daily', tasks=tasks, scope='DAILY')

    def test_sibling_valid_item_survives_missing_or_invalid_response(self):
        parsed, extra = batch.parse('{"items":{"C1":{"match":true,"type":"scheduled"},"C3":{"match":true,"type":"news"}}}', ['C1', 'C2'])
        self.assertTrue(parsed['C1']['match'])
        self.assertEqual(parsed['C2']['state'], 'INVALID_OR_MISSING_RESPONSE')
        self.assertEqual(extra, ['C3'])
        with self.assertRaises(ValueError):
            batch.parse('{"items":{"C1":{"match":true,"match":false,"type":"news"}}}', ['C1'])

    def test_bad_category_never_removes_retained_source(self):
        result = batch.admit(self.repo, self.packet, self.news,
            {'state': 'MODEL_RESPONSE', 'match': True, 'type': 'scheduled'}, NOW)
        self.assertEqual(result['state'], 'CATEGORY_NOT_SUPPORTED_BY_SOURCE')
        self.assertEqual(len(radar.status(self.repo, NOW)['source_leads']), 1)
        stale = batch.admit(self.repo, self.packet, self.news,
            {'state': 'MODEL_RESPONSE', 'match': True, 'type': 'news'}, NOW + timedelta(hours=49))
        self.assertEqual(stale['state'], 'SOURCE_NOT_CURRENT_OR_UNSUPPORTED')

    def test_partial_and_failed_pairs_keep_other_results_and_all_leads(self):
        self.run_case(0)
        self.run_case(1, generator=lambda *a, **k: 1 / 0)
        merged = worker.save_merge(self.repo, self.plan, NOW)
        states = [x['state'] for x in merged['assessments']]
        self.assertEqual(states[:2], ['MODEL_ASSESSMENT_AVAILABLE', 'MODEL_ASSESSMENT_AVAILABLE'])
        self.assertEqual(states[2:], ['MODEL_ASSESSMENT_UNAVAILABLE'] * 6)
        self.assertEqual(len(radar.status(self.repo, NOW)['source_leads']), 1)
        self.assertEqual(self.run_case(1)['state'], 'BATCH_CALL_ALREADY_SPENT')

    def test_idle_memory_failure_and_interruption_reservations(self):
        self.assertEqual(self.run_case(idle=lambda: 0)['model_calls'], 0)
        self.assertEqual(self.run_case(memory=lambda: runner.GIB)['model_calls'], 0)
        self.assertEqual(radar.rows(self.repo, 'model-attempt', NOW), [])
        def interrupted(*a, **k):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_case(generator=interrupted)
        self.assertEqual(self.run_case()['model_calls'], 0)
        self.assertEqual(worker.save_merge(self.repo, self.plan, NOW)['assessments'][0]['state'], 'MODEL_ASSESSMENT_UNAVAILABLE')

    def test_daily_budget_does_not_reset_old_discovery_slot(self):
        radar.save(self.repo, 'batch-release', 'release', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        old = radar.save(self.repo, 'model-attempt', ['discovery', NOW.astimezone(radar.SAST).date().isoformat()],
            {'mode': 'diagnostic_discovery'}, NOW)
        result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
            memory=lambda: 8 * runner.GIB, generator=self.generate)
        self.assertEqual(result['state'], 'MODEL_BUDGET_ALREADY_SPENT')
        self.assertEqual(self.repo.paper_record(old['record_id']), old)

    def test_later_release_decision_can_disable_daily_calls(self):
        radar.save(self.repo, 'batch-release', 'enabled', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        later = NOW + timedelta(seconds=1)
        radar.save(self.repo, 'batch-release', 'disabled', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': False}, later)
        self.assertIsNone(worker.active_release(self.repo, later))
        self.assertEqual(worker.daily(self.repo, later, self.folder, 'fixture', idle=lambda: 601,
            memory=lambda: 8 * runner.GIB, generator=self.generate)['model_calls'], 0)

    def test_four_daily_children_are_spent_once_and_merge_source_assessments(self):
        radar.save(self.repo, 'batch-release', 'release', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=self.generate)
            replay = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=lambda *a, **k: self.fail('no retry'))
        self.assertEqual(result['model_calls'], 4)
        self.assertEqual(replay['model_calls'], 0)
        self.assertEqual(len(radar.rows(self.repo, 'model-attempt', NOW)), 5)
        self.assertEqual(radar.status(self.repo, NOW)['model']['batch_screening']['state'], 'COMPLETE')
        self.assertIsNotNone(radar.status(self.repo, NOW)['source_leads'][0]['screening_assessment'])

    def test_daily_pauses_after_input_and_resumes_remaining_pairs_only(self):
        radar.save(self.repo, 'batch-release', 'release', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        calls = []
        def generate(packet, *args, **kwargs):
            calls.append([x['candidate_id'] for x in packet['items']])
            return self.generate(packet, *args, **kwargs)
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            first = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601 if not calls else 0,
                memory=lambda: 8 * runner.GIB, generator=generate)
            self.assertEqual(first['state'], 'WAITING_FOR_10_MINUTES_IDLE')
            self.assertEqual(first['model_calls'], 1)
            self.assertEqual(radar.status(self.repo, NOW)['model']['batch_screening']['state'], 'PARTIAL')
            second = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(second['model_calls'], 3)
        self.assertEqual(calls, [['C1', 'C2'], ['C3', 'C4'], ['C5', 'C6'], ['C7', 'C8']])

    def test_validation_requires_mixed_predeclared_expectations(self):
        second = batch.prepare(self.repo, NOW, self.packet, identity='second-test')
        # Separate plans alone cannot make a new held-out packet.
        expected = {p['record_id']: {i: i == 'C1' for i in p['candidate_order']} for p in (self.plan, second)}
        with self.assertRaises(ValueError):
            worker.validation_contract(self.repo, NOW, [self.plan, second], expected, identity='bad')

    def test_changed_prompt_cannot_run_frozen_plan(self):
        with patch.object(batch, 'prompt_for', return_value='changed'), self.assertRaises(ValueError):
            self.run_case()
        self.assertEqual(radar.rows(self.repo, 'model-attempt', NOW), [])


if __name__ == '__main__':
    unittest.main()
