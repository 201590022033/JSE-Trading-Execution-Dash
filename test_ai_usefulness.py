import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from flask import Flask
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import ai_usefulness as ai
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint

NOW = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)

class UsefulnessTests(unittest.TestCase):
    def setUp(self):
        self.repo=SQLiteRepository(':memory:'); self.addCleanup(self.repo.close)
        self.repo.create_paper_account('macro-expectations-v1', {'mode':'PAPER'})
        attempt={'record_id':'a','event_id':'event','received_at':NOW.isoformat(),'input_sha256':'hash',
                 'input':{'sources':[{'source_id':'s','body':'evidence'}]}}
        result={'record_id':'a-result','received_at':NOW.isoformat(),'state':'ABSTAIN','output':{'decision':'ABSTAIN'}}
        self.repo.save_paper_record('a','macro-expectations-v1','macro-expectation-attempt',NOW.isoformat(),attempt)
        self.repo.save_paper_record('a-result','macro-expectations-v1','macro-expectation-result',NOW.isoformat(),result)

    def test_review_is_idempotent_and_does_not_change_output(self):
        before=self.repo.paper_record('a-result')
        with patch('market_intelligence.ai_usefulness.shares.status',return_value={'proposals':[]}):
            one=ai.submit(self.repo,'a-result','NOT_ENOUGH_EVIDENCE','',NOW)
            two=ai.submit(self.repo,'a-result','NOT_ENOUGH_EVIDENCE','',NOW+timedelta(seconds=5))
            state=ai.status(self.repo,NOW+timedelta(seconds=6))
        self.assertEqual(one,two); self.assertEqual(before,self.repo.paper_record('a-result'))
        self.assertEqual(state['counts']['abstained'],1); self.assertEqual(state['counts']['reviewed'],1)
        self.assertFalse(one['independent_human_verification']); self.assertEqual(state['model_calls_on_read'],0)

    def test_api_requires_operator_and_reads_do_not_write(self):
        app=Flask(__name__);app.register_blueprint(create_weekly_brief_blueprint(lambda:self.repo));client=app.test_client()
        with patch.object(self.repo,'close'), patch('market_intelligence.ai_usefulness.shares.status',return_value={'proposals':[]}), patch('market_intelligence.weekly_brief_api.datetime') as clock:
            clock.now.return_value=NOW
            with patch.object(self.repo,'save_paper_record',side_effect=AssertionError('GET wrote')):
                self.assertEqual(client.get('/api/market-intelligence/ai-usefulness').status_code,200)
            payload={'output_id':'a-result','verdict':'USEFUL','reason':'fixture'}
            with patch('application.opportunities.operator_api.has_access',return_value=False), patch.dict('os.environ',{'SWING_DATA_UPLOAD_TOKEN':'secret'}):
                self.assertEqual(client.post('/api/market-intelligence/weekly-brief/ai-usefulness-review',json=payload).status_code,401)
                self.assertEqual(client.post('/api/market-intelligence/weekly-brief/ai-usefulness-review',json=payload,headers={'Authorization':'Bearer secret'}).status_code,202)

    def test_changed_review_then_return_to_first_verdict(self):
        with patch('market_intelligence.ai_usefulness.shares.status',return_value={'proposals':[]}):
            ai.submit(self.repo,'a-result','USEFUL','',NOW,request_id='one')
            ai.submit(self.repo,'a-result','UNSUPPORTED_OR_INCORRECT','',NOW+timedelta(seconds=1),request_id='two')
            third=ai.submit(self.repo,'a-result','USEFUL','',NOW+timedelta(seconds=2),request_id='three')
            state=ai.status(self.repo,NOW+timedelta(seconds=3))
            retry=ai.submit(self.repo,'a-result','USEFUL','',NOW+timedelta(seconds=4),request_id='three')
            with self.assertRaises(ValueError):
                ai.submit(self.repo,'a-result','PARTLY_USEFUL','',NOW+timedelta(seconds=5),request_id='three')
        self.assertEqual(third,retry)
        self.assertEqual(len(state['outputs'][0]['reviews']),3)
        self.assertEqual(state['counts']['owner_useful'],1)

    def test_later_same_url_receipt_keeps_actual_cutoff_and_provider(self):
        old=self.repo.paper_record('a'); old['input']['sources'][0]['url']='https://example.test/report'
        with patch('market_intelligence.ai_usefulness._outputs',return_value=([{'output_id':'a-result','state':'ABSTAIN',
            'received_at':NOW.isoformat(),'cutoff':NOW.isoformat(),'input_sources':old['input']['sources'],
            'citation_state':'NOT_APPLICABLE','followup_state':'NOT_ASSESSED'}], {'a':old})), \
            patch('market_intelligence.ai_usefulness.radar.sources',return_value=[
                {'source_id':'late','receipt_id':'receipt','url':'https://example.test/report','body':'Later news',
                 'available_at':(NOW+timedelta(hours=1)).isoformat(),'published_at':None},
                {'source_id':'other','receipt_id':'other','url':'https://other.test/report','body':'Other provider',
                 'available_at':(NOW+timedelta(hours=1)).isoformat(),'published_at':None}]):
            state=ai.status(self.repo,NOW+timedelta(hours=2))
        self.assertEqual([x['source_id'] for x in state['outputs'][0]['later_sources']],['late'])
        self.assertEqual(state['outputs'][0]['cutoff'],NOW.isoformat())
        self.assertEqual(state['counts']['followup_available'],1)

    def test_later_news_from_separate_source_store_is_included_once(self):
        source=object()
        old=self.repo.paper_record('a'); old['input']['sources'][0]['url']='https://example.test/report'
        output={'output_id':'a-result','state':'ABSTAIN','received_at':NOW.isoformat(),
                'cutoff':NOW.isoformat(),'input_sources':old['input']['sources'],
                'citation_state':'NOT_APPLICABLE','followup_state':'NOT_ASSESSED'}
        later={'source_id':'late','receipt_id':'receipt','url':'https://example.test/report','body':'Later news',
               'available_at':(NOW+timedelta(hours=1)).isoformat(),'published_at':None}
        with patch('market_intelligence.ai_usefulness._outputs',return_value=([output],{'a':old})), \
             patch('market_intelligence.ai_usefulness.radar.sources',side_effect=lambda repo,now: [later]):
            state=ai.status(self.repo,NOW+timedelta(hours=2),source_repo=source)
        self.assertEqual([x['source_id'] for x in state['outputs'][0]['later_sources']],['late'])
        self.assertEqual(state['counts']['followup_available'],1)

if __name__ == '__main__': unittest.main()
