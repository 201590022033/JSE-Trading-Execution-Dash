"""Read-only joins for confirmed macro preparation and warning evidence."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_calendar import sync
from market_intelligence.macro_prep import prepare
from market_intelligence.event_preparation import status


class EventPreparationTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now = datetime(2026, 11, 16, 10, tzinfo=timezone.utc)
        sync(self.repo, self.now, lambda _: 'Monetary Policy Committee briefing Event Date : 2026-11-19')
        self.packet = prepare(self.repo, self.now, price_rows=[])[0]

    def test_links_saved_packet_and_missed_window_without_writes(self):
        with patch.object(self.repo, 'save_paper_record', side_effect=AssertionError('read wrote')):
            result = status(self.repo, self.now)
        event = next(e for e in result['events'] if e['event_key'] == 'SARB_MPC_2026-11')
        self.assertEqual(event['confirmation_label'], 'Automated official-schedule sync')
        self.assertEqual(event['packets'][0]['record_id'], self.packet['record_id'])
        self.assertEqual(event['packets'][0]['state'], 'LATE_PACKET')
        self.assertEqual(event['windows'][0]['state'], 'MISSED_BEFORE_CONFIRMATION')
        self.assertIsNone(event['windows'][0]['receipt_id'])
        self.assertEqual(event['next_warning']['hours'], 24)
        self.assertTrue(event['next_warning']['due_sast'].startswith('2026-11-18T00:00:00'))
        self.assertEqual(result['model_calls_on_read'], 0)

    def test_past_date_only_anchor_is_not_a_release_confirmation(self):
        later = self.now + timedelta(days=4)
        event = next(e for e in status(self.repo, later)['events'] if e['event_key'] == 'SARB_MPC_2026-11')
        self.assertEqual(event['state'], 'PAST_AWAITING_OBSERVATIONAL_FOLLOWUP')
        self.assertEqual(event['time_precision'], 'DATE_ONLY_RELEASE_TIME_UNKNOWN')
        self.assertIsNone(event['next_warning'])

    def test_invalid_saved_citation_is_not_presented_as_advice(self):
        event = self.packet['event']
        self.repo.create_paper_account('macro-expectations-v1', {'mode':'PAPER'})
        attempt = {'record_id':'attempt', 'event_id':event['record_id'],
                   'event_key':event['event_key'], 'received_at':self.now.isoformat(),
                   'input':{'sources':[{'source_id':'source','body':'known source'}]}}
        result = {'record_id':'attempt-result', 'received_at':self.now.isoformat(),
                  'state':'ADVISORY_DRAFT', 'output':{'decision':'PROPOSE',
                  'expectation':'unsupported', 'citations':[{'source_id':'source','quote':'invented'}]}}
        self.repo.save_paper_record('attempt','macro-expectations-v1','macro-expectation-attempt',self.now.isoformat(),attempt)
        self.repo.save_paper_record('attempt-result','macro-expectations-v1','macro-expectation-result',self.now.isoformat(),result)
        projected = next(e for e in status(self.repo,self.now)['events'] if e['event_id']==event['record_id'])
        self.assertEqual(projected['macro_result']['state'], 'CITATION_INVALID')
        self.assertIsNone(projected['macro_result']['output'])
        self.assertNotIn('input', projected['macro_attempt'])

    def test_date_only_source_is_not_a_supported_expectation(self):
        event = self.packet['event']
        self.repo.create_paper_account('macro-expectations-v1', {'mode':'PAPER'})
        source = {'source_id':event['source_receipt_id'], 'body':event['source_quote']}
        attempt = {'record_id':'date-attempt', 'event_id':event['record_id'],
                   'event_key':event['event_key'], 'received_at':self.now.isoformat(),
                   'input':{'sources':[source]}}
        result = {'record_id':'date-attempt-result', 'received_at':self.now.isoformat(),
                  'state':'ADVISORY_DRAFT', 'output':{'decision':'PROPOSE',
                  'expectation':'Rates will increase', 'citations':[{'source_id':source['source_id'],
                                                                      'quote':source['body']}]}}
        self.repo.save_paper_record('date-attempt','macro-expectations-v1','macro-expectation-attempt',self.now.isoformat(),attempt)
        self.repo.save_paper_record('date-attempt-result','macro-expectations-v1','macro-expectation-result',self.now.isoformat(),result)
        projected = next(e for e in status(self.repo,self.now)['events'] if e['event_id']==event['record_id'])
        self.assertEqual(projected['macro_result']['state'], 'INSUFFICIENT_EVIDENCE')
        self.assertIsNone(projected['macro_result']['output'])

    def test_related_source_added_after_attempt_marks_input_stale(self):
        event = self.packet['event']
        self.repo.create_paper_account('macro-expectations-v1', {'mode':'PAPER'})
        attempt = {'record_id':'old', 'event_id':event['record_id'], 'received_at':self.now.isoformat(),
                   'input':{'sources':[{'source_id':event['source_receipt_id'], 'body':event['source_quote']}]}}
        self.repo.save_paper_record('old','macro-expectations-v1','macro-expectation-attempt',self.now.isoformat(),attempt)
        with patch('market_intelligence.event_preparation.relevant_sources', return_value=[{'source_id':'news', 'body':'SARB report', 'url':'https://example.test'}]):
            projected = next(e for e in status(self.repo,self.now)['events'] if e['event_id']==event['record_id'])
        self.assertEqual(projected['saved_input_source_state'],'NEW_RELATED_SOURCES_SINCE_ATTEMPT')
        self.assertEqual(projected['related_sources'][0]['source_id'],'news')

    def test_empty_quote_does_not_validate(self):
        event = self.packet['event']
        self.repo.create_paper_account('macro-expectations-v1', {'mode':'PAPER'})
        attempt = {'record_id':'empty', 'event_id':event['record_id'], 'received_at':self.now.isoformat(),
                   'input':{'sources':[{'source_id':'news','body':'Real text'}]}}
        result = {'record_id':'empty-result','received_at':self.now.isoformat(),'state':'ADVISORY_DRAFT',
                  'output':{'decision':'PROPOSE','expectation':'Claim','citations':[{'source_id':'news','quote':''}]}}
        self.repo.save_paper_record('empty','macro-expectations-v1','macro-expectation-attempt',self.now.isoformat(),attempt)
        self.repo.save_paper_record('empty-result','macro-expectations-v1','macro-expectation-result',self.now.isoformat(),result)
        projected = next(e for e in status(self.repo,self.now)['events'] if e['event_id']==event['record_id'])
        self.assertEqual(projected['macro_result']['state'],'CITATION_INVALID')


if __name__ == '__main__':
    unittest.main()
