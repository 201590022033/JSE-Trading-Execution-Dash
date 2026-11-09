import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from application.strategy_radar.quotes import QuoteCandidate, QuoteKind, select_quote


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)

    def c(self, **kw):
        args = dict(instrument='SOL', provider='a', source_time=self.now-timedelta(seconds=60),
                    received_at=self.now-timedelta(seconds=30), kind=QuoteKind.DELAYED,
                    delay_seconds=60, unit='ZAR_CENTS', last=D('12345'))
        args.update(kw)
        return QuoteCandidate(**args)

    def test_conversion_field_lineage_and_conflict(self):
        a = self.c(bid=D('12300'), last=D('12345'), revision='1')
        b = self.c(provider='b', unit='ZAR', bid=None, ask=D('124.00'), last=D('124'), revision='2')
        out = select_quote('SOL', [b,a], self.now)
        self.assertEqual(out['fields']['bid']['selected']['value'], '123')
        self.assertEqual(out['fields']['ask']['selected']['provider'], 'b')
        self.assertTrue(out['fields']['last']['conflict'])
        self.assertEqual(len(out['fields']['last']['candidates']), 2)
        self.assertEqual(out['fields']['bid']['selected']['raw_unit'], 'ZAR_CENTS')
        self.assertIsNone(out['fields']['bid']['selected']['source_ref'])
        self.assertEqual(select_quote('SOL', [a,b], self.now),out)

    def test_freshness_never_invents_live(self):
        historical = self.c(kind=QuoteKind.HISTORICAL, source_time=None, delay_seconds=None)
        self.assertEqual(select_quote('SOL',[historical],self.now)['fields']['last']['selected']['kind'],'HISTORICAL')
        unknown = self.c(kind=QuoteKind.LIVE, source_time=None, delay_seconds=0)
        self.assertEqual(select_quote('SOL',[unknown],self.now)['fields']['last']['selected']['kind'],'UNKNOWN')
        unknown_delay = self.c(kind=QuoteKind.LIVE, delay_seconds=None)
        self.assertEqual(select_quote('SOL',[unknown_delay],self.now)['fields']['last']['selected']['kind'],'UNKNOWN')
        stale = self.c(source_time=self.now-timedelta(hours=1), received_at=self.now, delay_seconds=None)
        selected = select_quote('SOL',[stale],self.now)['fields']['last']['selected']
        self.assertEqual(selected['kind'],'STALE')
        self.assertEqual(selected['source_age_seconds'],3600)
        self.assertEqual(selected['receipt_age_seconds'],0)
        manual = self.c(kind=QuoteKind.MANUAL, source_time=None, delay_seconds=None)
        self.assertEqual(select_quote('SOL',[manual],self.now)['fields']['last']['selected']['kind'],'MANUAL')
        live = self.c(kind=QuoteKind.LIVE, delay_seconds=0)
        self.assertEqual(select_quote('SOL',[historical,live],self.now)['fields']['last']['selected']['kind'],'LIVE')
        self.assertIsNone(select_quote('SOL',[],self.now)['fields']['bid']['selected'])

    def test_reject_invalid_units_prices_and_clocks(self):
        for changes in ({'unit':'USD'}, {'last':D('NaN')}, {'last':D('-1')},
                        {'instrument':'../x'}, {'delay_seconds':-1},
                        {'bid':D('14000'),'ask':D('13000')},
                        {'source_time':self.now+timedelta(seconds=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.c(**changes)
        future = self.c(source_time=self.now, received_at=self.now+timedelta(seconds=1))
        with self.assertRaises(ValueError):
            select_quote('SOL',[future],self.now)
        with self.assertRaises(ValueError):
            select_quote('BTI',[self.c()],self.now)

if __name__ == '__main__':
    unittest.main()
