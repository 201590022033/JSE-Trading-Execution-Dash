import unittest
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.target_design import matched_projection, source_rows
from application.backtest_lab.observed_history import from_chart
from application.opportunities.session_freshness import next_session
from domain.backtest.target_design_engine import Costs, Signal, replay


class TargetDesignTests(unittest.TestCase):
    def test_matching_excludes_outcomes_not_yet_known(self):
        rows=[{'timestamp':'2026-01-05'}]
        cases=[{'scope':'same_share','outcome_date':'2026-01-05','momentum':1,
                'change':1,'excursion_atr':2,'instrument':'BTI'},
               {'scope':'same_share','outcome_date':'2026-01-06','momentum':1,
                'change':1,'excursion_atr':100,'instrument':'BTI'}]
        with patch('application.backtest_lab.target_design.features',return_value={
                'momentum_atr':1,'momentum_change_atr':1,'atr':3}):
            result=matched_projection(rows,0,cases,'same_share')
        self.assertEqual(result['sample_count'],1)
        self.assertEqual(result['target_distance'],6)

    def test_missing_industry_uses_explicit_fallback(self):
        with patch('application.backtest_lab.target_design.features',return_value={
                'momentum_atr':1,'momentum_change_atr':1,'atr':3}):
            result=matched_projection([{'timestamp':'2026-01-05'}],0,[],'same_industry')
        self.assertEqual(result['status'],'FIXED_TARGET_FALLBACK')
        self.assertEqual(result['reason'],'NO_MATURED_MATCHING_SETUPS')

    def test_missing_fields_do_not_discard_available_close(self):
        rows=source_rows([{'session':'2026-01-05','fields':{'close':{'value':23}}}])
        self.assertEqual(rows[0]['close'],23)
        self.assertIsNone(rows[0]['volume'])

    def test_net_reward_floor_and_rejection_use_entry_costs(self):
        rows=[];day='2026-01-02'
        for i in range(65):
            rows.append({'timestamp':day,'open':100,'high':102,'low':99,'close':100,'volume':10000})
            day=next_session(day)
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'TEST',
            'source_sha256':'a'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}})
        common=dict(id='SOL-'+rows[55]['timestamp'],instrument='SOL',session=rows[55]['timestamp'],
            decision_at=manifest.bars[55].available_at+timedelta(seconds=1),stop=Decimal('95'),
            max_notional=Decimal('10000'),risk_budget=Decimal('1000'),target_distance=Decimal('1'))
        costs=Costs(fee_bps=Decimal('8'),minimum_fee=Decimal('5'),spread_bps=Decimal('20'),slippage_bps=Decimal('5'))
        def run(policy):
            return replay([manifest],[Signal(**common,target_policy=policy)],
                as_of=manifest.bars[-1].available_at+timedelta(days=8),initial_cash=Decimal('100000'),costs=costs)
        rejected=run('REJECT')['decisions']
        self.assertIn('TARGET_ECONOMICS_REJECTED',[d['state'] for d in rejected])
        floored=next(d for d in run('FLOOR')['decisions'] if d['state']=='TARGET_ECONOMICS')
        self.assertGreaterEqual(float(floored['estimated_net_target_r']),0.9999)
        self.assertGreater(float(floored['target']),float(floored['entry'])+1)

    def test_api_only_serves_content_addressed_read_only_studies(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'target-design';folder.mkdir()
            payload={'schema':'target-design-study-v1','live_execution':False,'instrument':'BTI',
                     'family':'box','horizon':3,'window':['2025-01-01','2025-12-31']}
            raw=json.dumps(payload).encode();key=hashlib.sha256(raw).hexdigest()
            (folder/(key+'.json')).write_bytes(raw)
            (folder/('0'*64+'.json')).write_bytes(raw)
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root))
            client=app.test_client();listing=client.get('/api/v1/backtest-lab/target-design')
            self.assertEqual(listing.status_code,200)
            self.assertEqual(listing.headers['Cache-Control'],'no-store')
            self.assertEqual([r['report_id'] for r in listing.json['reports']],[key])
            self.assertFalse(client.get('/api/v1/backtest-lab/target-design/'+key).json['live_execution'])
            self.assertEqual(client.get('/api/v1/backtest-lab/target-design/'+('0'*64)).status_code,404)


if __name__ == '__main__': unittest.main()
