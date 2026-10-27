"""The width comparison preserves questions and spends each call at most once."""
from copy import deepcopy
import json
from unittest.mock import patch
import unittest

import test_anticipatory_radar as fixtures
from market_intelligence import anticipatory_radar as radar, radar_batch_screening as batch, research_calendar as cal
from scripts import calendar_ollama as runner, radar_batch_screening as worker, radar_pair_diagnosis as diagnosis
from scripts import radar_exact_pair_diagnosis as exact
from scripts import radar_recheck


class WidthDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RadarTests('test_idle_and_ram_gates_make_zero_calls')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.repo, self.now = self.fixture.repo, fixtures.NOW
        self.fixture.qualify_fixture()
        from market_intelligence.hermes import capture_news_snapshot
        capture_news_snapshot(self.repo, self.fixture.feed(), self.now)
        base = radar.selection_packet(self.repo, self.now, relevance=True)
        template = base['host_candidates'][0]
        content = {k: deepcopy(v) for k, v in base.items() if k not in ('record_id', 'schema', 'received_at')}
        content['host_candidates'] = [{**deepcopy(template), 'candidate_id': f'C{i}'} for i in range(1, 9)]
        packet = radar.save(self.repo, 'input', 'width-test-input', content, self.now)
        positive = batch.prepare(self.repo, self.now, packet, identity='width-positive', scope='REVIEW', version=batch.BOOLEAN_VERSION)
        negative = batch.prepare(self.repo, self.now, packet, identity='width-negative', scope='VALIDATION', version=batch.BOOLEAN_VERSION)
        review = radar.save(self.repo, 'batch-source-review-contract', 'width-review', {
            'plan_id': positive['record_id'], 'plan_sha256': cal._hash(positive),
            'assistant_expected_ids': list(positive['candidate_order'])}, self.now)
        validation = radar.save(self.repo, 'batch-validation', 'width-validation', {
            'plan_ids': ['unused', negative['record_id']], 'plan_sha256': ['unused', cal._hash(negative)],
            'expected': {negative['record_id']: {f'C{i}': i not in (2, 3, 6, 7) for i in range(1, 9)}}}, self.now)
        self.args = (review['record_id'], validation['record_id'])

    def test_same_questions_are_compared_at_two_widths_and_order_varies(self):
        c = diagnosis.prepare(self.repo, self.now, *self.args)
        self.assertEqual(len(c['plans']), 12)
        self.assertEqual(c, diagnosis.prepare(self.repo, self.now, *self.args))
        for i in range(4):
            single_p = self.repo.paper_record(c['plans'][i]['plan_id'])['batches'][0]['items'][0]
            single_n = self.repo.paper_record(c['plans'][i + 4]['plan_id'])['batches'][0]['items'][0]
            pair = self.repo.paper_record(c['plans'][i + 8]['plan_id'])['batches'][0]['items']
            self.assertEqual({x['candidate_id']: x for x in pair},
                             {single_p['candidate_id']: single_p, single_n['candidate_id']: single_n})
            self.assertEqual(pair[0]['candidate_id'][0], 'P' if i % 2 == 0 else 'N')
        self.assertEqual(diagnosis.report(self.repo, c)['attempted_calls'], 0)

    def test_each_case_is_reserved_once_and_does_not_spend_daily_slot(self):
        c = diagnosis.prepare(self.repo, self.now, *self.args)
        plan = self.repo.paper_record(c['plans'][0]['plan_id'])
        def generate(packet, *args, **kwargs):
            content = json.dumps({'matches': {x['candidate_id']: True for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, self.now, self.now
        with patch.object(runner, 'utcnow', return_value=self.now):
            first = worker.run_case(self.repo, plan, 0, self.now, self.fixture.folder, 'fixture',
                idle=lambda: 601, memory=lambda: 8 * runner.GIB, generator=generate)
            again = worker.run_case(self.repo, plan, 0, self.now, self.fixture.folder, 'fixture',
                idle=lambda: 601, memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(first['state'], 'BATCH_RESPONSE_RECORDED')
        self.assertEqual(again['state'], 'BATCH_CALL_ALREADY_SPENT')
        self.assertEqual(diagnosis.report(self.repo, c)['attempted_calls'], 1)
        slot = 'radar-model-attempt-' + cal._hash(['discovery', self.now.astimezone(radar.SAST).date().isoformat()])
        self.assertIsNone(self.repo.paper_record(slot))

    def test_original_pair_prompts_are_byte_identical_and_singles_keep_ids(self):
        contract = exact.prepare(self.repo, self.now, self.args[0])
        self.assertEqual(len(contract['plans']), 7)
        self.assertEqual(exact.report(self.repo, contract)['attempted_calls'], 0)
        original = self.repo.paper_record(contract['original_plan_id'])
        for case in contract['plans']:
            plan = self.repo.paper_record(case['plan_id'])
            if case['original_batch_index'] is None:
                self.assertEqual(plan['candidate_order'], [case['name'].removeprefix('single-')])
            else:
                self.assertEqual(plan['batches'][0]['prompt'],
                    original['batches'][case['original_batch_index']]['prompt'])

    def test_existing_review_can_show_exact_rechecks_without_losing_first_answers(self):
        contract = exact.prepare(self.repo, self.now, self.args[0])
        original = self.repo.paper_record(contract['original_plan_id'])
        def generate(packet, *args, **kwargs):
            single = len(packet['items']) == 1
            content = json.dumps({'matches': {x['candidate_id']: single or x['candidate_id'] not in exact.MISSES
                                              for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, self.now, self.now
        with patch.object(runner, 'utcnow', return_value=self.now):
            for i in range(4):
                worker.run_case(self.repo, original, i, self.now, self.fixture.folder, 'fixture',
                    idle=lambda: 601, memory=lambda: 8 * runner.GIB, generator=generate)
            for case in contract['plans'][:4]:
                worker.run_case(self.repo, self.repo.paper_record(case['plan_id']), 0, self.now,
                    self.fixture.folder, 'fixture', idle=lambda: 601, memory=lambda: 8 * runner.GIB, generator=generate)
            rechecks = radar_recheck.adopt_review_diagnosis(self.repo, original, contract, self.now)
            merged = radar_recheck.save_merge(self.repo, original, rechecks, self.now)
        self.assertEqual(merged['recheck_matches'], 4)
        for item in merged['assessments']:
            if item['candidate_id'] in exact.MISSES:
                self.assertEqual(item['state'], 'MODEL_RECHECK_MATCH')
                self.assertFalse(item['assessment']['match'])
                self.assertTrue(item['recheck_assessment']['match'])


if __name__ == '__main__':
    unittest.main()
