import unittest
from datetime import datetime, timedelta, timezone

from application.strategy_radar.intraday_indicators import indicator_snapshot, daily_indicator_snapshot
from application.strategy_radar.intraday_store import _session


def records(count=90):
    start = datetime(2026, 11, 18, 7, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        t = start + timedelta(minutes=5*i)
        close = 10000 + i*3 + (i % 7)*4
        rows.append({'instrument': 'VOD', 'source': 'IRESS_VIEWPOINT_TABLE_CSV',
                     'interval_minutes': 5, 'clock_semantics': 'START',
                     'bar_start': t.isoformat(), 'bar_end': (t+timedelta(minutes=5)).isoformat(),
                     'source_timestamp': t.isoformat(), 'received_at': (t+timedelta(minutes=6)).isoformat(),
                     'availability': 'MANUAL', 'unit': 'ZAR_CENTS',
                     'fields': {'open': close, 'high': close+50, 'low': close-50,
                                'close': close, 'volume': None}})
    return rows


class RadarIndicatorTests(unittest.TestCase):
    def test_daily_zebra_uses_receipts_and_excludes_uncompleted_session(self):
        day = datetime(2026, 6, 1, tzinfo=timezone.utc).date()
        rows = []
        while len(rows) < 90:
            if _session(day):
                price = 100 + len(rows) * .1 + (len(rows) % 7) * .03
                fields = {key: {'value': value, 'source': 'ZEBRA_SOURCE',
                                'acquired_at': '2026-11-18T17:01:00+00:00'}
                          for key, value in {'open': price, 'high': price+1,
                                             'low': price-1, 'close': price, 'volume': None}.items()}
                rows.append({'session': day.isoformat(), 'fields': fields})
            day += timedelta(days=1)
        cutoff = '2026-11-19T07:00:00+00:00'
        output = daily_indicator_snapshot({'rows': rows}, as_of=cutoff)
        for name in ('rsi', 'ema', 'stochastic', 'ichimoku'):
            self.assertTrue(output['indicators'][name]['available'], name)
        self.assertEqual(output['latest_inputs']['close']['selected']['source'], 'ZEBRA_SOURCE')
        for detail in rows[-1]['fields'].values():
            detail['acquired_at'] = '2026-11-19T08:00:00+00:00'
        self.assertFalse(daily_indicator_snapshot({'rows': rows}, as_of=cutoff)['indicators']['rsi']['available'])

    def test_price_indicators_work_without_volume(self):
        result = indicator_snapshot(records(), as_of='2026-11-18T16:00:00+00:00')
        for name in ('rsi', 'ema', 'stochastic', 'ichimoku'):
            self.assertTrue(result['indicators'][name]['available'], name)
        self.assertEqual(result['indicators']['rsi']['bars_used'], 90)
        fast_d = result['indicators']['stochastic']['values']['stochastic_d']
        slow_k = result['indicators']['stochastic_14_3_3']['values']['slow_k']
        self.assertAlmostEqual(fast_d, slow_k)

    def test_gap_only_discards_older_window(self):
        rows = records()
        result = indicator_snapshot(rows[:10] + rows[11:], as_of='2026-11-18T16:00:00+00:00')
        self.assertTrue(result['indicators']['rsi']['available'])
        self.assertTrue(result['indicators']['ichimoku']['available'])
        self.assertEqual(result['indicators']['rsi']['bars_used'], 79)

    def test_missing_high_affects_only_ohlc_indicators(self):
        rows = records()
        rows[-1]['fields']['high'] = None
        result = indicator_snapshot(rows, as_of='2026-11-18T16:00:00+00:00')
        self.assertTrue(result['indicators']['rsi']['available'])
        self.assertTrue(result['indicators']['ema']['available'])
        self.assertFalse(result['indicators']['stochastic']['available'])
        self.assertFalse(result['indicators']['ichimoku']['available'])

    def test_future_receipt_does_not_change_snapshot(self):
        rows = records()
        cutoff = datetime.fromisoformat(rows[-2]['received_at'])
        before = indicator_snapshot(rows[:-1], as_of=cutoff)
        self.assertEqual(before, indicator_snapshot(rows, as_of=cutoff))
