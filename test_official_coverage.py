import unittest
from pathlib import Path
from datetime import date
from market_intelligence.official_coverage import parse

class CoverageTests(unittest.TestCase):
    def text(self,key):return (Path('tests/fixtures/macro')/(key+'.txt')).read_text(encoding='utf-8')
    def test_real_future_schedules(self):
        self.assertIn(('SARB_MPC',date(2027,1,28)),[(f,d) for f,d,q,r in parse('SARB_FULL',self.text('SARB_FULL'))])
        self.assertIn(('FOMC',date(2027,4,28)),[(f,d) for f,d,q,r in parse('FOMC_FULL',self.text('FOMC_FULL'))])
        rows=parse('BLS_2027',self.text('BLS_2027'))
        self.assertIn(('US_NFP',date(2027,4,2)),[(f,d) for f,d,q,r in rows])
        self.assertNotIn(('US_NFP',date(2027,4,6)),[(f,d) for f,d,q,r in rows])
        for f,d,q,r in rows:self.assertIn(q,self.text('BLS_2027'))

    def test_unrelated_and_strategy_dates_not_rate_decisions(self):
        self.assertEqual(parse('BLS_2027','Tuesday, April 06, 2027\n10:00 AM\nEmployment Situation of Veterans for Annual 2026'),[])
        self.assertEqual(parse('FOMC_FULL','2027 FOMC Meetings\nOctober\n26-27\nMonetary Policy Strategy Meeting\nLast Update:'),[])

    def test_real_fixture_registration_is_idempotent(self):
        from datetime import datetime,timezone
        from unittest.mock import patch
        from persistence.sqlite_repository import SQLiteRepository
        from market_intelligence import macro_calendar as macro,research_calendar as cal
        from market_intelligence.official_coverage import sync
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        now=datetime(2026,11,16,10,tzinfo=timezone.utc)
        revised=[False]
        def capture(repo,key,url,now,refresh=False):
            repo.create_paper_account(macro.ACCOUNT,{'mode':'PAPER'})
            body=self.text(key)
            if revised[0] and key=='ZA_CPI':body=body.replace('18 November 2026 (Wednesday)','1 December 2026 (Tuesday)')
            source=cal.import_source(repo,{'source_url':url,'title':'Test using real captured visible fixture',
                'body':body,'captured_at':now.isoformat(),'provenance':'REAL_PAGE_FIXTURE_OFFLINE_TEST'},now)
            return {'state':'CAPTURED','source_receipt_id':source['record_id'],'raw_html_sha256':'fixture-metadata'}
        with patch.object(macro,'browser_capture',side_effect=capture):
            self.assertGreater(sync(repo,now)['new_records'],0)
            self.assertEqual(sync(repo,now)['new_records'],0)
        events=cal.status(repo,now)['upcoming']
        self.assertTrue(any(e['event_key']=='US_NFP_2027-04' and e['event_date']=='2027-04-02' for e in events))
        self.assertFalse(any(e['event_key'].startswith('US_NFP') and e['event_date']=='2027-04-06' for e in events))
        sidecars=macro.records(repo,now)
        for event in events:self.assertEqual(sum(s['event_id']==event['record_id'] for s in sidecars),1)
        revised[0]=True
        with patch.object(macro,'browser_capture',side_effect=capture):
            sync(repo,now,refresh=True)
            self.assertEqual(sync(repo,now,refresh=True)['new_records'],0)
        revised_event=next(e for e in cal.status(repo,now)['upcoming'] if e['event_key']=='ZA_CPI_2026-11')
        self.assertEqual(revised_event['event_date'],'2026-12-01')
        self.assertEqual(revised_event['revision'],2)
