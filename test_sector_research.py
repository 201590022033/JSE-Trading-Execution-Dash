import unittest
import tempfile
from copy import deepcopy
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from application.backtest_lab.sector_research import compare
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.opportunities.research_classification import classifications
from application.opportunities.swing_research import BASELINE, evaluate, accept_dataset, run_research


def sample():
    return {'meta':{}, 'bars':{'BTI':[], 'SASOL':[], 'XYZ':[]}, 'strategies':[
        {'id':'swing','name':'Swing','run':{'signals':[{'inst':'BTI'}], 'trades':[
            {'instrument':'BTI','net_pnl':'30'}, {'instrument':'SASOL','net_pnl':'-5'}]}},
        {'id':'box','name':'Box','run':{'signals':[{'inst':'BTI'}], 'trades':[
            {'instrument':'BTI','net_pnl':'20'}, {'instrument':'SASOL','net_pnl':'-10'}]}}]}


class SectorResearchTests(unittest.TestCase):
    def test_sector_proposal_uses_scoped_training_and_shared_daily_budget(self):
        from persistence.sqlite_repository import SQLiteRepository
        from test_swing_research import fixture
        from test_swing_technical import clock
        data=fixture(); data['charts']['BTI']=deepcopy(data['charts']['TFMJ']); data['charts']['BTI']['symbol']='BTI.JO'
        now=clock(data['charts']['TFMJ']); contexts=[]
        def proposer(context):
            contexts.append(context)
            return {'parameters':{'volume_min':1.2,'rsi_max':70,'holding_sessions':3},'rationale':'Sector test'}
        with tempfile.TemporaryDirectory() as temp:
            repo=SQLiteRepository(Path(temp)/'research.db')
            try:
                accept_dataset(repo,data,now)
                result=run_research(repo,now,proposer,sector='Retail')
                self.assertEqual(result['sector_scope'],'Retail')
                self.assertEqual(contexts[0]['sector_scope'],'Retail')
                self.assertEqual(set(contexts[0]['technical_evidence_training_only']),{'TFMJ'})
                self.assertNotIn('holdout',contexts[0])
                self.assertEqual(run_research(repo,now,proposer,sector='Consumer')['state'],'DAILY_AI_BUDGET_USED')
            finally: repo.close()

    def test_swing_sector_scope_evaluates_only_selected_sector(self):
        start=datetime(2026,1,1)
        bars=[{'timestamp':(start+timedelta(days=i)).date().isoformat()} for i in range(52)]
        charts={'BTI':{'bars':bars},'SASOL':{'bars':bars}}
        feature={'state':'AVAILABLE','conditions':{'ema_uptrend':True,'breakout20':True,
                 'ema20_reclaim':False,'outperforming_benchmark20':True},
                 'values':{'rsi14_wilder':60,'relative_volume20':1.2}}
        replay={'state':'CLOSED','exit_session':bars[-1]['timestamp'],'gross_return':.1,
                'net_return_scenarios':{'10':.09,'25':.08,'50':.07}}
        with patch('application.opportunities.swing_research.public_share_catalog',return_value={'BTI':{},'SASOL':{}}), \
             patch('application.opportunities.swing_research.snapshot',return_value=feature), \
             patch('application.opportunities.swing_research.build_policy',return_value={'state':'SHADOW_READY'}), \
             patch('application.opportunities.swing_research.simulate',return_value=replay):
            result=evaluate(charts,BASELINE,bars[50]['timestamp'],bars[-1]['timestamp'],sector='Consumer')
        self.assertEqual(list(result['by_instrument']),['BTI'])
        self.assertEqual(list(result['by_sector']),['Consumer'])
        self.assertGreater(result['sample_count'],0)

    def test_contender_uses_closed_trades_and_no_trades_are_not_zero_profit(self):
        d=compare(sample())
        self.assertEqual(d['instruments']['BTI']['default']['strategy_id'],'swing')
        self.assertEqual(d['instruments']['BTI']['default']['label'],'Backtested top contender')
        self.assertEqual(d['instruments']['SASOL']['default']['label'],'Least negative observed')
        self.assertEqual(d['instruments']['SASOL']['default']['strategy_id'],'swing')
        self.assertIsNone(d['instruments']['XYZ']['default'])
        self.assertFalse(d['classifications_frozen_with_run'])
        self.assertEqual(d['instruments']['BTI']['classification']['industry'],'Tobacco')
        self.assertEqual(d['instruments']['XYZ']['classification']['sector'],'Unclassified')

    def test_frozen_classifications_remain_attached_to_run(self):
        run=sample();run['meta']['research_classifications']={'version':'old','basis':'frozen',
            'instruments':{'BTI':{'sector':'Frozen Sector','industry':'Test'}}}
        d=compare(run)
        self.assertTrue(d['classifications_frozen_with_run'])
        self.assertEqual(d['instruments']['BTI']['classification']['sector'],'Frozen Sector')

    def test_newly_classified_unmapped_universe(self):
        d=classifications(['DTC','HET','TMT','AGOGE','UNKNOWN'])['instruments']
        self.assertEqual(d['DTC']['sector'],'Technology')
        self.assertEqual(d['HET']['sector'],'Real Estate')
        self.assertEqual(d['TMT']['sector'],'Real Estate')
        self.assertEqual(d['AGOGE']['sector'],'Funds')
        self.assertEqual(d['UNKNOWN']['sector'],'Unclassified')

    def test_current_replay_universe_has_sector_and_industry(self):
        keys='ABSPJ AGL AGOGE BHP BTI BVT CFR CLS CSB DTC FSR GFI GPL HET HYP IMPJ KIO LHC MTH MTN NED NPN NWL PRX REM RNG SASOL SHPJ TEX TFMJ TMT TPC VIS VOD'.split()
        result=classifications(keys)['instruments']
        self.assertEqual(len(result),34)
        self.assertFalse([k for k,v in result.items() if v['sector']=='Unclassified' or v['industry']=='Unspecified'])

    def test_endpoint_is_read_only_and_no_store(self):
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(directory='.'))
        with patch('application.backtest_lab.blueprint._read',return_value=sample()), \
             patch('pathlib.Path.is_dir',return_value=True):
            r=app.test_client().get('/api/v1/backtest-lab/runs/'+'a'*64+'/sector-research')
        self.assertEqual(r.status_code,200);self.assertFalse(r.json['live_execution'])
        self.assertEqual(r.headers['Cache-Control'],'no-store')


if __name__=='__main__': unittest.main()
