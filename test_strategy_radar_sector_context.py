import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from application.strategy_radar.sector_context import sector_context

NOW = datetime(2026, 11, 9, 18, tzinfo=timezone.utc)


class Store:
    def get(self, key):
        return {'instrument': key, 'sector': 'Telecommunications', 'benchmark': 'ETF_STX40'} if key == 'MTN' else None


class Service:
    def __init__(self, root):
        self.root = Path(root)
        self.folder = self.root / 'cache'
        self.store = Store()
    def clock(self): return NOW


def write(service, key, values=(100, 105), state='SINGLE_SOURCE', acquired='2026-11-09T10:00:00+00:00', days=('2026-11-05','2026-11-06')):
    folder = service.folder / 'daily-cache'
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{'session': day, 'fields': {'close': {'value': value, 'source':'YAHOO',
             'state':state, 'acquired_at':acquired}}} for day, value in zip(days, values)]
    (folder / (key + '.json')).write_text(json.dumps({'daily':{'history':{'rows':rows}}}))


class SectorContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Service(self.temp.name)
        patcher = patch('application.strategy_radar.sector_context.mappings', return_value={'MTN':'MTN','VOD':'VOD'})
        patcher.start(); self.addCleanup(patcher.stop)

    def test_partial_coverage_and_generic_benchmark_not_sector_proxy(self):
        write(self.service, 'MTN'); write(self.service, 'ETF_STX40', (100, 101))
        result = sector_context(self.service, 'MTN')
        self.assertEqual(result['state'], 'PARTIAL')
        self.assertEqual(result['coverage'], {'qualified':1, 'total':2})
        self.assertEqual(result['breadth'], {'advancers':1,'decliners':0,'unchanged':0})
        self.assertIsNone(result['sector_proxy'])
        self.assertIsNone(result['relative_percentage_points'])
        self.assertIsNotNone(result['broad_benchmark'])
        self.assertEqual(result['qualified_members'][0]['observations'][1]['source'], 'YAHOO')

    def test_conflicting_future_or_missing_closes_not_counted(self):
        write(self.service, 'MTN', state='CONFLICT'); write(self.service, 'VOD', acquired='2026-11-10T10:00:00+00:00')
        result = sector_context(self.service, 'MTN')
        self.assertEqual(result['coverage']['qualified'], 0)
        self.assertIsNone(result['breadth'])
        self.assertEqual(result['state'], 'UNAVAILABLE')

    def test_complete_and_calendar_unknown(self):
        write(self.service, 'MTN'); write(self.service, 'VOD', (100, 95))
        result = sector_context(self.service, 'MTN')
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(result['breadth'], {'advancers':1,'decliners':1,'unchanged':0})
        unknown_calendar=sector_context(self.service, 'MTN', now=datetime(2027,2,1,tzinfo=timezone.utc))
        self.assertEqual(unknown_calendar['breadth'], {'advancers':1,'decliners':1,'unchanged':0})
        self.assertFalse(unknown_calendar['calendar_verified'])
        self.assertIn('EXCHANGE_CALENDAR_UNVERIFIED', unknown_calendar['limitations'])

    def test_stale_pair_retained_and_identified(self):
        write(self.service, 'MTN', days=('2026-11-03','2026-11-05'))
        result = sector_context(self.service, 'MTN')
        self.assertEqual(result['state'], 'STALE')
        self.assertEqual((result['reference_session'], result['session']), ('2026-11-03', '2026-11-05'))
        self.assertEqual(result['expected_session'], '2026-11-06')
        self.assertTrue(result['stale'])
        self.assertEqual(result['coverage'], {'qualified':1,'total':2})

    def test_conflicting_selected_closes_are_separate_provisional_breadth(self):
        write(self.service, 'MTN', state='CONFLICT_NO_CONSENSUS')
        path=self.service.folder/'daily-cache'/'MTN.json'
        payload=json.loads(path.read_text())
        payload['daily']['history']['rows'][-1]['fields']['close']['alternatives']=[{'source':'SHAREDATA','value':99,'acquired_at':'2026-11-09T09:00:00+00:00'}, {'source':'FUTURE','value':101,'acquired_at':'2026-11-10T09:00:00+00:00'}]
        path.write_text(json.dumps(payload))
        write(self.service, 'VOD', (100,95))
        result = sector_context(self.service, 'MTN')
        self.assertEqual(result['state'], 'PROVISIONAL')
        self.assertEqual(result['coverage'], {'qualified':1,'total':2,'provisional':1})
        self.assertEqual(result['breadth'], {'advancers':0,'decliners':1,'unchanged':0})
        self.assertEqual(result['provisional_breadth']['advancers'], 1)
        self.assertEqual(result['provisional_breadth']['decliners'], 1)
        self.assertEqual(result['provisional_members'][0]['observations'][1]['alternatives'][0]['source'], 'SHAREDATA')
        self.assertEqual(len(result['provisional_members'][0]['observations'][1]['alternatives']), 1)
        self.assertEqual(result['provisional_members'][0]['observations'][1]['alternatives_omitted_unqualified'], 1)
        self.assertIn('NOT_CONSENSUS', result['provisional_breadth']['basis'])

    def test_invalid_alternatives_sources_and_noncanonical_dates_are_excluded(self):
        from application.strategy_radar.sector_context import _alternatives, _latest_retained_pair
        valid = {'source':'YAHOO', 'value':99, 'acquired_at':'2026-11-09T10:00:00+00:00'}
        bad = [dict(valid, source=' '), dict(valid, source=1), dict(valid, value=0),
               dict(valid, value=-1), dict(valid, value='NaN'), dict(valid, value='bad')]
        accepted, omitted = _alternatives({'alternatives':[valid]+bad}, '2026-11-06', NOW)
        self.assertEqual(accepted, [valid]); self.assertEqual(omitted, len(bad))
        write(self.service, 'MTN', days=('20261105', '2026-11-06'))
        self.assertIsNone(_latest_retained_pair(self.service.folder, ['MTN'], NOW, '2026-11-06'))
        write(self.service, 'MTN')
        path = self.service.folder/'daily-cache'/'MTN.json'
        payload = json.loads(path.read_text())
        payload['daily']['history']['rows'][0]['fields']['close']['source'] = ' '
        path.write_text(json.dumps(payload))
        self.assertIsNone(_latest_retained_pair(self.service.folder, ['MTN'], NOW, '2026-11-06'))

    def test_missing_fields_do_not_block_another_member_or_invent_prices(self):
        write(self.service, 'MTN', values=(100,None))
        write(self.service, 'VOD', values=(100,95))
        result=sector_context(self.service, 'MTN')
        self.assertEqual(result['coverage']['qualified'],1)
        self.assertEqual(result['qualified_members'][0]['instrument'],'VOD')
        self.assertEqual(result['breadth'], {'advancers':0,'decliners':1,'unchanged':0})

    def test_mapping_mismatch_and_naive_clock(self):
        with patch('application.strategy_radar.sector_context.mappings', return_value={'VOD':'VOD'}):
            self.assertIn('INSTRUMENT_MAPPING_OR_SECTOR_MISMATCH', sector_context(self.service, 'MTN')['limitations'])
        with self.assertRaises(ValueError): sector_context(self.service,'MTN',now=datetime(2026,11,9))


if __name__ == '__main__': unittest.main()
