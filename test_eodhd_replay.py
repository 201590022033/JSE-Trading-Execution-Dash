import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from scripts.backtest_lab_run import add_eodhd_histories, append_eodhd_benchmark, demo
from application.opportunities.session_freshness import next_session
from application.backtest_lab.observed_history import CashListedETF, from_chart
from domain.backtest.engine import Signal, replay


class EodhdReplayTests(unittest.TestCase):
    def test_eodhd_handover_extends_instead_of_replacing_longer_history(self):
        charts, _=demo(); rows=charts['SOL']
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'IRESS','source_sha256':'c'*64,
                            'acquired_at':'2026-10-30T00:00:00+00:00'}})
        last=next_session(rows[-1]['timestamp'])
        # The benchmark bounds are extended using a genuine close observation.
        charts['ETF_STX40'].append({**charts['ETF_STX40'][-1],'timestamp':last})
        data=[{'session':r['timestamp'],**{k:r[k] for k in ('open','high','low','close','volume')}} for r in rows[-60:]]
        data.append({'session':last,'open':100,'high':101,'low':99,'close':100,'volume':1000})
        source={'source_sha256':'a'*64,'raw_sha256':'b'*64,'acquired_at':'2026-10-30T00:00:00+00:00','rows':data}
        with patch('application.opportunities.zebra_instruments.mappings',return_value={'SOL':'SOL'}), \
             patch('scripts.capture_eodhd_history.load_eodhd_history',return_value=source), \
             patch('application.opportunities.session_freshness.next_session',side_effect=lambda day:last if day==rows[-1]['timestamp'] else None):
            charts, manifests, info=add_eodhd_histories(charts,[manifest],'test/eodhd')
        self.assertEqual(len(charts['SOL']),151)
        self.assertEqual(info['SOL']['state'],'REPLAY_HISTORY_EXTENDED')
        self.assertEqual(manifests[0].supplemental_sources[-1]['provider'],'EODHD')

    def test_etf_adapter_requires_correct_product_and_currency(self):
        _, manifests=demo(); adapter=CashListedETF()
        adapter.validate(replace(manifests[0],product='ETF'))
        with self.assertRaises(ValueError): adapter.validate(manifests[0])
        with self.assertRaises(ValueError): adapter.validate(replace(manifests[0],product='ETF',currency='USD'))

    def test_etf_replay_uses_cash_adapter_and_records_trade(self):
        _, manifests=demo(); fund=replace(manifests[0], product='ETF')
        bar=fund.bars[60]
        signal=Signal('fund-test',fund.instrument,bar.session,bar.available_at+timedelta(seconds=1),
                      bar.close/2,Decimal('100000'),Decimal('10000'),horizon=3)
        result=replay([fund],[signal],as_of=fund.bars[-1].available_at+timedelta(days=8),
                      initial_cash=Decimal('1000000'),adapters={fund.instrument:CashListedETF()})
        self.assertEqual(len(result['trades']),1)

    def test_agoge_history_retains_etf_identity(self):
        charts, manifests=demo(); rows=charts['NPN']
        source={'source_sha256':'a'*64,'raw_sha256':'b'*64,'acquired_at':'2026-10-30T00:00:00+00:00',
                'rows':[{'session':r['timestamp'],**{k:r[k] for k in ('open','high','low','close','volume')}} for r in rows]}
        with patch('application.opportunities.zebra_instruments.mappings',return_value={'AGOGE':'AGOGE'}), \
             patch('scripts.capture_eodhd_history.load_eodhd_history',return_value=source), \
             patch('application.opportunities.session_freshness.next_session',return_value=None):
            _, manifests, info=add_eodhd_histories(charts,manifests,'test/eodhd')
        self.assertEqual(next(m for m in manifests if m.instrument=='AGOGE').product,'ETF')
        self.assertEqual(info['AGOGE']['product'],'ETF')

    def test_benchmark_extension_keeps_close_only_and_records_receipt(self):
        charts, _ = demo(); existing=charts['ETF_STX40']; last=existing[-1]
        day=next_session(last['timestamp'])
        source={'source_sha256':'a'*64,'raw_sha256':'b'*64,'acquired_at':'2026-10-30T00:00:00+00:00',
                'rows':[{'session':last['timestamp'],'close':last['close']},{'session':day,'close':'123'}]}
        with patch('scripts.capture_eodhd_history.load_eodhd_history',return_value=source):
            charts, provenance=append_eodhd_benchmark(charts,{'provider':'OST'},'test/eodhd')
        self.assertEqual(charts['ETF_STX40'][-1]['timestamp'],day)
        self.assertIsNone(charts['ETF_STX40'][-1]['open'])
        self.assertEqual(provenance['supplemental_sources'][-1]['raw_sha256'],'b'*64)

    def test_complete_eodhd_history_is_used_with_receipt(self):
        charts, manifests = demo()
        rows = charts.pop('NPN')
        manifests = [m for m in manifests if m.instrument != 'NPN']
        source = {'source_sha256':'a'*64, 'raw_sha256':'b'*64, 'acquired_at':'2026-10-30T00:00:00+00:00',
                  'rows':[{'session':r['timestamp'], **{k:r[k] for k in ('open','high','low','close','volume')}} for r in rows]}
        with patch('application.opportunities.zebra_instruments.mappings',return_value={'NPN':'NPN'}), \
             patch('scripts.capture_eodhd_history.load_eodhd_history',return_value=source), \
             patch('application.opportunities.session_freshness.next_session',return_value=None):
            charts, manifests, diagnostics = add_eodhd_histories(charts,manifests,'test/eodhd')
        self.assertEqual(len(charts['NPN']),150)
        self.assertEqual(next(m for m in manifests if m.instrument=='NPN').provider,'EODHD')
        self.assertEqual(diagnostics['NPN']['raw_sha256'],'b'*64)
        self.assertEqual(diagnostics['NPN']['state'],'REPLAY_HISTORY_SELECTED')

    def test_damaged_or_missing_capture_does_not_replace_existing_history(self):
        charts, manifests = demo(); original=charts['SOL']
        with patch('application.opportunities.zebra_instruments.mappings',return_value={'SOL':'SOL'}), \
             patch('scripts.capture_eodhd_history.load_eodhd_history',side_effect=ValueError('bad hash')):
            charts, manifests, diagnostics = add_eodhd_histories(charts,manifests,'test/eodhd')
        self.assertEqual(charts['SOL'],original)
        self.assertEqual(diagnostics,{})


if __name__ == '__main__': unittest.main()
