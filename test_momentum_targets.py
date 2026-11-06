import copy
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from dataclasses import replace
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.momentum_targets import features,projection,compare,peer_projection,timed_context
from application.backtest_lab.components import Components
from application.backtest_lab.observed_history import from_chart
from application.opportunities.session_freshness import next_session


class MomentumTargetTests(unittest.TestCase):
    def rows(self):
        return [{'timestamp':f'2025-01-{i+1:02d}','open':100+i,'high':102+i,
                 'low':99+i,'close':101+i,'volume':1000} for i in range(30)]

    def test_projection_cannot_see_unmatured_or_future_rows(self):
        rows=self.rows();before=projection(rows,25,3,'momentum')
        changed=copy.deepcopy(rows)
        for row in changed[26:]:row.update(high=99999,close=99999,volume=99999)
        self.assertEqual(before,projection(changed,25,3,'momentum'))
        self.assertEqual(before['status'],'PROJECTED')
        self.assertGreater(before['sample_count'],0)

    def test_missing_volume_does_not_block_price_projection(self):
        rows=self.rows()
        for row in rows:row['volume']=None
        self.assertEqual(projection(rows,25,3,'momentum')['status'],'PROJECTED')
        v=projection(rows,25,3,'momentum_volume')
        self.assertEqual(v['status'],'FIXED_TARGET_FALLBACK')
        self.assertEqual(v['reason'],'OPTIONAL_CONTEXT_MISSING')

    def test_peer_outcomes_after_signal_are_excluded(self):
        rows=self.rows();case={'instrument':'PEER','outcome_day':rows[25]['timestamp'],
             'momentum_atr':1,'change_atr':0,'excursion_atr':2}
        eligible=peer_projection(rows,25,3,[case]);self.assertEqual(eligible['sample_count'],1)
        case['outcome_day']=rows[26]['timestamp']
        self.assertEqual(peer_projection(rows,25,3,[case])['sample_count'],0)

    def test_date_only_news_uses_actual_receipt_without_backdating(self):
        item={'instrument':'SOL','headline':'Results','source_id':'s1','publication_date':'2026-10-01',
              'publication_precision':'date','acquired_at':'2026-10-03T08:00:00+00:00',
              'source_received_at':'2026-10-03T08:00:01+00:00','received_at':'2026-10-03T08:00:02+00:00'}
        early=timed_context([item],'SOL','2026-10-02T10:00:00+00:00')
        self.assertEqual(len(early['known_recent']),0)
        self.assertEqual(early['retrospective_recent'][0]['reason'],'CAPTURED_AFTER_SIGNAL')
        result=timed_context([item],'SOL','2026-10-03T09:00:00+00:00')
        self.assertEqual(result['known_recent'][0]['known_at'],'2026-10-03T08:00:02+00:00')
        self.assertIsNone(result['known_recent'][0]['published_at'])
        item['publication_date']='2026-10-03'
        item['acquired_at']='2026-10-03T08:00:00+00:00'
        result=timed_context([item],'SOL','2026-10-03T00:00:01+00:00',signal_session='2026-10-02')
        self.assertEqual(result['retrospective_recent'],[])

    def test_reference_calendar_keeps_holidays_but_splits_missing_sessions(self):
        from application.backtest_lab.zebra_field_windows import reference_segments
        dates=['2025-09-23','2025-09-25','2025-09-26','2025-09-29']
        rows=[{'session':d,'open':10,'high':11,'low':9,'close':10} for d in dates]
        reference=[{'session':d,'close':10} for d in dates]
        self.assertEqual(len(reference_segments(rows,reference)),1)
        reference.append({'session':'2025-09-24','close':10})
        self.assertEqual([len(x) for x in reference_segments(rows,reference)],[1,3])
        rows[2]['open']=None
        self.assertEqual([len(x) for x in reference_segments(rows,reference)],[1,1,1])

    def test_family_evaluator_keeps_history_across_observed_holiday(self):
        from datetime import date,timedelta
        from application.backtest_lab.zebra_field_windows import evaluate_mixed
        rows=[];day=date(2025,7,1)
        while len(rows)<75:
            if day.weekday()<5 and day.isoformat()!='2025-09-24':
                i=len(rows);rows.append({'timestamp':day.isoformat(),'open':100+i,'high':102+i,'low':99+i,'close':101+i,'volume':1000})
            day+=timedelta(days=1)
        reference=[{'session':r['timestamp'],'close':r['close']} for r in rows]
        old,_=evaluate_mixed('box','SOL',len(rows)-1,{'SOL':rows})
        new,_=evaluate_mixed('box','SOL',len(rows)-1,{'SOL':rows},reference_sessions=reference)
        self.assertFalse(old);self.assertTrue(new)

    def test_four_replays_keep_identical_signal_counts(self):
        rows=[];day='2026-01-02'
        for i in range(100):
            c=100+i*.2;rows.append({'timestamp':day,'open':c,'high':c+2,'low':c-1,'close':c,'volume':1000});day=next_session(day)
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'TEST','source_sha256':'a'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}})
        def evaluate(config,instrument,i,charts):
            return ([{'c':'test','state':'PASS','ok':True}] if i in (60,75) else [{'c':'test','state':'FAIL','ok':False}]),rows[i]['close']-5
        config=Components(volume_mode='off',benchmark_mode='off')
        source={'instrument':'SOL','source_id':'test-source','headline':'Earnings',
                'publication_date':rows[58]['timestamp'],'publication_precision':'date',
                'acquired_at':rows[59]['timestamp']+'T00:00:00+00:00',
                'source_received_at':rows[59]['timestamp']+'T00:01:00+00:00',
                'received_at':rows[59]['timestamp']+'T00:02:00+00:00'}
        with patch('application.backtest_lab.component_replay.evaluate',side_effect=evaluate):
            result=compare(config,manifest,{'SOL':rows},source_items=[source])
            from application.backtest_lab.component_replay import run_components
            base=run_components(config,manifest,{'SOL':rows})
            direct=compare(replace(config,horizon=4),manifest,{'SOL':rows})
            cached=compare(replace(config,horizon=4),manifest,{'SOL':rows},base_result=base)
            self.assertEqual(direct,cached)
            with self.assertRaises(ValueError):compare(replace(config,stop_pct=.1),manifest,{'SOL':rows},base_result=base)
        self.assertEqual([v['signals'] for v in result['variants'].values()],[2,2,2,2,2])
        first='SOL-'+rows[60]['timestamp']
        self.assertEqual(result['timed_context'][first]['known_recent'][0]['source_id'],'test-source')
        for name in ('momentum','momentum_volume'):
            self.assertEqual(result['variants'][name]['projected_signals'],2)
        self.assertEqual(result['variants']['momentum_sector']['projected_signals'],0)
        self.assertEqual(result['variants']['momentum_peers']['projected_signals'],0)
        for trade in result['variants']['momentum']['closed_trades']:
            calc=result['calculations']['momentum'][trade['id']]
            self.assertAlmostEqual(calc['target_price'],float(trade['entry'])+calc['target_distance'])

    def test_report_endpoint_checks_hash_and_no_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'momentum-targets';folder.mkdir()
            value={'schema':'momentum-target-comparison-v1','live_execution':False,'instrument':'SOL',
                   'family':'swing','window':['a','b'],'variants':{},'input_sources':{'SOL':[{'session':'2026-01-02'}]}}
            raw=json.dumps(value).encode();key=hashlib.sha256(raw).hexdigest();path=folder/(key+'.json');path.write_bytes(raw)
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
            response=client.get('/api/v1/backtest-lab/momentum-targets/'+key)
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertFalse(response.json['live_execution']);self.assertNotIn('input_sources',response.json['report'])
            self.assertIn('input_sources',client.get('/api/v1/backtest-lab/momentum-targets/'+key+'?include_sources=1').json['report'])
            path.write_bytes(raw+b' ')
            self.assertEqual(client.get('/api/v1/backtest-lab/momentum-targets/'+key).status_code,404)

if __name__=='__main__':unittest.main()
