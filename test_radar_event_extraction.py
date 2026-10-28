"""Causal source extraction, partial admissions, budgets and prospective review."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar, research_calendar as cal
from market_intelligence import radar_event_extraction as extract
from market_intelligence.hermes import capture_news_snapshot
from scripts import calendar_ollama as runner, radar_event_extraction as worker
from scripts import anticipatory_radar as coordinator, radar_batch_screening as screening_worker

NOW = datetime(2026, 10, 27, 8, tzinfo=timezone.utc)


class EventExtractionTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.capture('https://example.test/npn', 'Naspers: results will be released on 30 October 2026', NOW)
        self.packet = radar.selection_packet(self.repo, NOW, relevance=True)
        self.contract = worker.prepare(self.repo, NOW, self.packet, 'DAILY', '2026-10-27')
        self.one = self.repo.paper_record(self.contract['cases'][0]['packet_id'])
        self.candidate = self.one['host_candidates'][0]

    def capture(self, url, headline, at):
        payload = {'data': {'llm_used': False, 'ai_available': False, 'ai_pending': False,
            'feed_state': 'AVAILABLE', 'sources': {'fixture': 'AVAILABLE'},
            'items': [{'url': url, 'headline': headline, 'summary': headline,
                'timestamp': at.isoformat(), 'timestamp_kind': 'published'}]}}
        return capture_news_snapshot(self.repo, json.dumps(payload).encode(), at)

    def response(self, phrase='results will be released', date='', has=True):
        return json.dumps({'has_future_event': has, 'event_phrase': phrase, 'date_text': date})

    def parsed(self, phrase='results will be released', date=''):
        return extract.parse(self.response(phrase, date), self.candidate, NOW)

    def test_exact_phrase_and_full_date_are_source_cited(self):
        parsed = self.parsed('RESULTS WILL BE RELEASED', '30 October 2026')
        self.assertEqual(parsed['event_phrase'], 'results will be released')
        self.assertEqual(parsed['event_date'], '2026-10-30')
        result = extract.publish(self.repo, self.one, self.candidate, parsed, NOW + timedelta(seconds=1))
        watch = self.repo.paper_record(result['watch_id'])
        self.assertEqual(watch['instrument_ids'], ['NPN'])
        self.assertEqual(watch['date_state'], 'UNCONFIRMED_SOURCE_CANDIDATE')
        self.assertEqual(watch['frozen_at'], (NOW + timedelta(seconds=1)).isoformat())
        self.assertEqual(watch['causal_cutoff'], NOW.isoformat())
        self.assertFalse(watch['live_execution'])

    def test_missing_or_unsupported_dates_do_not_discard_valid_phrase(self):
        for date, issue in [('tomorrow', 'DATE_NOT_IN_SOURCE'),
                            ('29 October 2026', 'DATE_NOT_IN_SOURCE')]:
            parsed = self.parsed(date=date)
            self.assertEqual(parsed['event_phrase'], 'results will be released')
            self.assertIsNone(parsed['event_date'])
            self.assertEqual(parsed['date_issue'], issue)
        p = {'quote': 'Naspers results on 26 October 2026 and on 30 October.'}
        for date in ('26 October 2026', '30 October'):
            parsed = extract.parse(self.response('Naspers results', date), p, NOW)
            self.assertIsNone(parsed['event_date'])
            self.assertEqual(parsed['date_issue'], 'DATE_NOT_FULLY_SPECIFIED_AND_FUTURE')

    def test_invented_phrase_and_duplicate_json_are_rejected(self):
        with self.assertRaises(ValueError):
            self.parsed('Sasol will report results')
        with self.assertRaises(ValueError):
            extract.parse('{"has_future_event":true,"has_future_event":false,"event_phrase":"","date_text":""}',
                          self.candidate, NOW)
        self.assertEqual(radar.rows(self.repo, 'watch', NOW), [])

    def test_vague_commentary_does_not_become_an_event_but_source_survives(self):
        self.capture('https://example.test/sasol', 'Sasol at R300: Where to next?', NOW)
        packet = radar.selection_packet(self.repo, NOW, relevance=True)
        candidate = next(x for x in packet['host_candidates'] if 'Where to next?' in x['quote'])
        parsed = extract.parse(self.response('Where to next?', has=True), candidate, NOW)
        result = extract.publish(self.repo, packet, candidate, parsed, NOW)
        self.assertEqual(result['state'], 'UNSPECIFIC_COMMENTARY_NEEDS_REVIEW')
        self.assertTrue(result['source_retained'])
        self.assertTrue(parsed['has_future_event'])  # Original model answer remains auditable.
        self.assertFalse(radar.rows(self.repo, 'watch', NOW))
        self.assertTrue(any('Where to next?' in s['body'] for s in radar.sources(self.repo, NOW)))
        self.assertFalse(extract.commentary_only('results will be released'))
        self.assertTrue(extract.commentary_only('Sasol at R300: Where to next?'))
        self.assertFalse(extract.commentary_only('Sasol results on 30 October: Where to next?'))

    def test_specific_appointment_is_not_blocked_as_commentary(self):
        self.capture('https://example.test/appointment', 'Sasol: a director will be appointed on 30 October 2026', NOW)
        packet = radar.selection_packet(self.repo, NOW, relevance=True)
        candidate = next(x for x in packet['host_candidates'] if 'director will be appointed' in x['quote'])
        parsed = extract.parse(self.response('director will be appointed', '30 October 2026'), candidate, NOW)
        result = extract.publish(self.repo, packet, candidate, parsed, NOW)
        self.assertEqual(result['state'], 'SOURCE_EVENT_WATCH_CREATED')
        self.assertEqual(result['event_date'], '2026-10-30')

    def test_no_event_and_stale_source_do_not_create_watches(self):
        p = extract.parse(self.response(has=False), self.candidate, NOW)
        self.assertEqual(extract.publish(self.repo, self.one, self.candidate, p, NOW)['state'], 'NO_SPECIFIC_FUTURE_EVENT')
        with self.assertRaisesRegex(ValueError, 'expired'):
            extract.publish(self.repo, self.one, self.candidate, self.parsed(date='30 October 2026'),
                            NOW + timedelta(hours=49))
        self.assertFalse(radar.rows(self.repo, 'watch', NOW + timedelta(hours=49)))

    def test_tampered_source_and_wrong_issuer_cannot_be_published(self):
        altered = dict(self.candidate, instrument_ids=['SOL'])
        with self.assertRaises(ValueError):
            extract.publish(self.repo, self.one, altered, self.parsed(), NOW)
        self.assertFalse(radar.rows(self.repo, 'watch', NOW))

    def test_confirmed_calendar_reference_never_makes_duplicate_watch(self):
        text = 'Naspers results will be released on 30 October 2026.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/calendar', 'title': 'Schedule',
            'body': text, 'captured_at': NOW.isoformat(), 'provenance': 'TEST'}, NOW)
        event = cal.propose_event(self.repo, {'event_key': 'npn-results', 'title': 'Naspers results',
            'instrument_ids': ['NPN'], 'source_receipt_id': source['record_id'], 'source_quote': text,
            'event_date': '2026-10-30', 'timezone': 'Africa/Johannesburg'}, NOW)
        cal.confirm_event(self.repo, event['record_id'], 'fixture', NOW)
        packet = radar.selection_packet(self.repo, NOW, relevance=True)
        c = next(x for x in packet['host_candidates'] if x.get('calendar_event_id'))
        parsed = extract.parse(self.response('results will be released', '30 October 2026'), c, NOW)
        result = extract.publish(self.repo, packet, c, parsed, NOW)
        self.assertEqual(result['state'], 'CONFIRMED_CALENDAR_REFERENCE')
        self.assertFalse(radar.rows(self.repo, 'watch', NOW))
        parsed['event_date'] = '2026-10-31'
        with self.assertRaises(ValueError):
            extract.publish(self.repo, packet, c, parsed, NOW)

    def test_followup_requires_later_receipt_and_same_direct_issuer(self):
        result = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW + timedelta(seconds=1))
        self.capture('https://example.test/wrong', 'Sasol: results will be released', NOW + timedelta(hours=1))
        self.capture('https://example.test/right', 'Naspers: results will be released soon', NOW + timedelta(hours=2))
        self.capture('https://example.test/unattributed', 'The results will be released soon', NOW + timedelta(hours=2, minutes=15))
        scan = extract.observe_followups(self.repo, NOW + timedelta(hours=3))
        self.assertEqual(scan['new_related_sources'], 2)
        self.assertEqual(extract.observe_followups(self.repo, NOW + timedelta(hours=3))['new_related_sources'], 0)
        view = radar.status(self.repo, NOW + timedelta(hours=3))
        watch = next(w for w in view['watches'] if w['record_id'] == result['watch_id'])
        self.assertEqual(watch['related_source_count'], 2)
        linked = {x['source_url']: x for x in watch['related_sources']}
        self.assertIn('https://example.test/right', linked)
        self.assertNotIn('https://example.test/wrong', linked)
        self.assertEqual(linked['https://example.test/unattributed']['context_state'], 'ISSUER_NOT_REPEATED_REVIEW_REQUIRED')
        self.assertEqual(linked['https://example.test/right']['state'], 'RELATED_SOURCE_NEEDS_REVIEW_NOT_EVENT_OUTCOME')
        self.assertEqual(view['metrics']['occurred'], 0)
        self.assertEqual(view['model_calls_on_read'], 0)

    def test_expiry_is_saved_at_actual_scan_time_not_graded(self):
        extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)
        scan_time = NOW + timedelta(hours=49)
        self.assertEqual(extract.observe_followups(self.repo, scan_time)['new_expiries'], 1)
        self.assertEqual(extract.observe_followups(self.repo, scan_time)['new_expiries'], 0)
        view = radar.status(self.repo, scan_time)
        watch = view['watches'][0]
        self.assertEqual(watch['expiry_observation']['observed_at'], scan_time.isoformat())
        self.assertEqual(watch['state'], 'EXPIRED_UNREVIEWED')
        self.assertEqual(view['metrics']['not_observed'], 0)

    def test_reworded_later_source_and_human_review_keep_actual_clocks(self):
        result = extract.publish(self.repo, self.one, self.candidate,
                                 self.parsed(date='30 October 2026'), NOW)
        self.capture('https://example.test/reworded', 'Naspers released the results', NOW + timedelta(hours=2))
        self.assertEqual(extract.observe_followups(self.repo, NOW + timedelta(hours=3))['new_related_sources'], 1)
        radar.review(self.repo, result['watch_id'], 'OCCURRED', 'Reviewed later source', 'owner',
                     NOW + timedelta(hours=4))
        watch = radar.status(self.repo, NOW + timedelta(hours=4))['watches'][0]
        self.assertEqual(watch['related_sources'][0]['match_basis'], 'SHARED_EVENT_WORDS')
        self.assertEqual(watch['review_hours_after_watch'], 4)
        self.assertEqual(watch['review_note'], 'Reviewed later source')
        self.assertEqual(watch['date_only_lead_hours'], 62)

    def test_repeat_source_does_not_reset_first_watch(self):
        first = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)
        later = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW + timedelta(hours=1))
        self.assertEqual(later['state'], 'EXISTING_SOURCE_EVENT_WATCH')
        self.assertEqual(first['watch_id'], later['watch_id'])
        self.assertEqual(self.repo.paper_record(first['watch_id'])['frozen_at'], NOW.isoformat())

    def test_idle_budget_and_attempts_are_individual_and_spent_once(self):
        case = self.contract['cases'][0]
        wait = worker.run_case(self.repo, self.contract, case['candidate_id'], NOW, self.folder, 'unused',
                               idle=lambda: 599, memory=lambda: 8*runner.GIB)
        self.assertEqual(wait['state'], 'WAITING_FOR_10_MINUTES_IDLE')
        self.assertFalse(radar.rows(self.repo, 'model-attempt', NOW))
        def generate(*args, **kwargs):
            return b'{}', self.response(date='tomorrow'), NOW, NOW
        with patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.run_case(self.repo, self.contract, case['candidate_id'], NOW, self.folder, 'unused',
                idle=lambda: 601, memory=lambda: 8*runner.GIB, generator=generate)
            repeat = worker.run_case(self.repo, self.contract, case['candidate_id'], NOW, self.folder, 'unused',
                idle=lambda: 601, memory=lambda: 8*runner.GIB, generator=generate)
        self.assertEqual(result['state'], 'EVENT_RESPONSE_RECORDED')
        self.assertEqual(result['parsed']['date_issue'], 'DATE_NOT_IN_SOURCE')
        self.assertEqual(result['publication']['state'], 'SOURCE_EVENT_WATCH_CREATED')
        self.assertEqual(repeat['state'], 'EVENT_CASE_ALREADY_SPENT')
        self.assertEqual(len(radar.rows(self.repo, 'model-attempt', NOW)), 1)
        status = radar.status(self.repo, NOW)
        self.assertEqual(status['model']['event_extraction']['completed'], 1)
        self.assertEqual(status['source_leads'][0]['event_assessment']['parsed']['event_phrase'], 'results will be released')
        worker.prepare(self.repo, NOW + timedelta(seconds=1), self.packet, 'DAILY', 'later-parent')
        old_watch = radar.status(self.repo, NOW + timedelta(seconds=1))['watches'][0]
        self.assertIn('MODEL_DATE_NOT_SUPPORTED_BY_SOURCE', old_watch['extraction_warnings'])

    def test_failure_in_one_source_does_not_stop_another(self):
        self.capture('https://example.test/sol', 'Sasol will announce a meeting', NOW)
        packet = radar.selection_packet(self.repo, NOW, relevance=True)
        contract = worker.prepare(self.repo, NOW, packet, 'DAILY', 'second-test')
        self.assertGreaterEqual(len(contract['cases']), 2)
        def failing(*args, **kwargs):
            raise RuntimeError('one source failed')
        def good(packet, *args, **kwargs):
            phrase = packet['candidate']['quote'].splitlines()[0]
            return b'{}', self.response(phrase), NOW, NOW
        with patch.object(runner, 'utcnow', return_value=NOW):
            first = worker.run_case(self.repo, contract, contract['cases'][0]['candidate_id'], NOW,
                self.folder, 'unused', idle=lambda: 601, memory=lambda: 8*runner.GIB, generator=failing)
            second = worker.run_case(self.repo, contract, contract['cases'][1]['candidate_id'], NOW,
                self.folder, 'unused', idle=lambda: 601, memory=lambda: 8*runner.GIB, generator=good)
        self.assertEqual(first['state'], 'EVENT_FAILED_NO_RETRY')
        self.assertEqual(second['state'], 'EVENT_RESPONSE_RECORDED')
        self.assertEqual(worker.report(self.repo, contract, NOW)['reserved'], 2)

    def test_missed_forward_wording_is_an_independent_cited_lead(self):
        self.capture('https://example.test/gold', 'Gold steadies as traders prepare for Fed rate call', NOW)
        packet = radar.selection_packet(self.repo, NOW, relevance=True)
        contract = worker.prepare(self.repo, NOW, packet, 'DAILY', 'wording-test')
        case = next(c for c in contract['cases'] if 'Fed rate call' in self.repo.paper_record(
            c['packet_id'])['host_candidates'][0]['quote'])
        def missed(*args, **kwargs):
            return b'{}', self.response(has=False), NOW, NOW
        with patch.object(runner, 'utcnow', return_value=NOW):
            result = worker.run_case(self.repo, contract, case['candidate_id'], NOW, self.folder, 'unused',
                idle=lambda: 601, memory=lambda: 8*runner.GIB, generator=missed)
        self.assertFalse(result['parsed']['has_future_event'])
        self.assertEqual(result['publication']['state'], 'SOURCE_WORDING_FALLBACK')
        watch = next(w for w in radar.status(self.repo, NOW)['watches'] if 'Fed rate call' in w['reason'])
        self.assertEqual(watch['suggestion_origin'], 'SOURCE_WORDING')
        self.assertIsNone(watch['event_date'])
        self.assertIn('prepare for Fed rate call', watch['quote'])

    def test_unlinked_source_is_not_excluded_from_event_input_or_leads(self):
        self.capture('https://example.test/unlinked', 'Exampleco will hold an investor day', NOW)
        packet = worker.input_packet(self.repo, NOW)
        c = next(x for x in packet['host_candidates'] if 'Exampleco' in x['quote'])
        self.assertEqual(c['instrument_ids'], [])
        contract = worker.prepare(self.repo, NOW, packet, 'DAILY', 'unlinked-test')
        self.assertTrue(any(x['candidate_id'] == c['candidate_id'] for x in contract['cases']))
        self.assertTrue(any('Exampleco' in x['quote'] for x in radar.status(self.repo, NOW)['source_leads']))

    def test_screening_wait_does_not_suppress_separate_event_parent(self):
        with patch.object(screening_worker, 'active_release', return_value=True), \
             patch.object(screening_worker, 'daily', return_value={'state': 'BATCH_VALIDATION_REVIEW_PENDING'}), \
             patch.object(worker, 'daily', return_value={'state': 'EVENT_DAILY_CASES_SPENT', 'model_calls': 0}) as event_daily, \
             patch.object(runner, 'utcnow', return_value=NOW):
            result = coordinator.model_tick(self.repo, NOW, self.folder, 'unused')
        event_daily.assert_called_once()
        self.assertEqual(result['screening']['state'], 'BATCH_VALIDATION_REVIEW_PENDING')
        self.assertEqual(result['event_extraction']['state'], 'EVENT_DAILY_CASES_SPENT')

    def test_assistant_review_keeps_publication_and_acquisition_distinct(self):
        watch_id = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)['watch_id']
        acquired = NOW + timedelta(hours=2)
        body = 'Naspers results were published yesterday.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/review',
            'title': 'Review source', 'body': body, 'captured_at': acquired.isoformat(),
            'published_at': (NOW - timedelta(hours=1)).isoformat(), 'provenance': 'TEST'}, acquired)
        review = extract.record_source_review(self.repo, watch_id, 'PART_OF_WATCH_OCCURRENCES_PRECEDE_WATCH',
            'Assistant reviewed a previously published source.', [{'source_id': source['record_id'], 'quote': body}], acquired)
        repeated = extract.record_source_review(self.repo, watch_id, 'PART_OF_WATCH_OCCURRENCES_PRECEDE_WATCH',
            'Assistant reviewed a previously published source.', [{'source_id': source['record_id'], 'quote': body}], acquired)
        self.assertEqual(review, repeated)
        self.assertFalse(review['citations'][0]['published_after_watch'])
        self.assertTrue(review['citations'][0]['acquired_after_watch'])
        linked = extract.attach_reviewed_source(self.repo, review, source['record_id'], acquired)
        self.assertEqual(linked['match_basis'], 'ASSISTANT_REVIEWED_EVENT_LINK')
        self.assertEqual(linked['published_at'], (NOW - timedelta(hours=1)).isoformat())
        self.assertEqual(extract.attach_reviewed_source(self.repo, review, source['record_id'], acquired), linked)
        status = radar.status(self.repo, acquired)
        self.assertEqual(status['metrics']['assistant_source_review_count'], 1)
        self.assertEqual(status['metrics']['reviewed_watch_count'], 0)
        self.assertEqual(status['metrics']['occurred'], 0)
        self.assertEqual(status['watches'][0]['source_reviews'][0]['review_origin'],
                         'ASSISTANT_SOURCE_REVIEW_NOT_INDEPENDENT_HUMAN_LABEL')

    def test_assistant_review_rejects_invented_or_pre_watch_sources(self):
        watch_id = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW + timedelta(seconds=1))['watch_id']
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/pre',
            'title': 'Earlier source', 'body': 'Naspers held a meeting.', 'captured_at': NOW.isoformat(),
            'provenance': 'TEST'}, NOW)
        with self.assertRaises(ValueError):
            extract.record_source_review(self.repo, watch_id, 'LATER_REPORT_EVENT_PENDING', 'Earlier',
                [{'source_id': source['record_id'], 'quote': 'Naspers held a meeting.'}], NOW + timedelta(minutes=1))
        with self.assertRaises(ValueError):
            extract.record_source_review(self.repo, watch_id, 'NO_SPECIFIC_EVENT_IN_QUOTED_PHRASE', 'Invented',
                [{'source_id': self.candidate['source_id'], 'quote': 'A made-up event.'}], NOW + timedelta(minutes=1))
        self.assertEqual(radar.rows(self.repo, 'watch-source-review', NOW + timedelta(minutes=1)), [])

    def test_original_source_remains_reviewable_after_fresh_feed_window(self):
        watch_id = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)['watch_id']
        later = NOW + timedelta(days=8)
        self.assertFalse(any(s['source_id'] == self.candidate['source_id'] for s in radar.sources(self.repo, later)))
        review = extract.record_source_review(self.repo, watch_id, 'NO_SPECIFIC_EVENT_IN_QUOTED_PHRASE',
            'An archival source review.', [{'source_id': self.candidate['source_id'], 'quote': 'Naspers'}], later)
        self.assertFalse(review['citations'][0]['acquired_after_watch'])

    def test_old_capture_imported_later_is_not_mislabeled_as_new_acquisition(self):
        watch_id = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)['watch_id']
        received = NOW + timedelta(hours=2)
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/archived',
            'title': 'Older capture', 'body': 'Naspers results are on the calendar.',
            'captured_at': (NOW - timedelta(hours=1)).isoformat(), 'provenance': 'TEST'}, received)
        review = extract.record_source_review(self.repo, watch_id, 'LATER_REPORT_EVENT_PENDING', 'Imported later.',
            [{'source_id': source['record_id'], 'quote': 'Naspers results are on the calendar.'}], received)
        self.assertFalse(review['citations'][0]['acquired_after_watch'])
        self.assertTrue(review['citations'][0]['available_after_watch'])
        followup = extract.attach_reviewed_source(self.repo, review, source['record_id'], received)
        self.assertEqual(followup['source_captured_at'], (NOW - timedelta(hours=1)).isoformat())

    def test_early_review_receipts_remain_linkable(self):
        watch_id = extract.publish(self.repo, self.one, self.candidate, self.parsed(), NOW)['watch_id']
        received = NOW + timedelta(hours=2)
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/legacy',
            'title': 'Legacy', 'body': 'Naspers results appear.', 'captured_at': received.isoformat(),
            'provenance': 'TEST'}, received)
        citation = {'source_id': source['record_id'], 'source_url': source['source_url'],
            'quote': source['body'], 'available_at': source['received_at'],
            'published_at': None, 'acquired_after_watch': True}
        old = radar.save(self.repo, 'watch-source-review', ['legacy'], {'watch_id': watch_id,
            'citations': [citation]}, received)
        linked = extract.attach_reviewed_source(self.repo, old, source['record_id'], received)
        self.assertEqual(linked['source_captured_at'], received.isoformat())


if __name__ == '__main__':
    unittest.main()
