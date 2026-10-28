"""Individual event watches, source dates, and prospective clock behavior."""
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch

from flask import Flask

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar, research_calendar as cal
from market_intelligence import radar_event_extraction as extract, radar_event_components as components
from market_intelligence.hermes import capture_news_snapshot
from scripts import radar_event_extraction as worker

NOW = datetime(2026, 10, 27, 8, tzinfo=timezone.utc)


class EventComponentTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)

    def capture(self, headline, at, url='https://example.test/oil'):
        payload = {'data': {'llm_used': False, 'ai_available': False, 'ai_pending': False,
            'feed_state': 'AVAILABLE', 'sources': {'fixture': 'AVAILABLE'},
            'items': [{'url': url, 'headline': headline, 'summary': headline,
                       'timestamp': at.isoformat(), 'timestamp_kind': 'published'}]}}
        capture_news_snapshot(self.repo, json.dumps(payload).encode(), at)

    def publish(self, headline, phrase, at=NOW, date_text=''):
        self.capture(headline, at)
        packet = worker.input_packet(self.repo, at)
        candidate = next(c for c in packet['host_candidates'] if headline in c['quote'])
        parsed = extract.parse(json.dumps({'has_future_event': True, 'event_phrase': phrase,
                                           'date_text': date_text}), candidate, at)
        result = extract.publish(self.repo, packet, candidate, parsed, at + timedelta(seconds=1))
        return packet, candidate, parsed, result

    def shared(self):
        return self.publish('Oil declines before Israeli, US votes', 'Israeli, US votes')

    def test_shared_noun_creates_two_linked_idempotent_watches(self):
        packet, candidate, parsed, result = self.shared()
        parent = self.repo.paper_record(result['watch_id'])
        children = [self.repo.paper_record(i) for i in result['component_watch_ids']]
        self.assertEqual([w['component_label'] for w in children], ['Israeli votes', 'US votes'])
        self.assertTrue(all(w['parent_watch_id'] == parent['record_id'] for w in children))
        self.assertTrue(all(w['frozen_at'] == parent['frozen_at'] for w in children))
        self.assertTrue(all(w['event_date'] is None for w in children))
        repeated = extract.publish(self.repo, packet, candidate, parsed, NOW + timedelta(hours=1))
        self.assertEqual(result['component_watch_ids'], repeated['component_watch_ids'])
        self.assertEqual(len(radar.rows(self.repo, 'watch', NOW + timedelta(hours=1))), 3)
        view = radar.status(self.repo, NOW + timedelta(hours=1))
        self.assertEqual(view['metrics']['split_parent_count'], 1)
        self.assertEqual(view['metrics']['event_component_count'], 2)
        self.assertEqual(next(w for w in view['watches'] if w['record_id'] == parent['record_id'])['state'],
                         'SPLIT_INTO_EVENT_WATCHES')
        with self.assertRaisesRegex(ValueError, 'individual'):
            radar.review(self.repo, parent['record_id'], 'NOT_OBSERVED', 'No events', 'operator', NOW + timedelta(days=4))

    def test_headline_can_split_when_model_selected_only_one_named_clause(self):
        headline = 'Oil drops before Fed rate decision and US elections'
        _, _, _, result = self.publish(headline, 'Fed rate decision')
        children = [self.repo.paper_record(i) for i in result['component_watch_ids']]
        self.assertEqual([w['component_label'] for w in children], ['Fed rate decision', 'US elections'])
        self.assertTrue(all(all(f in headline for f in w['component_fragments']) for w in children))

    def test_unrelated_model_phrase_does_not_create_a_fake_event_component(self):
        headline = 'Oil drops before Fed rate decision and US elections'
        _, _, _, result = self.publish(headline, 'Oil drops')
        self.assertEqual(result['component_watch_ids'], [])
        self.assertEqual(len(radar.rows(self.repo, 'watch', NOW + timedelta(minutes=1))), 1)

    def test_date_in_multi_event_sentence_is_not_assigned_to_wrong_child(self):
        headline = 'Sasol results and Naspers results'
        _, _, _, result = self.publish(headline, headline)
        sasol, naspers = [self.repo.paper_record(i) for i in result['component_watch_ids']]
        text = 'Sasol results and Naspers results are due on 3 November 2026.'
        self.assertTrue(components.matches_component(sasol, text))
        self.assertTrue(components.matches_component(naspers, text))
        self.assertIsNone(components.source_date_candidate(sasol, text))
        self.assertIsNone(components.source_date_candidate(naspers, text))
        self.capture(text, NOW + timedelta(hours=1), 'https://example.test/ambiguous')
        self.assertEqual(extract.observe_followups(self.repo, NOW + timedelta(hours=2))['new_event_dates'], 0)

    def test_adjacent_event_nouns_can_share_one_source_date(self):
        headline = 'Sasol results and Naspers results'
        _, _, _, result = self.publish(headline, headline)
        sasol = self.repo.paper_record(result['component_watch_ids'][0])
        candidate = components.source_date_candidate(sasol,
            'Sasol results announcement scheduled for 3 November 2026.')
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate[2].isoformat(), '2026-11-03')

    def test_individual_clauses_only_receive_their_own_dates(self):
        headline = 'Sasol results on 30 October 2026 and Naspers results on 3 November 2026'
        _, _, _, result = self.publish(headline, headline)
        view = radar.status(self.repo, NOW + timedelta(minutes=1))
        children = [w for w in view['watches'] if w.get('parent_watch_id') == result['watch_id']]
        dates = {w['component_label'].split()[0]: w['event_date'] for w in children}
        self.assertEqual(dates, {'Sasol': '2026-10-30', 'Naspers': '2026-11-03'})
        self.assertTrue(all(w['timing']['origin'] == 'HOST_LITERAL_DATE_CANDIDATE' for w in children))
        self.assertTrue(all(len(w['instrument_ids']) == 1 for w in children))
        self.assertEqual(radar.status(self.repo, NOW + timedelta(days=4))['metrics']['occurred'], 0)

    def test_later_dated_source_extends_only_its_event_and_keeps_as_of_clocks(self):
        _, _, _, result = self.shared()
        ids = result['component_watch_ids']
        self.capture('US elections scheduled for 3 November 2026', NOW + timedelta(hours=1),
                     'https://example.test/us')
        observed = NOW + timedelta(hours=2)
        scan = extract.observe_followups(self.repo, observed)
        self.assertEqual(scan['new_event_dates'], 1)
        before = {w['record_id']: w for w in radar.status(self.repo, observed - timedelta(seconds=1))['watches']}
        after = {w['record_id']: w for w in radar.status(self.repo, observed)['watches']}
        israel, us = ids
        self.assertIsNone(before[us]['event_date'])
        self.assertEqual(after[us]['event_date'], '2026-11-03')
        self.assertIsNone(after[israel]['event_date'])
        self.assertEqual(after[us]['expires_at'], '2026-11-04T12:00:00+00:00')
        self.assertEqual(after[us]['original_expires_at'], before[us]['expires_at'])
        self.assertEqual(after[us]['related_sources'][0]['match_basis'], 'INDIVIDUAL_EVENT_TERMS')
        self.assertEqual(after[israel]['related_source_count'], 0)
        self.assertEqual(extract.observe_followups(self.repo, observed)['new_event_dates'], 0)
        almost_end = datetime(2026, 11, 4, 11, 59, tzinfo=timezone.utc)
        self.assertNotEqual(next(w for w in radar.status(self.repo, almost_end)['watches'] if w['record_id'] == us)['state'],
                            'EXPIRED_UNREVIEWED')
        with self.assertRaises(ValueError):
            radar.review(self.repo, us, 'NOT_OBSERVED', 'No election', 'operator', almost_end)
        end = almost_end + timedelta(minutes=1)
        self.assertEqual(extract.observe_followups(self.repo, end)['new_expiries'], 3)
        self.assertEqual(next(w for w in radar.status(self.repo, end)['watches'] if w['record_id'] == us)['state'],
                         'EXPIRED_UNREVIEWED')
        radar.review(self.repo, us, 'NOT_OBSERVED', 'No election reported', 'operator', end)

    def test_later_date_evidence_can_reactivate_an_expired_undated_event(self):
        _, _, _, result = self.shared()
        israel, us = result['component_watch_ids']
        first_scan = NOW + timedelta(hours=49)
        extract.observe_followups(self.repo, first_scan)
        expired = next(w for w in radar.status(self.repo, first_scan)['watches'] if w['record_id'] == us)
        self.assertEqual(expired['state'], 'EXPIRED_UNREVIEWED')
        previous_expiry = expired['expiry_observation']
        received = NOW + timedelta(hours=50)
        self.capture('US elections scheduled for 3 November 2026', received, 'https://example.test/late-date')
        linked = received + timedelta(minutes=1)
        extract.observe_followups(self.repo, linked)
        view = {w['record_id']: w for w in radar.status(self.repo, linked)['watches']}
        self.assertEqual(view[us]['event_date'], '2026-11-03')
        self.assertEqual(view[us]['state'], 'UNCONFIRMED_SOURCE_CANDIDATE')
        self.assertIsNone(view[us]['expiry_observation'])
        self.assertEqual(view[israel]['state'], 'EXPIRED_UNREVIEWED')
        self.assertEqual(self.repo.paper_record(previous_expiry['record_id']), previous_expiry)
        earlier = next(w for w in radar.status(self.repo, linked - timedelta(seconds=1))['watches']
                       if w['record_id'] == us)
        self.assertEqual(earlier['state'], 'EXPIRED_UNREVIEWED')
        self.assertIsNone(earlier['event_date'])

    def test_preexisting_source_dates_a_watch_only_when_new_link_is_recorded(self):
        self.capture('US elections scheduled for 3 November 2026', NOW - timedelta(hours=1),
                     'https://example.test/preexisting-us')
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        at = NOW + timedelta(hours=1)
        before = next(w for w in radar.status(self.repo, at - timedelta(seconds=1))['watches'] if w['record_id'] == us)
        self.assertIsNone(before['event_date'])
        self.assertEqual(extract.observe_followups(self.repo, at)['new_event_dates'], 1)
        after = next(w for w in radar.status(self.repo, at)['watches'] if w['record_id'] == us)
        self.assertEqual(after['event_date'], '2026-11-03')
        self.assertEqual(after['timing']['received_at'], at.isoformat())
        self.assertEqual(after['timing']['citations'][0]['available_at'], (NOW - timedelta(hours=1)).isoformat())
        self.assertEqual(after['related_source_count'], 0)

    def test_single_unscheduled_event_can_gain_a_later_sourced_date(self):
        _, _, _, result = self.publish('Gold steadies as traders prepare for Fed rate call',
                                       'prepare for Fed rate call')
        watch_id = result['watch_id']
        self.assertEqual(result['component_watch_ids'], [])
        self.capture('Federal Reserve interest-rate decision scheduled for 30 October 2026',
                     NOW + timedelta(hours=1), 'https://example.test/fed')
        scan = extract.observe_followups(self.repo, NOW + timedelta(hours=2))
        self.assertEqual(scan['new_event_dates'], 1)
        view = next(w for w in radar.status(self.repo, NOW + timedelta(hours=2))['watches']
                    if w['record_id'] == watch_id)
        self.assertEqual(view['event_date'], '2026-10-30')
        self.assertEqual(view['expires_at'], '2026-10-31T12:00:00+00:00')
        self.assertEqual(view['related_sources'][0]['context_state'], 'TOPIC_NOT_REPEATED_REVIEW_REQUIRED')

    def test_wrong_named_issuer_cannot_supply_a_date_for_generic_event_words(self):
        _, _, _, result = self.publish('Naspers results will be released', 'results will be released')
        self.capture('Sasol results will be released on 3 November 2026', NOW + timedelta(hours=1),
                     'https://example.test/wrong-issuer')
        scan = extract.observe_followups(self.repo, NOW + timedelta(hours=2))
        self.assertEqual(scan['new_event_dates'], 0)
        view = next(w for w in radar.status(self.repo, NOW + timedelta(hours=2))['watches']
                    if w['record_id'] == result['watch_id'])
        self.assertIsNone(view['event_date'])
        self.assertEqual(view['related_source_count'], 0)

    def test_later_conflict_does_not_replace_a_single_frozen_dated_watch(self):
        headline = 'Naspers results on 30 October 2026'
        _, _, _, result = self.publish(headline, 'Naspers results', date_text='30 October 2026')
        self.capture('Naspers results scheduled for 3 November 2026', NOW + timedelta(hours=1),
                     'https://example.test/naspers-revision')
        scan = extract.observe_followups(self.repo, NOW + timedelta(hours=2))
        self.assertEqual(scan['new_date_conflicts'], 1)
        view = next(w for w in radar.status(self.repo, NOW + timedelta(hours=2))['watches']
                    if w['record_id'] == result['watch_id'])
        self.assertEqual(view['event_date'], '2026-10-30')
        self.assertEqual(view['timing_conflicts'][0]['candidate_dates'], ['2026-10-30', '2026-11-03'])
        self.assertEqual(view['expires_at'], '2026-11-04T12:00:00+00:00')
        self.assertFalse(view['calendar_proposable'])

    def test_conflicting_later_dates_are_not_selected_arbitrarily(self):
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        self.capture('US elections scheduled for 3 November 2026', NOW + timedelta(hours=1), 'https://example.test/a')
        self.capture('US elections scheduled for 4 November 2026', NOW + timedelta(hours=1), 'https://example.test/b')
        scan = extract.observe_followups(self.repo, NOW + timedelta(hours=2))
        self.assertEqual(scan['new_event_dates'], 0)
        self.assertEqual(scan['new_date_conflicts'], 1)
        view = next(w for w in radar.status(self.repo, NOW + timedelta(hours=2))['watches'] if w['record_id'] == us)
        self.assertIsNone(view['event_date'])
        self.assertEqual(view['timing_conflicts'][0]['candidate_dates'], ['2026-11-03', '2026-11-04'])
        self.assertEqual(view['expires_at'], '2026-11-05T12:00:00+00:00')
        self.assertEqual(view['state'], 'CONFLICTING_SOURCE_DATES_NEED_REVIEW')
        self.assertEqual(extract.observe_followups(self.repo, NOW + timedelta(hours=2))['new_date_conflicts'], 0)
        after_original_expiry = NOW + timedelta(days=3)
        pending = next(w for w in radar.status(self.repo, after_original_expiry)['watches'] if w['record_id'] == us)
        self.assertEqual(pending['state'], 'CONFLICTING_SOURCE_DATES_NEED_REVIEW')
        with self.assertRaises(ValueError):
            radar.review(self.repo, us, 'NOT_OBSERVED', 'No election reported', 'operator', after_original_expiry)

    def test_operator_resolves_conflict_without_erasing_history_or_reopening_old_sources(self):
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        self.capture('US elections scheduled for 3 November 2026', NOW + timedelta(hours=1), 'https://example.test/a')
        self.capture('US elections scheduled for 4 November 2026', NOW + timedelta(hours=1), 'https://example.test/b')
        extract.observe_followups(self.repo, NOW + timedelta(hours=2))
        source = next(s for s in radar.sources(self.repo, NOW + timedelta(hours=3)) if s['url'].endswith('/a'))
        components.record_timing(self.repo, us, '2026-11-03', components.UNKNOWN_ZONE,
            [{'source_id': source['source_id'], 'quote': source['body']}], source['source_id'],
            '3 November 2026', 'Operator selected this source.', NOW + timedelta(hours=3),
            origin='LOCAL_OPERATOR_SOURCE_DATE_REVIEW')
        self.assertEqual(extract.observe_followups(self.repo, NOW + timedelta(hours=4))['new_date_conflicts'], 0)
        view = next(w for w in radar.status(self.repo, NOW + timedelta(hours=4))['watches'] if w['record_id'] == us)
        self.assertEqual(view['event_date'], '2026-11-03')
        self.assertEqual(view['expires_at'], '2026-11-04T12:00:00+00:00')
        self.assertEqual(view['timing_conflicts'], [])
        self.assertEqual(len(view['timing_conflict_history']), 1)

    def test_source_date_review_api_requires_auth_and_keeps_exact_citations(self):
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        at = NOW + timedelta(hours=1)
        body = 'US elections are scheduled for November 3, 2026.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/date-api', 'title': 'Election',
            'body': body, 'captured_at': at.isoformat(), 'provenance': 'TEST'}, at)
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        client = app.test_client()
        payload = {'watch_id': us, 'event_date': '2026-11-03', 'timezone': 'Etc/GMT+12',
            'source_id': source['record_id'], 'source_quote': body, 'date_text': 'November 3, 2026',
            'explanation': 'The source dates the election.'}
        url = '/api/market-intelligence/weekly-brief/radar-date-review'
        with patch.object(self.repo, 'close'), patch.dict(os.environ, {'SWING_DATA_UPLOAD_TOKEN': 'test-token'}), \
             patch('application.opportunities.operator_api.has_access', return_value=False):
            self.assertEqual(client.post(url, json=payload).status_code, 401)
            response = client.post(url, json=payload, headers={'Authorization': 'Bearer test-token'})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json['origin'], 'LOCAL_OPERATOR_SOURCE_DATE_REVIEW')
            bad = dict(payload, source_quote='Not in the saved source')
            self.assertEqual(client.post(url, json=bad, headers={'Authorization': 'Bearer test-token'}).status_code, 422)
            self.assertEqual(radar.status(self.repo, datetime.now(timezone.utc))['metrics']['reviewed_watch_count'], 0)

    def test_known_zone_date_end_handles_dst_and_citation_validation(self):
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        at = NOW + timedelta(hours=1)
        body = 'US elections are scheduled for November 1, 2026.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/date', 'title': 'Election',
            'body': body, 'captured_at': at.isoformat(), 'provenance': 'TEST'}, at)
        refs = [{'source_id': source['record_id'], 'quote': body}]
        with self.assertRaises(ValueError):
            components.record_timing(self.repo, us, '2026-11-02', 'America/New_York', refs,
                                     source['record_id'], 'November 1, 2026', 'Review', at)
        with self.assertRaises(ValueError):
            components.record_timing(self.repo, us, '2026-11-01', 'America/New_York',
                                     [{'source_id': source['record_id'], 'quote': 'invented'}],
                                     source['record_id'], 'November 1, 2026', 'Review', at)
        timing = components.record_timing(self.repo, us, '2026-11-01', 'America/New_York', refs,
                                          source['record_id'], 'November 1, 2026', 'Review', at)
        self.assertEqual(timing['expires_at'], '2026-11-02T05:00:00+00:00')
        self.assertFalse(timing['automatic_occurrence_verdict'])
        self.assertEqual(components.record_timing(self.repo, us, '2026-11-01', 'America/New_York', refs,
            source['record_id'], 'November 1, 2026', 'Review', at), timing)
        self.assertEqual(radar.status(self.repo, at)['metrics']['occurred'], 0)

    def test_timing_records_cannot_be_mistaken_for_event_watches(self):
        _, _, _, result = self.shared()
        us = result['component_watch_ids'][1]
        at = NOW + timedelta(hours=1)
        body = 'US elections are scheduled for November 3, 2026.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/record-type', 'title': 'Election',
            'body': body, 'captured_at': at.isoformat(), 'provenance': 'TEST'}, at)
        refs = [{'source_id': source['record_id'], 'quote': body}]
        timing = components.record_timing(self.repo, us, '2026-11-03', components.UNKNOWN_ZONE, refs,
                                          source['record_id'], 'November 3, 2026', 'Review.', at)
        with self.assertRaisesRegex(ValueError, 'watch'):
            radar.review(self.repo, timing['record_id'], 'OCCURRED', 'No watch exists here', 'operator', at)
        with self.assertRaisesRegex(ValueError, 'watch'):
            components.record_timing(self.repo, timing['record_id'], '2026-11-03', components.UNKNOWN_ZONE,
                                     refs, source['record_id'], 'November 3, 2026', 'Review.', at)
        with self.assertRaisesRegex(ValueError, 'watch'):
            extract.record_source_review(self.repo, timing['record_id'], 'LATER_REPORT_EVENT_PENDING',
                                         'Review.', refs, at)
        self.assertEqual(radar.status(self.repo, at)['metrics']['reviewed_watch_count'], 0)

    def test_calendar_proposal_does_not_use_an_outdated_original_date(self):
        headline = 'Naspers results on 30 October 2026'
        _, _, _, result = self.publish(headline, 'Naspers results', date_text='30 October 2026')
        at = NOW + timedelta(hours=1)
        body = 'Naspers results rescheduled for 3 November 2026.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/revised', 'title': 'Revision',
            'body': body, 'captured_at': at.isoformat(), 'provenance': 'TEST'}, at)
        components.record_timing(self.repo, result['watch_id'], '2026-11-03', components.UNKNOWN_ZONE,
            [{'source_id': source['record_id'], 'quote': body}], source['record_id'], '3 November 2026',
            'Reviewed the revised date.', at, origin='LOCAL_OPERATOR_SOURCE_DATE_REVIEW')
        with self.assertRaisesRegex(ValueError, 'current individual date source'):
            radar.propose_calendar_watch(self.repo, result['watch_id'], at)
        view = next(w for w in radar.status(self.repo, at)['watches'] if w['record_id'] == result['watch_id'])
        self.assertEqual(view['event_date'], '2026-11-03')

    def test_publication_today_is_attributed_and_never_backdated(self):
        _, _, _, result = self.shared()
        israel = result['component_watch_ids'][0]
        at = NOW + timedelta(hours=2)
        body = 'Israel election today: voting ended.'
        source = cal.import_source(self.repo, {'source_url': 'https://example.test/israel', 'title': 'Election',
            'body': body, 'captured_at': at.isoformat(), 'published_at': '2026-10-26T23:00:00+00:00',
            'provenance': 'TEST'}, at)
        timing = components.record_timing(self.repo, israel, '2026-10-27', 'Asia/Jerusalem',
            [{'source_id': source['record_id'], 'quote': body}], source['record_id'], 'today',
            'The report says today and was published on that local date.', at, basis='PUBLICATION_DAY_TODAY')
        self.assertEqual(timing['received_at'], at.isoformat())
        self.assertEqual(timing['citations'][0]['published_at'], '2026-10-26T23:00:00+00:00')
        previous = next(w for w in radar.status(self.repo, at - timedelta(seconds=1))['watches'] if w['record_id'] == israel)
        self.assertIsNone(previous['event_date'])
        with self.assertRaises(ValueError):
            components.record_timing(self.repo, israel, '2026-10-28', 'Asia/Jerusalem',
                [{'source_id': source['record_id'], 'quote': body}], source['record_id'], 'today',
                'Incorrect date.', at, basis='PUBLICATION_DAY_TODAY')

    def test_reject_ambiguous_or_unrelated_splits_and_sources(self):
        self.assertEqual(components._components('Profit and loss results'), [])
        _, _, _, result = self.shared()
        israel, us = [self.repo.paper_record(i) for i in result['component_watch_ids']]
        self.assertTrue(components.matches_component(us, 'US midterm elections scheduled for 3 November 2026'))
        self.assertFalse(components.matches_component(israel, 'US midterm elections scheduled for 3 November 2026'))
        self.assertFalse(components.matches_component(us, 'The oil price rises on 3 November 2026'))
        self.assertIsNone(components.source_date_candidate(us,
            'US elections on 3 November 2026; US elections on 4 November 2026'))
        self.assertEqual(components.date_mentions('US elections on 9999-12-31'), [])
        with self.assertRaises(ValueError):
            components.date_end('9999-12-31')

    def test_legacy_midnight_expiry_is_projected_without_rewriting_history(self):
        headline = 'Naspers results on 28 October 2026'
        _, _, _, result = self.publish(headline, 'Naspers results', date_text='28 October 2026')
        modern = self.repo.paper_record(result['watch_id'])
        legacy_payload = {k: v for k, v in modern.items() if k not in {'record_id', 'schema', 'received_at'}}
        legacy_payload['expires_at'] = '2026-10-27T22:00:00+00:00'
        legacy = radar.save(self.repo, 'watch', ['legacy-test'], legacy_payload, NOW + timedelta(seconds=1))
        old_time = datetime(2026, 10, 27, 22, 5, tzinfo=timezone.utc)
        old_expiry = radar.save(self.repo, 'watch-expiry', [legacy['record_id']], {'watch_id': legacy['record_id'],
            'expired_at': legacy['expires_at'], 'observed_at': old_time.isoformat(),
            'state': 'EXPIRED_AWAITING_REVIEW'}, old_time)
        before = next(w for w in radar.status(self.repo, old_time)['watches'] if w['record_id'] == legacy['record_id'])
        self.assertEqual(before['expires_at'], legacy['expires_at'])
        self.assertEqual(before['state'], 'EXPIRED_UNREVIEWED')
        with self.assertRaises(ValueError):
            radar.review(self.repo, legacy['record_id'], 'NOT_OBSERVED', 'No event', 'operator', old_time)
        extract.observe_followups(self.repo, old_time)
        current = next(w for w in radar.status(self.repo, old_time)['watches'] if w['record_id'] == legacy['record_id'])
        self.assertEqual(current['original_expires_at'], legacy['expires_at'])
        self.assertEqual(current['expires_at'], '2026-10-29T12:00:00+00:00')
        self.assertEqual(current['expiry_policy']['received_at'], old_time.isoformat())
        self.assertIsNone(current['expiry_observation'])
        self.assertEqual(self.repo.paper_record(old_expiry['record_id']), old_expiry)
        history = next(w for w in radar.status(self.repo, old_time - timedelta(seconds=1))['watches']
                       if w['record_id'] == legacy['record_id'])
        self.assertEqual(history['expires_at'], legacy['expires_at'])
        self.assertEqual(history['state'], 'EXPIRED_UNREVIEWED')
        self.assertIsNone(history['expiry_policy'])
        extract.observe_followups(self.repo, old_time + timedelta(seconds=1))
        self.assertEqual(len(radar.rows(self.repo, 'watch-expiry-policy', old_time + timedelta(seconds=1))), 1)

    def test_new_answer_does_not_rewrite_an_abstained_frozen_packet(self):
        headline = 'Naspers results on 30 October 2026'
        self.capture(headline, NOW)
        packet = worker.input_packet(self.repo, NOW)
        candidate = packet['host_candidates'][0]
        frozen = radar.record_response(self.repo, packet, json.dumps({'items': []}), NOW)
        parsed = extract.parse(json.dumps({'has_future_event': True, 'event_phrase': 'Naspers results',
                                           'date_text': '30 October 2026'}), candidate, NOW)
        result = extract.publish(self.repo, packet, candidate, parsed, NOW + timedelta(seconds=1))
        self.assertEqual(result['state'], 'FROZEN_DISCOVERY_RETAINED_NO_NEW_WATCH')
        self.assertEqual(result['discovery_id'], frozen['record_id'])
        self.assertEqual(radar.rows(self.repo, 'watch', NOW + timedelta(seconds=1)), [])
        self.assertEqual(self.repo.paper_record(frozen['record_id']), frozen)

    def test_replaying_frozen_discovery_keeps_original_watch_identity(self):
        headline = 'Naspers results on 30 October 2026'
        self.capture(headline, NOW)
        packet = worker.input_packet(self.repo, NOW)
        candidate = packet['host_candidates'][0]
        item = {'kind': 'DATED_CANDIDATE', 'source_id': candidate['source_id'], 'quote': candidate['quote'],
            'instrument_ids': candidate['instrument_ids'], 'event_date': '2026-10-30', 'reason': 'Watch results'}
        content = json.dumps({'items': [item]})
        old_item = dict(radar.validate(content, packet, NOW)[0], expires_at='2026-10-29T22:00:00+00:00',
                        time_precision='DATE_ONLY_RELEASE_TIME_UNKNOWN')
        run = radar.save(self.repo, 'discovery', packet['record_id'], {'input_id': packet['record_id'],
            'input_sha256': cal._hash(packet), 'state': 'CITED_CANDIDATES', 'items': [old_item],
            'causal_cutoff': packet['cutoff']}, NOW)
        old = radar.save(self.repo, 'watch', [run['record_id'], old_item], {**old_item,
            'discovery_id': run['record_id'], 'causal_cutoff': packet['cutoff'], 'frozen_at': NOW.isoformat(),
            'trigger': 'Review', 'failure_condition': 'Review'}, NOW)
        self.assertEqual(radar.record_response(self.repo, packet, content, NOW + timedelta(seconds=1)), run)
        self.assertEqual([w['record_id'] for w in radar.rows(self.repo, 'watch', NOW + timedelta(seconds=1))],
                         [old['record_id']])

    def test_calendar_button_respects_the_frozen_calendar_date_parser(self):
        headline = 'Naspers results on November 3, 2026'
        _, _, _, result = self.publish(headline, 'Naspers results', date_text='November 3, 2026')
        view = next(w for w in radar.status(self.repo, NOW + timedelta(minutes=1))['watches']
                    if w['record_id'] == result['watch_id'])
        self.assertEqual(view['event_date'], '2026-11-03')
        self.assertFalse(view['calendar_proposable'])
        self.assertEqual(view['state'], 'UNCONFIRMED_SOURCE_CANDIDATE')

    def test_single_dated_watch_stays_active_through_its_date(self):
        headline = 'Naspers results on 27 October 2026'
        _, _, _, result = self.publish(headline, 'Naspers results', date_text='27 October 2026')
        at = datetime(2026, 10, 27, 23, tzinfo=timezone.utc)
        view = next(w for w in radar.status(self.repo, at)['watches'] if w['record_id'] == result['watch_id'])
        self.assertEqual(view['event_date'], '2026-10-27')
        self.assertEqual(view['expires_at'], '2026-10-28T12:00:00+00:00')
        self.assertEqual(view['state'], 'UNCONFIRMED_SOURCE_CANDIDATE')
        with self.assertRaises(ValueError):
            radar.review(self.repo, result['watch_id'], 'NOT_OBSERVED', 'No release', 'operator', at)


if __name__ == '__main__':
    unittest.main()
