import unittest
from datetime import datetime,timezone
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_health import status,MEMBERS

class MacroHealthTests(unittest.TestCase):
    def test_empty_weekday_has_specific_warnings_and_macro_scope(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        result=status(repo,datetime(2026,11,16,10,tzinfo=timezone.utc))
        self.assertEqual(result['next_7_days'],0)
        self.assertEqual(set(result['scope']),{'USDZAR','ZAR_RATES','DXY'})
        self.assertIn('No confirmed macro events are registered for the next 7 days.',result['warnings'])
        self.assertEqual(len([w for w in result['warnings'] if w.startswith('Official schedule capture missing:')]),4)
