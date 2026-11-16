import unittest
from datetime import datetime,timezone,timedelta
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_lookahead import run
from market_intelligence.macro_health import status

class LookaheadTests(unittest.TestCase):
    def test_daily_gate_and_stale_warning(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        now=datetime(2026,11,16,4,tzinfo=timezone.utc);calls=[]
        def syncer(repo,now):calls.append(now);return {}
        first=run(repo,now,syncer=syncer)
        self.assertEqual(first['receipt']['sast_day'],'2026-11-16')
        self.assertEqual(run(repo,now,syncer=syncer)['state'],'ALREADY_RUN_TODAY')
        self.assertEqual(len(calls),1)
        self.assertTrue(any('older than 26 hours' in s for s in status(repo,now+timedelta(hours=27))['warnings']))

    def test_failed_source_is_visible(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        from market_intelligence.macro_calendar import ACCOUNT
        now=datetime(2026,11,16,4,tzinfo=timezone.utc)
        repo.create_paper_account(ACCOUNT,{'mode':'PAPER'})
        repo.save_paper_record('failed-source',ACCOUNT,'macro-browser-result',now.isoformat(),
            {'source_url':'https://www.bls.gov/schedule/2026/','state':'PARSE_FAILED','received_at':now.isoformat()})
        self.assertTrue(any('PARSE_FAILED' in s for s in status(repo,now)['warnings']))
