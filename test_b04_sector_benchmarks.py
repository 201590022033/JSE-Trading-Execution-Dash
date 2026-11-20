import unittest

from application.backtest_lab.zebra_field_windows import constructed_sector_proxy, research_benchmarks
from application.opportunities.session_freshness import next_session
from scripts.backtest_lab_zebra_v2 import build


def closes(days, prices):
    return [{'session': day, 'close': price} for day, price in zip(days, prices)]


def replay_fixture(instruments):
    days = ['2026-01-02']
    while len(days) < 65:
        days.append(next_session(days[-1]))
    data = {}
    for n, (instrument, sector) in enumerate(instruments.items()):
        rows = []
        for i, day in enumerate(days):
            close = 100 + n + i * .08 if i != 59 else 110 + n
            rows.append({'session': day, 'open': close - .1, 'high': close + .2,
                         'low': close - .2, 'close': close, 'volume': 2000 if i == 59 else 1000,
                         'fields': {'close': {'value': close, 'source': 'IRESS', 'source_sha256': 'a' * 64,
                                              'acquired_at': '2026-11-05T00:00:00+00:00'}}})
        data[instrument] = {'asset_class': 'cash_equity', 'sector': sector, 'rows': rows}
    for instrument in ('ETF_STX40', 'ETF_STXRES', 'ETF_STXFIN', 'ETF_STXIND'):
        data[instrument] = {'asset_class': 'index_etf', 'rows': closes(days, [100 + i * .1 for i in range(len(days))])}
    return {'instruments': data}


LEGACY_FIXTURE = {
    'ABSPJ': 'Financials', 'BTI': 'Consumer', 'FSR': 'Financials',
    'NEWGOLD': 'Funds', 'SASOL': 'Energy',
}


class SectorBenchmarkTests(unittest.TestCase):
    def test_missing_member_is_dropped_without_bridging_its_missing_close(self):
        dates = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05']
        history = {
            'VOD': {day: {'value': value} for day, value in zip(dates, (100, 110, 121, 133.1))},
            'OTHER': {day: {'value': value} for day, value in zip(dates, (100, 120, None, 150)) if value is not None},
        }
        rows = constructed_sector_proxy(dates, history)
        self.assertEqual(rows[dates[0]]['close'], 100)
        self.assertAlmostEqual(rows[dates[1]]['close'], 115)
        for day in dates[2:]:
            self.assertEqual(rows[day]['members'], ['VOD'])
            self.assertEqual(rows[day]['data_quality'], 'PARTIAL')
        self.assertAlmostEqual(rows[dates[3]]['close'], 139.15)

    def test_benchmark_policy_order_and_prefix_invariance(self):
        dates = ['2026-11-02', '2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06']
        data = {
            'SHPJ': {'sector': 'Financials', 'rows': closes(dates, [100] * 5)},
            'SBK': {'sector': 'Financials', 'rows': closes(dates, [100, 102, 104, None, 110])},
            'ETF_STXFIN': {'rows': closes(dates, [100, 102, None, None, None])},
            'ETF_STX40': {'rows': closes(dates, [100, 101, 102, 103, None])},
        }
        result, _ = research_benchmarks('SHPJ', data, dates)
        self.assertEqual(result[dates[1]]['instrument'], 'ETF_STXFIN')
        self.assertEqual(result[dates[2]]['members'], ['SBK'])
        self.assertEqual(result[dates[3]]['basis'], 'BROAD_MARKET_FALLBACK')
        self.assertEqual(result[dates[4]]['data_quality'], 'NO_DATA')
        data['SBK']['rows'][-1]['close'] = 1000
        prefix, _ = research_benchmarks('SHPJ', data, dates[:3])
        self.assertEqual(prefix, {day: result[day] for day in dates[:3]})

    def test_replay_uses_labelled_broad_etf_for_telecommunications(self):
        run = build(replay_fixture({'MTN': 'Telecommunications', 'VOD': 'Telecommunications'}))
        meta = run['meta']
        for subject in ('MTN', 'VOD'):
            result = meta['sector_benchmarks'][subject]
            self.assertEqual(result['basis'], 'BROAD_MARKET_FALLBACK')
            self.assertEqual(result['instrument'], 'ETF_STX40')
            self.assertIn('Telecommunications benchmark', result['label'])
        self.assertFalse(meta.get('constructed_sector_inputs'))
        trace = run['strategies'][0]['run']
        mtn = [row for row in trace['rejected_bars'] if row['inst'] == 'MTN']
        self.assertTrue(any(c['c'] == 'Benchmark' and c['v'] is not None for row in mtn for c in row['trace']))

    def test_protected_research_fixture_replays_to_prior_bytes(self):
        result = build(replay_fixture(LEGACY_FIXTURE))
        self.assertEqual(result['meta']['config_hash'], 'cbed15d167f0c461f57ea235fc2ca593971674446deec0e7e4ef2e0163720946')
