"""Boundary fixtures: source clocks and unavailable data are not signals."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from application.strategy_radar.contracts import (Availability, Bar, FieldObservation,
    ProductValue, Quote, RuleState, RuleTrace, StrategyVersion, TradePlan, Watch, Alert)


class RadarContractsTests(unittest.TestCase):
    def setUp(self):
        self.source = datetime(2026, 11, 6, 8, tzinfo=timezone.utc)
        self.receipt = datetime(2026, 11, 6, 8, 15, tzinfo=timezone.utc)
        self.missing = FieldObservation(None, None, Availability.MISSING)
        self.delayed = FieldObservation(Decimal('112.34'), 'ZAR', Availability.DELAYED,
                                        'provider-A', self.source, self.receipt, 900)
        self.historical = FieldObservation(Decimal('111.00'), 'ZAR', Availability.HISTORICAL,
                                           'provider-B', None, self.receipt)
        self.strategy = StrategyVersion('swing', 'v1', '1d')

    def test_quote_does_not_turn_missing_or_historical_into_live(self):
        quote = Quote('SOL', self.missing, self.delayed, self.historical)
        self.assertIsNone(quote.bid.value)
        self.assertEqual(quote.ask.delay_seconds, 900)
        self.assertEqual(quote.ask.source_time, self.source)
        self.assertEqual(quote.ask.received_at, self.receipt)
        self.assertEqual(quote.last.availability, Availability.HISTORICAL)
        self.assertIsNone(quote.last.source_time)

    def test_partial_mixed_source_bar_retains_each_field(self):
        bar = Bar('SOL', '1d', self.source, self.receipt, self.missing,
                  self.historical, self.missing, self.delayed, self.missing)
        self.assertIsNone(bar.open.value)
        self.assertEqual(bar.high.source, 'provider-B')
        self.assertEqual(bar.close.source, 'provider-A')
        self.assertIsNone(bar.volume.value)

    def test_missing_and_naive_clocks_are_rejected(self):
        with self.assertRaises(ValueError):
            FieldObservation(Decimal('1'), 'ZAR', Availability.MISSING)
        with self.assertRaises(ValueError):
            FieldObservation(Decimal('1'), 'ZAR', Availability.LIVE, 'x', datetime(2026, 1, 1), self.receipt)
        with self.assertRaises(ValueError):
            FieldObservation(Decimal('1'), 'ZAR', Availability.DELAYED, 'x', None, self.receipt, -1)

    def test_unverified_product_units_and_unknown_rule_stay_explicit(self):
        unknown = ProductValue(None, None)
        with self.assertRaises(ValueError):
            ProductValue(Decimal('1234'), 'cents', True)
        plan = TradePlan('SOL', 'CFD', self.strategy, unknown, unknown, unknown, unknown, unknown)
        trace = RuleTrace('volume', RuleState.UNKNOWN, True, (self.missing,))
        watch = Watch('SOL', self.strategy, True, 'PIN', self.receipt)
        alert = Alert('a', watch.instrument, watch.strategy, 'DEVELOPING', self.receipt, (trace,))
        self.assertFalse(plan.entry.mapping_verified)
        self.assertEqual(alert.trace[0].state, RuleState.UNKNOWN)


if __name__ == '__main__':
    unittest.main()
