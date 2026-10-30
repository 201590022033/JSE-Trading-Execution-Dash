from datetime import datetime, timezone
import unittest
from application.opportunities.session_freshness import latest_expected_session, current_chart, daily_clock_allowed


def now(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class SessionFreshnessTests(unittest.TestCase):
    def test_weekend_and_public_holiday_preserve_last_session(self):
        # Good Friday and Easter Monday: Thursday remains the latest close.
        instant = now('2026-04-07T06:00:00')
        self.assertEqual(latest_expected_session(instant), '2026-04-02')
        chart = {'provenance': {'acquired_at': '2026-04-02T15:30:00+00:00'},
                 'bars': [{'timestamp': '2026-04-02'}]}
        self.assertTrue(current_chart(chart, instant))
        self.assertTrue(daily_clock_allowed(now('2026-04-03T00:00:00'), instant, 4*86400))

    def test_intraday_yesterday_valid_but_missing_yesterday_stale(self):
        instant = now('2026-10-30T10:00:00')
        self.assertEqual(latest_expected_session(instant), '2026-10-29')
        chart = {'provenance': {'acquired_at': '2026-10-29T18:00:00+00:00'},
                 'bars': [{'timestamp': '2026-10-29'}, {'timestamp': '2026-10-30'}]}
        self.assertTrue(current_chart(chart, instant))
        chart['bars'] = [{'timestamp': '2026-10-28'}]
        self.assertFalse(current_chart(chart, instant))
        # At 01:00 SAST the previous day's bar has not reached the retained
        # next-UTC-day availability convention yet.
        self.assertEqual(latest_expected_session(now('2026-10-29T23:00:00')), '2026-10-28')

    def test_future_capture_and_shorter_budget_never_bypassed(self):
        instant = now('2026-10-30T10:00:00')
        chart = {'provenance': {'acquired_at': '2026-10-30T11:00:00+00:00'}, 'bars': [{'timestamp':'2026-10-29'}]}
        self.assertFalse(current_chart(chart, instant))
        self.assertFalse(daily_clock_allowed(now('2026-10-30T00:00:00'), instant, 3600))

    def test_unknown_year_does_not_invent_calendar(self):
        self.assertIsNone(latest_expected_session(now('2027-02-04T10:00:00')))

    def test_stale_iress_does_not_erase_current_ost_close(self):
        from application.opportunities.supplemental_data import current_research_charts
        instant = now('2026-10-30T10:00:00')
        primary = {'provenance': {'provider':'OST', 'acquired_at':'2026-10-29T20:00:00+00:00'},
                   'bars':[{'timestamp':'2026-10-29', 'open':None, 'close':10}]}
        alternative = {'provenance': {'provider':'IRESS', 'acquired_at':'2026-10-28T20:00:00+00:00'},
                       'bars':[{'timestamp':'2026-10-28', 'open':9, 'close':10}]}
        result = current_research_charts({'schema':'local-swing-dataset-v3',
                 'charts':{'SASOL':primary}, 'research_charts':{'SASOL':alternative}}, instant)
        self.assertEqual(result['SASOL']['provenance']['provider'],'OST')
        self.assertIsNone(result['SASOL']['bars'][0]['open'])

    def test_hlc_atr_remains_available_without_open_and_stops_at_bad_row(self):
        from application.opportunities.supplemental_data import hlc_research
        from datetime import timedelta
        start = now('2026-09-01T00:00:00')
        bars = [{'timestamp':(start+timedelta(days=i)).date().isoformat(),
                 'open':None, 'high':11, 'low':9, 'close':10} for i in range(30)]
        result = hlc_research({'bars':bars}, now('2026-10-30T10:00:00'))
        self.assertEqual(result['atr14_wilder'], 2)
        self.assertFalse(result['opening_price_invented'])
        bars[-1]['low'] = 12
        self.assertIsNone(hlc_research({'bars':bars}, now('2026-10-30T10:00:00'))['atr14_wilder'])


if __name__ == '__main__':
    unittest.main()
