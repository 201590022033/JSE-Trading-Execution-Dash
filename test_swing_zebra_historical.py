from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask

from application.opportunities.swing_research import run_research, accept_dataset
from application.opportunities.swing_historical_inputs import acquired_no_later_than, observed_rows_as_of, prepare_v3_research
from persistence.sqlite_repository import SQLiteRepository
from test_swing_research import fixture
from test_swing_technical import clock


class ZebraSwingHistoricalTests(unittest.TestCase):
    def test_unconfigured_cloud_does_not_spend_the_daily_budget(self):
        from types import SimpleNamespace
        data=fixture(); now=clock(data['charts']['TFMJ'])
        providers=SimpleNamespace(providers=[None,SimpleNamespace(key='')])
        with tempfile.TemporaryDirectory() as temp:
            repo=SQLiteRepository(Path(temp)/'test.db')
            try:
                accept_dataset(repo,data,now)
                with patch('sentiment_providers.SentimentProviders',return_value=providers), \
                     patch('application.opportunities.africa_api_credentials.load_key',return_value=None):
                    out=run_research(repo,now,sector='Retail')
                self.assertEqual(out['state'],'AI_NOT_CONFIGURED')
                self.assertFalse(out['model_called'])
                self.assertIsNone(repo.paper_record('swing-ai-budget-'+now.date().isoformat()))
            finally: repo.close()

    def test_unavailable_ost_iress_can_use_retained_whole_source_fallback(self):
        from datetime import datetime,timezone
        from application.backtest_lab.observed_history import from_chart
        from contextlib import ExitStack
        now=datetime(2026,11,4,tzinfo=timezone.utc)
        data=fixture(); stock=data['charts']['TFMJ']['bars']; acquired='2026-11-04T00:00:00+00:00'
        dataset={'schema':'local-swing-dataset-v3','observed_at':acquired,
                 'charts':{'ETF_STX40':{'provenance':{'source_sha256':'a'*64}}}}
        benchmark={'acquired_at':acquired,'source_sha256':'b'*64,'rows':[
            {'session':r['timestamp'],'close':r['close']} for r in stock]}
        receipt={'provider':'SHAREDATA','source_sha256':'c'*64,'acquired_at':acquired}
        chart={'bars':stock,'provenance':receipt}; manifest=from_chart('TFMJ',chart)
        def add_share(charts, manifests, folder):
            charts['TFMJ']=stock
            return charts,[manifest]
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'repo/runtime/local-swing-data';folder.mkdir(parents=True)
            (folder/'latest.json').write_text(json.dumps(dataset))
            with ExitStack() as stack:
                stack.enter_context(patch('scripts.backtest_lab_run.load_real',side_effect=ValueError('no IRESS')))
                stack.enter_context(patch('application.opportunities.radar_price_capture.latest_close_history',return_value=benchmark))
                for method in ('add_research_histories','append_public_bars','append_sharedata_bars'):
                    stack.enter_context(patch('scripts.backtest_lab_run.'+method,side_effect=lambda c,m,*a,**kw:(c,m)))
                stack.enter_context(patch('scripts.backtest_lab_run.append_eodhd_benchmark',side_effect=lambda c,p,*a:(c,p)))
                stack.enter_context(patch('scripts.backtest_lab_run.add_sharedata_histories',side_effect=add_share))
                stack.enter_context(patch('scripts.backtest_lab_run.add_eodhd_histories',side_effect=lambda c,m,*a:(c,m,{})))
                stack.enter_context(patch('scripts.backtest_lab_run.apply_consensus_windows',side_effect=lambda c,m,*a,**kw:(c,m,{})))
                stack.enter_context(patch('application.opportunities.zebra_instruments.mappings',return_value={'TFMJ':'TFG'}))
                stack.enter_context(patch('application.opportunities.session_freshness.next_session',return_value=None))
                out=prepare_v3_research(dataset,now,folder)
        self.assertEqual(out['charts']['TFMJ']['provenance']['provider'],'SHAREDATA')
        self.assertEqual(out['benchmark_provenance']['provider'],'YAHOO')
        self.assertEqual(len(out['charts']['TFMJ']['bars']),133)
        self.assertLess(out['charts']['TFMJ']['bars'][-1]['timestamp'],now.date().isoformat())

    def test_older_legacy_dataset_can_be_explicit_historical_research(self):
        data=fixture(); observed=clock(data['charts']['TFMJ']); later=observed+timedelta(days=8)
        proposer=lambda context:{'parameters':{'volume_min':1.2,'rsi_max':70,'holding_sessions':3},'rationale':'Test'}
        with tempfile.TemporaryDirectory() as temp:
            repo=SQLiteRepository(Path(temp)/'test.db')
            try:
                accept_dataset(repo,data,observed)
                out=run_research(repo,later,proposer,sector='Retail',allow_historical=True)
                self.assertEqual(out['state'],'PROPOSED_AND_TESTED')
                self.assertEqual(out['historical_freshness']['state'],'HISTORICAL_NOT_CURRENT')
                self.assertIn('HISTORICAL_RESEARCH_NOT_CURRENT_QUOTE',out['limitations'])
            finally: repo.close()

    def test_historical_readiness_is_read_only_and_does_not_call_model(self):
        from application.opportunities.swing_research_api import create_research_blueprint
        app=Flask(__name__); app.register_blueprint(create_research_blueprint(lambda:None))
        ready={'charts':{'BTI':{'bars':[{'timestamp':'2026-01-01'}]},'ETF_STX40':{}},'freshness':{'state':'HISTORICAL_NOT_CURRENT'},
               'source':'TEST','limitations':[]}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp); (folder/'latest.json').write_text(json.dumps({'schema':'local-swing-dataset-v3'}))
            with patch('application.opportunities.ost_data.ROOT',folder), \
                 patch('application.opportunities.swing_historical_inputs.prepare_v3_research',return_value=ready):
                r=app.test_client().get('/api/v1/swing-research/historical-readiness')
        self.assertEqual(r.status_code,200); self.assertFalse(r.json['model_called'])
        self.assertFalse(r.json['live_execution']); self.assertEqual(r.json['sectors']['Consumer'],['BTI'])
        self.assertEqual(r.json['state'],'MORE_HISTORY_REQUIRED')
        self.assertEqual(r.headers['Cache-Control'],'no-store')

    def test_future_or_unzoned_acquisition_is_not_historical_evidence(self):
        from datetime import datetime,timezone
        now=datetime(2026,11,4,tzinfo=timezone.utc)
        self.assertTrue(acquired_no_later_than({'acquired_at':'2026-11-03T12:00:00Z'},now))
        self.assertFalse(acquired_no_later_than({'acquired_at':'2026-11-05T12:00:00Z'},now))
        self.assertFalse(acquired_no_later_than({'acquired_at':'2026-11-03T12:00:00'},now))
        self.assertFalse(acquired_no_later_than({'acquired_at':'2026-11-03T12:00:00Z',
            'supplemental_sources':[{'acquired_at':'2026-11-05T12:00:00Z'}]},now))

    def test_each_row_must_precede_its_provider_acquisition(self):
        from datetime import datetime,timezone
        now=datetime(2026,11,4,tzinfo=timezone.utc)
        receipt={'provider':'IRESS+YAHOO','acquired_at':'2026-10-31T08:00:00Z',
                 'supplemental_sources':[{'provider':'YAHOO','acquired_at':'2026-11-04T00:00:00Z'}]}
        rows=[{'timestamp':'2026-10-30','_source':'IRESS'}, {'timestamp':'2026-11-02','_source':'IRESS'},
              {'timestamp':'2026-11-03','_source':'YAHOO'}]
        self.assertEqual([r['timestamp'] for r in observed_rows_as_of(rows,receipt,now)],['2026-11-03'])

    def test_stale_v3_reconstructed_data_reaches_sector_proposer_once(self):
        data=fixture(); now=clock(data['charts']['TFMJ']); contexts=[]
        v3={'schema':'local-swing-dataset-v3','observed_at':(now-timedelta(days=10)).isoformat()}
        history={'schema':'zebra-swing-research-input-v1','source':'ZEBRA_RECONSTRUCTED_WHOLE_SOURCE_OHLCV',
                 'observed_at':v3['observed_at'],'charts':deepcopy(data['charts']),
                 'freshness':{'state':'HISTORICAL_NOT_CURRENT','latest_benchmark_session':'2025-01-01'},
                 'limitations':['RECONSTRUCTED_HISTORICAL_AVAILABILITY'],
                 'source_receipts':{'TFMJ':{'provider':'TEST'}},'consensus_windows':{}}
        def proposer(context):
            contexts.append(context)
            return {'parameters':{'volume_min':1.2,'rsi_max':70,'holding_sessions':3},'rationale':'Test only'}
        with tempfile.TemporaryDirectory() as temp:
            repo=SQLiteRepository(Path(temp)/'test.db')
            try:
                out=run_research(repo,now,proposer,sector='Retail',dataset_override=v3,
                                 historical_loader=lambda payload,at:history)
                self.assertEqual(out['state'],'PROPOSED_AND_TESTED')
                self.assertEqual(out['sector_scope'],'Retail')
                self.assertEqual(out['historical_freshness']['state'],'HISTORICAL_NOT_CURRENT')
                self.assertEqual(contexts[0]['dataset_source'],'ZEBRA_RECONSTRUCTED_WHOLE_SOURCE_OHLCV')
                self.assertEqual(set(contexts[0]['technical_evidence_training_only']),{'TFMJ'})
                self.assertFalse(out['live_execution'])
                self.assertEqual(len(contexts),1)
            finally: repo.close()

    def test_unavailable_whole_source_never_calls_proposer(self):
        data=fixture(); now=clock(data['charts']['TFMJ'])
        def unavailable(*args): raise ValueError('missing source')
        def proposer(_): self.fail('model must not be called')
        with tempfile.TemporaryDirectory() as temp:
            repo=SQLiteRepository(Path(temp)/'test.db')
            try:
                out=run_research(repo,now,proposer,dataset_override={'schema':'local-swing-dataset-v3'},
                                 historical_loader=unavailable)
                self.assertEqual(out['state'],'OST_SOURCE_SEMANTICS_UNVERIFIED')
                self.assertFalse(out['model_called'])
            finally: repo.close()


if __name__=='__main__': unittest.main()
