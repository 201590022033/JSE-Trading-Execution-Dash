import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from application.opportunities.zebra_instruments import mappings
from scripts.refresh_zebra_sources import run
from application.opportunities.zebra_screen_queue import record_research_screen


class ZebraRefreshTests(unittest.TestCase):
    def test_maps_share_alias_and_etf_code(self):
        result=mappings(Path('nonexistent-test-captures'))
        self.assertEqual(result['SASOL'],'SOL')
        self.assertEqual(result['ABSPJ'],'ABG')
        self.assertEqual(result['ETF_STX40'],'STX40')

    def test_one_provider_failure_does_not_stop_other_instruments(self):
        def fake_capture(code, output):
            if code=='BVT': raise ValueError('unavailable')
            return {'last':'2026-11-03'}
        with tempfile.TemporaryDirectory() as directory, \
             patch('scripts.refresh_zebra_sources.mappings',return_value={'SASOL':'SOL','BVT':'BVT'}), \
             patch('scripts.refresh_zebra_sources.capture',side_effect=fake_capture), \
             patch('scripts.refresh_zebra_sources.build',return_value={'sessions':5}), \
             patch('application.opportunities.radar_price_capture.capture',return_value={'results':[]}), \
             patch('application.opportunities.radar_price_capture.research_catalog',return_value={}), \
             patch('jse_adapter.YahooFinanceFetcher'):
            result=run(Path(directory),workers=1)
        self.assertEqual(result['attempted'],2)
        self.assertEqual(result['captured'],1)
        self.assertEqual(result['compared'],2)
        self.assertEqual(result['failures'][0]['instrument'],'BVT')

    def test_screen_queue_is_seen_by_existing_refresh_without_account_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            record_research_screen({'schema':'zebra-research-screen-v1','generated_at':'2026-11-04T20:00:00+00:00',
                'opportunities':[{'rank':1,'research_key':'BTI','provenance':{'data_symbol':'BTI.JO'}}]},
                root/'runtime/local-swing-data/screen-requests')
            with patch('scripts.refresh_zebra_sources.mappings',return_value={}), \
                 patch('scripts.refresh_zebra_sources.capture',return_value={'last':'2026-11-03'}) as capture, \
                 patch('scripts.refresh_zebra_sources.build',return_value={'sessions':5}), \
                 patch('application.opportunities.radar_price_capture.capture',return_value={'results':[]}), \
                 patch('application.opportunities.radar_price_capture.research_catalog',return_value={}), \
                 patch('jse_adapter.YahooFinanceFetcher'):
                result=run(root,workers=1)
            self.assertEqual(result['attempted'],1)
            self.assertEqual(result['screen_queue']['requested'],1)
            self.assertEqual(capture.call_args.args[0],'BTI')

    def test_yahoo_outage_does_not_stop_queued_sharedata_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            record_research_screen({'schema':'zebra-research-screen-v1','generated_at':'2026-11-04T20:00:00+00:00',
                'opportunities':[{'rank':1,'research_key':'BTI','provenance':{'data_symbol':'BTI.JO'}}]},
                root/'runtime/local-swing-data/screen-requests')
            with patch('scripts.refresh_zebra_sources.mappings',return_value={}), \
                 patch('scripts.refresh_zebra_sources.capture',return_value={'last':'2026-11-03'}) as capture, \
                 patch('scripts.refresh_zebra_sources.build',return_value={'sessions':5}), \
                 patch('application.opportunities.radar_price_capture.capture',side_effect=RuntimeError('private upstream detail')), \
                 patch('application.opportunities.radar_price_capture.research_catalog',return_value={}), \
                 patch('jse_adapter.YahooFinanceFetcher'):
                result=run(root,workers=1)
            self.assertEqual(result['attempted'],1)
            self.assertEqual(result['captured'],1)
            self.assertEqual(capture.call_args.args[0],'BTI')
            receipt=__import__('json').loads(Path(result['receipt']).read_text(encoding='utf-8'))
            self.assertEqual(receipt['yahoo']['state'],'FAILED_PRIOR_CAPTURES_RETAINED')
            self.assertNotIn('private upstream detail',str(receipt))

    def test_screen_discovered_issuer_reaches_both_existing_public_paths(self):
        class Yahoo:
            def get_chart(self,symbol,period):
                return {'symbol':symbol,'provider_symbol':symbol,'currency':'ZAR',
                        'instrument_type':'EQUITY','exchange':'JNB','interval':'1d',
                        'bars':[{'timestamp':'2026-10-28','open':10,'high':11,'low':9,'close':10,'volume':100}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); output=root/'runtime/local-swing-data'
            record_research_screen({'schema':'zebra-research-screen-v1','generated_at':'2026-10-29T20:00:00+00:00',
                'opportunities':[{'rank':1,'research_key':'ZZZZ','provenance':{'data_symbol':'ZZZZ.JO'}}]},
                output/'screen-requests')
            with patch('scripts.refresh_zebra_sources.mappings',return_value={}), \
                 patch('scripts.refresh_zebra_sources.capture',return_value={'last':'2026-10-28'}) as sharedata, \
                 patch('scripts.refresh_zebra_sources.build',return_value={'sessions':1}), \
                 patch('application.opportunities.radar_price_capture.research_catalog',return_value={}), \
                 patch('jse_adapter.YahooFinanceFetcher',return_value=Yahoo()):
                result=run(root,workers=1)
            self.assertEqual((result['yahoo_captured'],result['captured']),(1,1))
            self.assertEqual(sharedata.call_args.args[0],'ZZZZ')
            from application.opportunities.radar_price_capture import latest_close_history
            history=latest_close_history(output/'radar-public-prices','ZZZZ')
            self.assertEqual(history['identity_basis'],'SCREEN_YAHOO_METADATA')
            self.assertEqual(history['rows'][0]['close'],10)


if __name__=='__main__': unittest.main()
