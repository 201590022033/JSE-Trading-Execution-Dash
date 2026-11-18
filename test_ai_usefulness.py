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

if __name__ == '__main__': unittest.main()
