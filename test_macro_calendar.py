import unittest
from datetime import datetime, timezone
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_calendar import sync, records

class MacroCalendarTests(unittest.TestCase):
    def test_confirmation_sidecar_and_idempotence(self):
        repo=SQLiteRepository(':memory:')
        self.addCleanup(repo.close)
        now=datetime(2026,11,16,tzinfo=timezone.utc)
        fetch=lambda url:'Monetary Policy Committee briefing Event Date : 2026-11-19'
        first=sync(repo,now,fetch)
        self.assertEqual(first['SARB']['event']['event_date'],'2026-11-19')
        self.assertEqual(len(records(repo,now)),1)
        self.assertEqual(sync(repo,now,fetch)['new_records'],0)
        self.assertEqual(len(records(repo,now)),1)
        sidecar=records(repo,now)[0]
        self.assertEqual(repo.paper_record(sidecar['confirmation_record_id'])['event_id'],sidecar['event_id'])

    def test_missing_verbatim_date_never_confirms(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        now=datetime(2026,11,16,tzinfo=timezone.utc)
        result=sync(repo,now,lambda url:'Monetary Policy Committee briefing next Thursday')
        self.assertEqual(result['SARB']['state'],'PARSE_FAILED')
        self.assertEqual(records(repo,now),[])
