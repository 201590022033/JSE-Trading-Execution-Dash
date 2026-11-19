import importlib.util
import os
import unittest
from datetime import datetime,timezone
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_calendar import browser_capture,playwright_fetch,SARB_URL

class BrowserCaptureTests(unittest.TestCase):
    def test_visible_text_preserved_and_daily_reuse(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        calls=[]
        def fetch(url):
            calls.append(url)
            return {'body':'Visible\n2026-11-19','html':'<body>Visible<br>2026-11-19</body>', 'http_status':200,'challenge':False}
        now=datetime(2026,11,16,tzinfo=timezone.utc)
        first=browser_capture(repo,'SARB',SARB_URL,now,fetcher=fetch)
        self.assertEqual(repo.paper_record(first['source_receipt_id'])['body'],'Visible\n2026-11-19')
        self.assertEqual(browser_capture(repo,'SARB',SARB_URL,now,fetcher=fetch),first)
        browser_capture(repo,'SARB',SARB_URL,now,fetcher=fetch,refresh=True)
        browser_capture(repo,'SARB',SARB_URL,now,fetcher=fetch,refresh=True)
        self.assertEqual(len(calls),2)

    @unittest.skipUnless(importlib.util.find_spec('playwright'), 'Installed Playwright unavailable: SARB browser integration skipped')
    @unittest.skipIf(os.environ.get('TRADING_OFFLINE_TESTS') == '1', 'Live SARB browser capture requires an explicit online run')
    def test_real_sarb_visible_date(self):
        capture=playwright_fetch(SARB_URL)
        self.assertFalse(capture['challenge'])
        self.assertEqual(capture['http_status'],200)
        self.assertRegex(capture['body'],r'Event Date\s*:\s*2026-11-19')
