import unittest
from datetime import datetime, timezone, timedelta
from application.strategy_radar.sharedata_quote import parse_quote


class ShareDataQuoteTests(unittest.TestCase):
    def test_session_identity_and_delay_guards(self):
        raw = b'''<input id="IntradayChart_Intraday1DDate" value="Mon 9 Nov 2026">
        <span id="LatestIntradayData_LblJSECode">MTN</span>
        <span id="LatestIntradayData_LblLastTradeDay"></span>
        <span id="LatestIntradayData_LblTradeTime">As at 2:00pm, 15 mins delayed*</span>
        <span id="LatestIntradayData_lblLastTrade">217.60</span>'''
        now = datetime(2026,11,9,12,20,tzinfo=timezone.utc)
        quote = parse_quote(raw, now, now)
        self.assertEqual(quote['source_time'], '2026-11-09T14:00:00+02:00')
        self.assertEqual(quote['last'], '217.60')
        for changed in (raw.replace(b'>MTN<', b'>VOD<'),
                        raw.replace(b'Mon 9 Nov 2026', b'Fri 6 Nov 2026'),
                        raw.replace(b'2:00pm', b'2:19pm'),
                        raw.replace(b'15 mins delayed', b'live')):
            with self.assertRaises(ValueError): parse_quote(changed, now, now)
        with self.assertRaises(ValueError): parse_quote(raw, now, now-timedelta(days=1))
