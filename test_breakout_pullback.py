"""Deterministic fixtures for the opt-in breakout and pullback research lane."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from application.backtest_lab.observed_history import from_chart
from application.opportunities.session_freshness import next_session
from application.opportunities.swing_technical import snapshot
from application.strategy_radar.breakout_pullback import REFERENCE, Settings, _clock, evaluate, replay_setups
from application.strategy_radar.intraday_indicators import research_wilder_rsi
from domain.backtest.component_engine import Costs
from domain.features.technical import candidate_rsi_wilder
from domain.strategy import DEFAULT_STRATEGY_REGISTRY


FINAL_CLOCK = datetime(2026, 11, 19, tzinfo=timezone.utc)


def sessions(count, start='2026-04-01'):
    days = [start]
    for _ in range(count - 1):
        days.append(next_session(days[-1]))
    return days


def row(day, close, *, low=None, high=None, volume=100, other_volume=200):
    values = {'open': close, 'high': close + .3 if high is None else high,
              'low': close - .35 if low is None else low, 'close': close, 'volume': volume}
    seen = _clock(day).isoformat()
    detail = {key: {'value': value, 'acquired_at': seen, 'source': 'SELECTED',
                    'source_sha256': 'a'*64, 'state': 'SINGLE_SOURCE'} for key, value in values.items()}
    detail['volume']['alternatives'] = [{'value': other_volume, 'acquired_at': seen, 'source': 'OTHER',
                                         'source_sha256': 'b'*64}]
    return {'session': day, **values, 'fields': detail}


def case(*, tail=(), warmup=84):
    days = sessions(warmup + 3 + len(tail))
    share = [row(day, 100.5 if index % 2 else 99.5) for index, day in enumerate(days[:warmup])]
    share.extend((
        row(days[warmup], 104, high=105, low=101.6, volume=140),
        row(days[warmup+1], 100.85, high=101.4, low=100.8, volume=80),
        row(days[warmup+2], 102.6, high=103, low=101.5, volume=120, other_volume=160),
    ))
    share.extend(row(day, close) for day, close in zip(days[warmup+3:], tail))
    return share, [row(day, 100) for day in days]


def observed(share, bench, **kwargs):
    return evaluate('VOD', share, bench, as_of=FINAL_CLOCK, benchmark='ETF_STX40', **kwargs)['observations']


class BreakoutPullbackTests(unittest.TestCase):
    def test_rsi14_uses_frozen_output_and_other_period_is_editable(self):
        closes = [100, 104, 102, 106, 104, 103, 101, 107, 105, 110, 100, 101, 106, 109, 108, 111, 112]
        for length in range(len(closes) + 1):
            self.assertEqual(research_wilder_rsi(closes[:length], 14), candidate_rsi_wilder(closes[:length]).value)
        self.assertAlmostEqual(research_wilder_rsi([100, 104, 102, 103, 101], 2), 37.5)
        self.assertIsNone(research_wilder_rsi([100, 104], 2))
        self.assertEqual(research_wilder_rsi([100, 100, 100], 2), 50)
        share, bench = case()
        base = observed(share, bench)[-1]['rules']['rsi']['value']
        alternative = observed(share, bench, config=replace(Settings(), RSI_PERIOD=7))[-1]['rules']['rsi']['value']
        self.assertNotEqual(base, alternative)

    def test_clean_retest_trigger_and_volume_sensitivity(self):
        share, bench = case()
        breakout, touch, signal = observed(share, bench)[-3:]
        self.assertEqual([item['state'] for item in (breakout, touch, signal)],
                         ['BREAKOUT_SEEN', 'IN_PULLBACK_ZONE', 'TRIGGERED'])
        self.assertEqual(signal['breakout_level'], 100.8)
        self.assertEqual(signal['breakout_date'], breakout['session'])
        self.assertEqual(signal['breakout_bar_high'], 105)
        self.assertEqual(signal['pullback_low'], 100.8)
        self.assertEqual(touch['touch_levels'], ['breakout_level', 'cloud_top'])
        self.assertEqual(signal['volume_source'], 'SELECTED')
        self.assertEqual(signal['alternate_volume']['OTHER'], {'ratio': .8, 'would_flip': True})
        self.assertEqual(signal['components_evaluable'], 5)
        self.assertNotEqual(signal['score'], signal['equal_weight_score'])
        self.assertLess(signal['stop_reference'], signal['pullback_low'])
        self.assertGreater(signal['target_reference'], share[-1]['close'])
        self.assertEqual(DEFAULT_STRATEGY_REGISTRY.resolve(REFERENCE.strategy_profile_id).reference, REFERENCE)
        self.assertNotIn(REFERENCE, [item.reference for item in DEFAULT_STRATEGY_REGISTRY.current_profiles()])
        self.assertEqual(observed(share, bench, touch_mode='PERCENT')[-1]['state'], 'TRIGGERED')

    def test_invalidation_and_last_window_expiry(self):
        share, bench = case(tail=(100, 100, 100))
        share[85] = row(share[85]['session'], 98)
        self.assertEqual(observed(share, bench)[85]['state'], 'INVALIDATED')
        self.assertEqual(observed(share, bench)[85]['score_components']['structure'], 0)
        share, bench = case(tail=(104, 104, 104))
        for index in range(85, 90):
            share[index] = row(share[index]['session'], 104, high=105, low=103.7)
        last = observed(share, bench)[-1]
        self.assertEqual(last['state'], 'EXPIRED')
        self.assertEqual(last['sessions_left'], 0)

    def test_rsi_does_not_block_breakout_second_breakout_is_ignored_and_high_alone_is_insufficient(self):
        share, bench = case()
        day = share[84]['session']
        share[84] = row(day, 120, high=121, low=118)
        share[85] = row(share[85]['session'], 122, high=123, low=121)
        breakout, later, _ = observed(share, bench)[-3:]
        self.assertGreater(breakout['rules']['rsi']['value'], 70)
        self.assertEqual(breakout['state'], 'BREAKOUT_SEEN')
        self.assertEqual(later['rules']['breakout']['state'], 'PASS')
        self.assertEqual(later['breakout_date'], day)
        self.assertEqual(later['breakout_level'], breakout['breakout_level'])
        share, bench = case()
        share[84] = row(day, 100, high=120, low=99)
        observations = observed(share, bench)
        self.assertEqual(observations[84]['state'], 'WATCHING')
        self.assertEqual(observations[85]['state'], 'WATCHING')

    def test_gaps_short_history_and_optional_no_data(self):
        share, bench = case()
        del share[60:62]
        last = observed(share, bench)[-1]
        self.assertEqual(last['state'], 'TRIGGERED')
        self.assertEqual(last['data_quality'], 'GAP_TOLERATED')
        self.assertEqual(len(last['gaps'][0]['missing_sessions']), 2)
        short = observed(share[:10], bench)[-1]
        self.assertTrue(short['low_confidence'])
        self.assertEqual(short['state'], 'WATCHING')
        self.assertEqual(short['rules']['breakout']['state'], 'NO_DATA')
        share, bench = case(warmup=30)
        share[-1]['fields']['volume']['value'] = None
        last = observed(share, [])[-1]
        self.assertEqual(last['state'], 'TRIGGERED')
        self.assertEqual(last['components_evaluable'], 2)
        for name in ('volume', 'cloud', 'relative_strength'):
            self.assertEqual(last['rules'][name]['state'], 'NO_DATA')
            self.assertIsNone(last['score_components']['trend' if name == 'cloud' else name])
        self.assertAlmostEqual(last['score'], 100*(.35*last['score_components']['structure'] +
                                                  .20*last['score_components']['momentum'])/.55)

    def test_prefix_and_later_receipts_cannot_change_prior_results(self):
        share, bench = case(tail=(103, 103, 103, 103))
        earlier = observed(share[:-4], bench[:-4])
        later = observed(share, bench)
        self.assertEqual(earlier, later[:-4])
        revised = deepcopy(share)
        revised[84]['fields']['high']['acquired_at'] = _clock(share[-1]['session']).isoformat()
        self.assertNotIn('high', observed(revised, bench)[84]['input_receipts'])
        observed_retro = observed(revised, bench, retrospective=True)
        self.assertIn('high', observed_retro[84]['input_receipts'])

    def test_engine_integration_and_uncovered_execution(self):
        share, bench = case(tail=(103, 103, 103, 103))
        result = evaluate('VOD', share, bench, as_of=FINAL_CLOCK)
        bars = [{'timestamp': item['session'], **{key: item[key] for key in ('open', 'high', 'low', 'close', 'volume')}}
                for item in share]
        provenance = {'provider': 'SYNTHETIC', 'source_sha256': 'a'*64, 'acquired_at': FINAL_CLOCK.isoformat()}
        manifest = from_chart('VOD', {'bars': bars, 'provenance': provenance})
        args = {'horizon': 3, 'initial_cash': 100000, 'max_notional': 10000, 'risk_budget': 100, 'costs': Costs(fee_bps=8)}
        output = replay_setups(result, manifest, **args)
        self.assertEqual(output['state'], 'RESEARCH_REPLAY')
        self.assertEqual(output['signals'], [f"VOD-{share[86]['session']}"])
        self.assertEqual(output['trades'][0]['entry_session'], share[87]['session'])
        self.assertEqual(output['trades'][0]['strategy_profile_id'], REFERENCE.strategy_profile_id)
        self.assertEqual(output['trades'][0]['reason'], 'HORIZON_CLOSE')
        without_native = from_chart('VOD', {'bars': bars[:87]+bars[88:], 'provenance': provenance})
        refused = replay_setups(result, without_native, **args)
        self.assertEqual(refused['state'], 'REPLAY_INPUT_UNAVAILABLE')
        self.assertEqual(refused['uncovered_sessions'], [share[87]['session']])

    def test_existing_exact_daily_snapshot_matches_master_fixture(self):
        share, bench = case()
        chart = lambda name, items: {'symbol': name, 'interval': '1d', 'currency': 'ZAR',
                                     'bars': [{'timestamp': item['session'], **{k: item[k] for k in
                                               ('open', 'high', 'low', 'close', 'volume')}} for item in items]}
        result = snapshot(chart('VOD', share), evaluated_at=_clock(share[-1]['session']),
                          benchmark_chart=chart('ETF_STX40', bench), feature_profile_version='1.1.2')
        self.assertEqual(result['state'], 'AVAILABLE')
        digest = sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '7595599222ad84d26c877a8409d80e0ddb50b23667b28f5c3244613936e2439d')
