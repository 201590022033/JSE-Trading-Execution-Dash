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

    def test_boolean_protocol_keeps_legacy_plan_valid_and_types_from_host(self):
        v2 = batch.prepare(self.repo, NOW, self.packet, identity='v2-test', version=batch.BOOLEAN_VERSION)
        self.assertEqual(batch.verify(self.repo, self.plan), self.packet)
        spec = v2['batches'][0]
        self.assertEqual(spec['response_schema']['properties']['matches']['properties']['C1'], {'type': 'boolean'})
        parsed, extra = batch.parse_boolean('{"matches":{"C1":true,"C2":false}}', ['C1', 'C2'])
        self.assertEqual(extra, [])
        self.assertTrue(parsed['C1']['match'])
        self.assertFalse(parsed['C2']['match'])
        admitted = batch.admit(self.repo, self.packet, self.calendar, parsed['C1'], NOW)
        self.assertEqual(admitted['display_type'], 'scheduled')
        self.assertEqual(admitted['type_origin'], 'RETAINED_HOST_SOURCE_KIND')

    def test_boolean_response_bad_sibling_does_not_discard_good_match(self):
        parsed, extra = batch.parse_boolean('{"matches":{"C1":true,"C2":"false","C3":true}}', ['C1', 'C2'])
        self.assertTrue(parsed['C1']['match'])
        self.assertEqual(parsed['C2']['state'], 'INVALID_OR_MISSING_RESPONSE')
        self.assertEqual(extra, ['C3'])
        with self.assertRaises(ValueError):
            batch.parse_boolean('{"matches":{"C1":true,"C1":false}}', ['C1'])

    def test_boolean_daily_release_still_uses_four_children(self):
        radar.save(self.repo, 'batch-release', 'boolean-release', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        def generate(packet, *args, **kwargs):
            content = json.dumps({'matches': {x['candidate_id']: True for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
            replay = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=lambda *a, **k: self.fail('no retry'))
        self.assertEqual(result['model_calls'], 4)
        self.assertEqual(replay['model_calls'], 0)
        self.assertEqual(self.repo.paper_record(result['batch_plan_id'])['version'], batch.BOOLEAN_VERSION)
        self.assertEqual(radar.status(self.repo, NOW)['source_leads'][0]['screening_assessment']['type_origin'],
            'RETAINED_HOST_SOURCE_KIND')

    def test_daily_rechecks_only_four_supported_misses_and_keeps_original_answers(self):
        radar.save(self.repo, 'batch-release', 'boolean-recheck-release', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        def generate(packet, *args, **kwargs):
            matched = len(packet['items']) == 1
            content = json.dumps({'matches': {x['candidate_id']: matched for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
            again = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=lambda *a, **k: self.fail('must not repeat'))
        self.assertEqual(result['model_calls'], 8)
        self.assertEqual(again['model_calls'], 0)
        merge = self.repo.paper_record(result['merge_id'])
        self.assertEqual(merge['recheck_attempts'], 4)
        self.assertEqual(merge['recheck_matches'], 4)
        self.assertEqual(sum(x['state'] == 'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK' for x in merge['assessments']), 4)
        for item in merge['assessments']:
            self.assertFalse(item['assessment']['match'])
            if item['state'] == 'MODEL_RECHECK_MATCH':
                self.assertTrue(item['recheck_assessment']['match'])
        view = radar.status(self.repo, NOW)
        self.assertEqual(view['model']['batch_screening']['recheck_matches'], 4)
        self.assertEqual(view['model']['batch_screening']['model_matches'], 0)

    def test_daily_does_not_recheck_unverified_or_failed_source_links(self):
        radar.save(self.repo, 'batch-release', 'boolean-no-supported-recheck', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        def generate(packet, *args, **kwargs):
            content = json.dumps({'matches': {x['candidate_id']: False for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW
        with patch.object(batch, 'host_supports_task', return_value=False), \
                patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(result['model_calls'], 4)
        self.assertEqual(self.repo.paper_record(result['merge_id'])['recheck_attempts'], 0)

    def test_old_frozen_daily_parent_does_not_gain_a_recheck_budget(self):
        radar.save(self.repo, 'batch-release', 'old-parent-release', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        old = batch.prepare(self.repo, NOW, self.packet, identity='old-parent', scope='DAILY', version=batch.BOOLEAN_VERSION)
        day = NOW.astimezone(radar.SAST).date().isoformat()
        radar.save(self.repo, 'model-attempt', ['discovery', day], {'mode': 'source_specific_daily_parent',
            'batch_plan_id': old['record_id'], 'maximum_child_generation_calls': 4}, NOW)
        def generate(packet, *args, **kwargs):
            content = json.dumps({'matches': {x['candidate_id']: False for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW
        with patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(result['model_calls'], 4)
        self.assertNotIn('recheck_attempts', self.repo.paper_record(result['merge_id']))

    def test_failed_individual_rechecks_are_spent_and_original_misses_remain(self):
        radar.save(self.repo, 'batch-release', 'failed-recheck-release', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        def generate(packet, *args, **kwargs):
            if len(packet['items']) == 1:
                raise ValueError('fixture recheck failure')
            content = json.dumps({'matches': {x['candidate_id']: False for x in packet['items']}})
            return json.dumps({'response': content, 'done': True}).encode(), content, NOW, NOW
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
            again = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=lambda *a, **k: self.fail('no retry'))
        merged = self.repo.paper_record(result['merge_id'])
        self.assertEqual(result['model_calls'], 8)
        self.assertEqual(again['model_calls'], 0)
        self.assertEqual(merged['recheck_matches'], 0)
        self.assertTrue(all(x['state'] == 'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK' for x in merged['assessments']))

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

    def test_one_off_source_review_is_distinct_from_daily_budget(self):
        plan=batch.prepare(self.repo,NOW,self.packet,identity='review-test',scope='REVIEW',version=batch.BOOLEAN_VERSION)
        def generate(packet,*args,**kwargs):
            content=json.dumps({'matches':{x['candidate_id']:True for x in packet['items']}})
            return json.dumps({'response':content,'done':True}).encode(),content,NOW,NOW
        with patch.object(runner,'utcnow',return_value=NOW):
            worker.run_case(self.repo,plan,0,NOW,self.folder,'fixture',idle=lambda:601,
                memory=lambda:8*runner.GIB,generator=generate)
            worker.save_merge(self.repo,plan,NOW)
        view=radar.status(self.repo,NOW)
        self.assertEqual(view['model']['batch_screening']['scope'],'REVIEW')
        self.assertIsNotNone(view['source_leads'][0]['screening_assessment'])
        slot_id='radar-model-attempt-'+cal._hash(['discovery',NOW.astimezone(radar.SAST).date().isoformat()])
        self.assertIsNone(self.repo.paper_record(slot_id))

    def test_host_disagreement_never_rewrites_the_model_response(self):
        plan=batch.prepare(self.repo,NOW,self.packet,identity='review-false',scope='REVIEW',version=batch.BOOLEAN_VERSION)
        parsed={i:{'state':'MODEL_RESPONSE','match':False} for i in ('C1','C2')}
        merged=batch.merge(self.repo,plan,{0:{'parsed':parsed}},NOW)
        for item in merged['assessments'][:2]:
            self.assertEqual(item['state'],'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK')
            self.assertFalse(item['assessment']['match'])
        self.assertEqual(len(radar.status(self.repo,NOW)['source_leads']),1)

    def test_host_disagreement_is_not_applied_to_changed_or_expired_tasks(self):
        tasks=batch.tasks_for_packet(self.packet)
        tasks[1]['question']='Does the evidence describe a different issuer?'
        plan=batch.prepare(self.repo,NOW,self.packet,identity='custom-review',scope='REVIEW',
            version=batch.BOOLEAN_VERSION,tasks=tasks)
        parsed={'C2':{'state':'MODEL_RESPONSE','match':False}}
        self.assertEqual(batch.merge(self.repo,plan,{0:{'parsed':parsed}},NOW)['assessments'][1]['state'],
            'MODEL_DID_NOT_MATCH')
        standard=batch.prepare(self.repo,NOW,self.packet,identity='normal-review',scope='REVIEW',version=batch.BOOLEAN_VERSION)
        self.assertEqual(batch.merge(self.repo,standard,{0:{'parsed':parsed}},NOW+timedelta(hours=49))['assessments'][1]['state'],
            'MODEL_DID_NOT_MATCH')

    def test_reviewed_source_is_visible_even_below_eight_newer_leads(self):
        source_list=[{'source_id':'fixture-'+str(i),'body':'Naspers source '+str(i),
            'url':'https://example.test/'+str(i),'receipt_id':'receipt-'+str(i),
            'available_at':NOW.isoformat(),'published_at':None} for i in range(9)]
        radar.save(self.repo,'batch-merge','review-order',{'scope':'REVIEW','state':'COMPLETE',
            'attempted_pairs':1,'total_pairs':1,'assessments':[{'candidate_id':'C9','source_id':'fixture-8',
                'calendar_event_id':None,'state':'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK',
                'assessment':{'match':False}}]},NOW)
        with patch.object(radar,'sources',return_value=source_list):
            view=radar.status(self.repo,NOW)
        self.assertEqual(len(view['source_leads']),8)
        reviewed=next(s for s in view['source_leads'] if s['source_id']=='fixture-8')
        self.assertEqual(reviewed['screening_assessment']['state'],'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK')

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

    def test_new_protocol_does_not_change_an_in_progress_old_daily_packet(self):
        radar.save(self.repo, 'batch-release', 'old-release', {'version': batch.VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, NOW)
        calls = []
        def generate(packet, *args, **kwargs):
            calls.append([x['candidate_id'] for x in packet['items']])
            return self.generate(packet, *args, **kwargs)
        later = NOW + timedelta(seconds=1)
        with patch.object(radar, 'selection_packet', return_value=self.packet), patch.object(runner, 'utcnow', return_value=NOW):
            first = worker.daily(self.repo, NOW, self.folder, 'fixture', idle=lambda: 601 if not calls else 0,
                memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(first['model_calls'], 1)
        radar.save(self.repo, 'batch-release', 'new-release', {'version': batch.BOOLEAN_VERSION,
            'model_digest': worker.DIGEST, 'enabled': True}, later)
        with patch.object(runner, 'utcnow', return_value=later):
            result = worker.daily(self.repo, later, self.folder, 'fixture', idle=lambda: 601,
                memory=lambda: 8 * runner.GIB, generator=generate)
        self.assertEqual(result['model_calls'], 3)
        self.assertEqual(self.repo.paper_record(result['batch_plan_id'])['version'], batch.VERSION)
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
