import unittest
from pathlib import Path
from market_intelligence.macro_calendar import parse_schedule

class ScheduleParsers(unittest.TestCase):
    def test_real_rendered_fixtures(self):
        for key,expected in [('ZA_CPI','2026-11-18'),('US_CPI','2026-12-10'),('FOMC','2026-12-09')]:
            body=(Path('tests/fixtures/macro')/(key+'.txt')).read_text(encoding='utf-8')
            parsed=parse_schedule(key,body)
            self.assertIn(expected,[row[0].isoformat() for row in parsed])
            for _,quote,_ in parsed:self.assertIn(quote,body)

    def test_unrelated_date_not_event(self):
        for key in ('ZA_CPI','US_CPI','FOMC'):
            self.assertEqual(parse_schedule(key,'18 November 2026\nUnrelated release'),[])
