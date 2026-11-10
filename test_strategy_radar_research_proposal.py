import unittest
from datetime import datetime

from application.strategy_radar.research_proposal import research_proposal
import test_strategy_radar_swing as swing_fixture


class ResearchProposalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = swing_fixture.SwingRadarTests('test_real_daily_rules_work_without_intraday')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        for row in self.fixture.rows:
            for field in row['fields'].values():
                field['source'] = 'FIXTURE_SOURCE'
        self.fixture.write()
        self.service = self.fixture.service

    def get(self, instrument='MTN', product='CASH_SHARE'):
        return research_proposal(self.service, instrument, product, now=swing_fixture.NOW)

    def test_sourced_geometry_is_historical_not_fill_or_order(self):
        result = self.get()
        self.assertEqual(result['state'], 'HISTORICAL_REFERENCE')
        self.assertEqual(result['session'], '2026-11-06')
        self.assertEqual(result['strategy_version'], '1.1.0')
        self.assertEqual(result['source_fields']['close']['sources'], ['FIXTURE_SOURCE'])
        self.assertEqual(len(result['source_sha256']), 64)
        self.assertLess(result['stop_reference'], result['entry_reference'])
        self.assertAlmostEqual(result['target_reference'] - result['entry_reference'],
                               2 * (result['entry_reference'] - result['stop_reference']))
        self.assertIsNone(result['costs'])
        self.assertIsNone(result['broker_input'])
        self.assertNotIn('ALIGNED_BENCHMARK_UNAVAILABLE', result['missing'])
        self.assertIn('Benchmark is not evaluated by this geometry-only proposal', result['limitations'])
        self.assertFalse(result['live_execution'])

    def test_missing_source_conflict_stale_and_product_are_explicit(self):
        self.assertEqual(self.get(product='CFD')['reason'], 'PRODUCT_UNSUPPORTED')
        self.assertEqual(self.get(instrument='../MTN')['reason'], 'WATCH_IDENTITY_UNAVAILABLE')
        self.fixture.rows[-1]['fields']['close'].pop('source')
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['session'], '2026-11-05')
        self.assertEqual(result['freshness'], 'STALE')
        self.fixture.rows[-1]['fields']['close']['source'] = 'FIXTURE_SOURCE'
        self.fixture.rows[-1]['fields']['high']['state'] = 'CONFLICT_NO_CONSENSUS'
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'CONDITIONAL_REFERENCE')
        self.assertTrue(result['source_fields']['high']['conflicts'])
        self.assertNotIn('ALIGNED_BENCHMARK_UNAVAILABLE', result['missing'])
        self.fixture.write(latest='2026-11-05')
        self.assertEqual(self.get()['freshness'], 'STALE')

    def test_future_receipt_and_naive_clock_are_rejected(self):
        self.fixture.rows[-1]['fields']['close']['acquired_at'] = '2026-11-10T00:00:00+00:00'
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['session'], '2026-11-05')
        self.assertEqual(result['freshness'], 'STALE')
        with self.assertRaises(ValueError):
            research_proposal(self.service, 'MTN', 'CASH_SHARE', now=datetime(2026, 11, 9))

    def test_missing_open_does_not_block_hlc_geometry(self):
        for row in self.fixture.rows:
            row['fields']['open']['value'] = None
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'HISTORICAL_REFERENCE')
        self.assertIsNotNone(result['stop_reference'])
        self.assertNotIn('open', result['source_fields'])

    def test_missing_low_keeps_close_without_inventing_geometry(self):
        self.fixture.rows[-3]['fields']['low']['value'] = None
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertEqual(result['session'], '2026-11-06')
        self.assertIsNotNone(result['entry_reference'])
        self.assertIsNone(result['stop_reference'])
        self.assertIsNone(result['target_reference'])

    def test_older_incomplete_field_uses_disclosed_contiguous_suffix(self):
        self.fixture.rows[-20]['fields']['high']['value'] = None
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'HISTORICAL_REFERENCE')
        self.assertEqual(result['qualified_hlc_sessions'], 19)
        self.assertIn('Wilder ATR initialized on the displayed contiguous qualified HLC window', result['assumptions'])

    def test_missing_session_is_not_compressed_into_atr_window(self):
        self.fixture.rows.pop(-3)
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertEqual(result['qualified_hlc_sessions'], 2)
        self.assertIsNone(result['stop_reference'])

    def test_bad_old_rows_are_quarantined_not_global_block(self):
        self.fixture.rows.insert(0, {'session': 'bad-date', 'fields': {}})
        self.fixture.rows.insert(2, dict(self.fixture.rows[1]))
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'HISTORICAL_REFERENCE')
        self.assertEqual(result['data_quality']['invalid_session_rows'], 1)
        self.assertEqual(len(result['data_quality']['duplicate_sessions']), 1)
        self.assertEqual(result['qualified_hlc_sessions'], len(self.fixture.rows)-3)

    def test_recent_duplicate_stops_suffix_and_is_never_selected(self):
        duplicated = self.fixture.rows[-3]['session']
        self.fixture.rows.insert(-2, dict(self.fixture.rows[-3]))
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertEqual(result['qualified_hlc_sessions'], 2)
        self.assertEqual(result['data_quality']['duplicate_sessions'], [duplicated])
        self.assertIsNone(result['stop_reference'])

    def test_duplicate_latest_falls_back_to_older_labelled_reference(self):
        duplicated = self.fixture.rows[-1]['session']
        self.fixture.rows.append(dict(self.fixture.rows[-1]))
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['session'], '2026-11-05')
        self.assertEqual(result['freshness'], 'STALE')
        self.assertEqual(result['data_quality']['duplicate_sessions'], [duplicated])

    def test_invalid_declared_latest_is_conditional_not_global_block(self):
        self.fixture.write(latest='not-a-date')
        result = self.get()
        self.assertEqual(result['state'], 'CONDITIONAL_REFERENCE')
        self.assertTrue(result['data_quality']['invalid_declared_latest'])
        self.assertIn('Cache latest-session metadata is invalid; selected date is conditional', result['limitations'])
        self.assertFalse(any('conflicting fields' in item for item in result['limitations']))

    def test_conflict_preserves_selected_value_and_alternative(self):
        field = self.fixture.rows[-1]['fields']['close']
        field['state'] = 'CONFLICT_NO_CONSENSUS'
        field['alternatives'] = [{'value': 77, 'source': 'OTHER', 'acquired_at': '2026-11-09T11:00:00+00:00'}]
        field['source_sha256'] = 'a' * 64
        field['field_source_sha256'] = 'b' * 64
        field['upstream_independence'] = 'NOT_ESTABLISHED'
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'CONDITIONAL_REFERENCE')
        self.assertEqual(result['entry_reference'], field['value'])
        self.assertEqual(result['source_fields']['close']['conflicts'][-1]['alternatives'][0]['value'], 77)
        selected = result['source_fields']['close']['observations'][-1]
        self.assertEqual(selected['value'], field['value'])
        self.assertEqual(selected['source_sha256'], 'a' * 64)
        self.assertEqual(selected['field_source_sha256'], 'b' * 64)
        self.assertEqual(selected['upstream_independence'], 'NOT_ESTABLISHED')
        self.assertIsNone(result['source_fields']['close']['observations'][-2]['upstream_independence'])

    def test_conflict_excludes_future_and_unqualified_alternatives(self):
        field = self.fixture.rows[-1]['fields']['close']
        field['state'] = 'CONFLICT_NO_CONSENSUS'
        field['alternatives'] = [
            {'value': 77, 'source': 'KNOWN', 'acquired_at': '2026-11-09T11:00:00+00:00'},
            {'value': 88, 'source': 'FUTURE', 'acquired_at': '2026-11-10T11:00:00+00:00'},
            {'value': 89, 'source': 'NAIVE', 'acquired_at': '2026-11-09T11:00:00'},
            {'value': 90, 'source': 'EARLY', 'acquired_at': '2026-11-06T10:00:00+00:00'},
            {'value': float('nan'), 'source': 'NONFINITE', 'acquired_at': '2026-11-09T11:00:00+00:00'},
            {'value': 91, 'source': '', 'acquired_at': '2026-11-09T11:00:00+00:00'},
        ]
        self.fixture.write()
        result = self.get()
        self.assertEqual(result['state'], 'CONDITIONAL_REFERENCE')
        conflict = result['source_fields']['close']['conflicts'][-1]
        self.assertEqual([candidate['source'] for candidate in conflict['alternatives']], ['KNOWN'])
        self.assertEqual(conflict['alternatives_omitted_count'], 5)

    def test_receipt_range_uses_absolute_time_not_string_order(self):
        self.fixture.rows[-1]['fields']['close']['acquired_at'] = '2026-11-09T11:00:00+02:00'
        self.fixture.rows[-2]['fields']['close']['acquired_at'] = '2026-11-09T08:30:00+00:00'
        self.fixture.write()
        # Previous-session receipt can be accepted only after that session ended.
        result = self.get()
        self.assertEqual(result['state'], 'HISTORICAL_REFERENCE')
        self.assertEqual(result['source_fields']['close']['first_received_at'], '2026-11-09T08:30:00+00:00')
        self.assertEqual(result['source_fields']['close']['last_received_at'], '2026-11-09T10:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
