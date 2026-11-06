import tempfile
import unittest
from pathlib import Path
from application.backtest_lab.components import Components
from application.backtest_lab.learning_loop import run_cycle, validate_proposal, split_sessions
from application.backtest_lab.observed_history import from_chart
from application.opportunities.session_freshness import next_session
from persistence.experiment_repo import DurableExperimentRepository
from persistence.sqlite_repository import SQLiteRepository


class ComponentLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)
        self.storage=SQLiteRepository(self.path/'research.db')
        self.storage.create_paper_account('research',{'mode':'PAPER'})
        self.repo=DurableExperimentRepository(self.storage,account_id='research',namespace='component-test')
        day='2026-01-02'; self.rows=[]
        for i in range(140):
            close=100+i*.1+(i%8)*.2
            self.rows.append({'timestamp':day,'open':close-.1,'high':close+.5,'low':close-.6,'close':close,'volume':1000+i%9})
            day=next_session(day)
        self.manifest=from_chart('SOL',{'bars':self.rows,'provenance':{'provider':'TEST','source_sha256':'a'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}})
        self.charts={'SOL':self.rows}; self.base=Components(volume_mode='threshold',benchmark_mode='off')
    def tearDown(self): self.storage.close();self.tmp.cleanup()
    def test_listed_gold_adapter_tracks_training_and_validation_prefixes(self):
        from scripts.backtest_gold_reference import ObservedGoldUnits
        from domain.backtest.products import GoldListed
        manifest=ObservedGoldUnits(**{**vars(self.manifest),'product':'GOLD_ETF'})
        adapter=GoldListed('ZAR','ZAR',manifest.calendar_id,manifest.sessions,(),manifest.instrument)
        result=run_cycle(self.repo,manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',adapter=adapter)
        self.assertEqual(result['state'],'COMPLETED')
        self.assertEqual(len(self.repo.get_experiment(result['experiment_id'],'1')['results']),2)
        self.assertEqual(result['holdout'],'UNOPENED')
    def test_two_cycles_restart_idempotence_and_no_holdout_context(self):
        contexts=[]
        def proposer(context):
            contexts.append(context)
            return {'component':'volume_mode','value':'off','rationale':'Compare a volume-free control'}
        from application.backtest_lab.learning_loop import _artifact
        source=_artifact(self.path/'inputs',{'source':'TEST','session':'2026-01-02'})
        first=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=proposer,source_lineage=source)
        self.assertEqual(first['state'],'COMPLETED')
        self.assertEqual(len(self.repo.get_experiment(first['experiment_id'],'1')['results']),2)
        self.assertEqual(self.repo.get_experiment(first['experiment_id'],'1')['definition'].baseline_artifacts[0].sha256,source.sha256)
        self.storage.close(); self.storage=SQLiteRepository(self.path/'research.db')
        self.repo=DurableExperimentRepository(self.storage,account_id='research',namespace='component-test')
        again=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=proposer)
        self.assertEqual(again['state'],'ALREADY_COMPLETED')
        self.assertEqual(len(contexts),1)
        def followup_proposer(context):
            self.assertTrue(context['prior_training_results'])
            self.assertIn('sample_counts',context['prior_training_results'][0])
            return {'component':'horizon','value':4,'rationale':'Investigate holding period'}
        second=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',cycle=2,proposer=followup_proposer)
        self.assertEqual(second['state'],'COMPLETED')
        split=split_sessions(self.manifest)
        self.assertNotIn(self.manifest.sessions[split['holdout'][0]].key,str(contexts))
        self.assertEqual(len(self.repo.list_experiments()),2)
        followup=self.repo.get_experiment(second['experiment_id'],'1')['definition']
        self.assertIn(followup.changed_components[0],('horizon','benchmark_mode'))
        self.assertEqual(second['holdout'],'UNOPENED')
        duplicate=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',cycle=3,proposer=proposer)
        self.assertEqual(duplicate['state'],'DUPLICATE_PROPOSAL')
        self.assertEqual(duplicate['prior_experiment_id'],first['experiment_id'])
        self.assertEqual(len(self.repo.list_experiments()),2)
    def test_failed_proposer_falls_back_without_retaining_exception(self):
        def bad(_):raise RuntimeError('private-provider-error')
        result=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=bad)
        self.assertEqual(result['proposal_source'],'PROPOSER_FAILED_FALLBACK')
        self.assertNotIn('private-provider-error',str(self.repo.get_experiment(result['experiment_id'],'1')))
    def test_model_context_excludes_holdout_price_and_future_benchmark(self):
        sentinel=987654.321
        rows=[dict(r) for r in self.rows]
        rows[-1].update(open=sentinel,high=sentinel+1,low=sentinel-1,close=sentinel)
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'TEST','source_sha256':'b'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}})
        context_seen=[]
        def proposer(context):
            context_seen.append(context)
            return {'component':'volume_mode','value':'off','rationale':'test'}
        benchmark=[{'timestamp':r['timestamp'],'close':r['close']} for r in rows]
        run_cycle(self.repo,manifest,{'SOL':rows,'ETF_STX40':benchmark},self.base,artifact_dir=self.path/'artifacts',proposer=proposer)
        self.assertNotIn(str(sentinel),str(context_seen))
        self.assertNotIn(rows[-1]['timestamp'],str(context_seen))
    def test_missing_validation_volume_keeps_training_result(self):
        rows=[dict(r) for r in self.rows];split=split_sessions(self.manifest)
        rows[split['validation'][0]]['volume']=None
        manifest=from_chart('SOL',{'bars':rows,'provenance':{'provider':'TEST','source_sha256':'c'*64,'acquired_at':'2026-11-05T00:00:00+00:00'}})
        result=run_cycle(self.repo,manifest,{'SOL':rows},self.base,artifact_dir=self.path/'artifacts',
            proposer=lambda context:{'component':'horizon','value':4,'rationale':'test'})
        records=self.repo.get_experiment(result['experiment_id'],'1')['results']
        self.assertEqual(result['state'],'COMPLETED');self.assertEqual(len(records),2)
        self.assertIsNotNone(records[0].metrics['control_net'])
        self.assertIsNone(records[1].metrics['control_net'])
        self.assertIn('missing observed volume',records[1].data_quality_limitations)
    def test_only_timely_optional_context_reaches_proposer(self):
        from datetime import timedelta
        split=split_sessions(self.manifest);cutoff=self.manifest.bars[split['train'][1]].available_at
        def item(name,when):
            stamp=when.isoformat()
            return {'kind':'NEWS','source_id':name,'instrument':'SOL','published_at':stamp,
                    'acquired_at':stamp,'source_received_at':stamp,'received_at':stamp}
        seen=[]
        def proposer(context):
            seen.append(context)
            return {'component':'volume_mode','value':'off','rationale':'test'}
        run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=proposer,
                  context_items=[item('timely',cutoff-timedelta(hours=1)),item('late',cutoff+timedelta(hours=1))])
        self.assertEqual([x['source_id'] for x in seen[0]['optional_context']],['timely'])
        self.assertNotIn('late',str(seen[0]))
    def test_proposals_reject_code_and_unknown_choices(self):
        for raw in ({'component':'exec','value':'rm','rationale':'x'},
                    {'component':'horizon','value':30,'rationale':'x'},
                    {'component':'volume_mode','value':'off','rationale':'x','command':'bad'}):
            with self.assertRaises(ValueError):validate_proposal(raw,self.base)
    def test_learning_status_is_read_only(self):
        import json,hashlib
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        folder=self.path/'component-learning';folder.mkdir()
        (folder/'SOL.json').write_text(json.dumps({'schema':'component-learning-status-v1','instrument':'SOL','live_execution':False}),encoding='utf-8')
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(self.path))
        response=app.test_client().get('/api/v1/backtest-lab/learning-status')
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertFalse(response.json['live_execution']);self.assertEqual(response.json['reports'][0]['instrument'],'SOL')
        artifacts=folder/'artifacts';artifacts.mkdir();raw=b'{"instrument":"SOL"}'
        digest=hashlib.sha256(raw).hexdigest();path=artifacts/(digest+'.json');path.write_bytes(raw)
        client=app.test_client();self.assertEqual(client.get('/api/v1/backtest-lab/learning-artifacts/'+digest).status_code,200)
        path.write_bytes(raw+b' ')
        self.assertEqual(client.get('/api/v1/backtest-lab/learning-artifacts/'+digest).status_code,404)
    def test_cloud_uses_shared_daily_budget_and_reuses_frozen_proposal(self):
        from dataclasses import asdict
        from application.backtest_lab.cloud_component_proposer import BudgetedCloudProposer
        from application.opportunities.swing_research import ACCOUNT
        self.storage.create_paper_account(ACCOUNT,{'mode':'PAPER'})
        calls=[]
        def fake(prompt):
            calls.append(prompt)
            return '{"component":"volume_mode","value":"off","rationale":"test"}'
        proposer=BudgetedCloudProposer(self.storage,request=fake)
        context={'baseline_config':asdict(self.base),'training':'only'}
        self.assertEqual(proposer(context)['component'],'volume_mode')
        self.assertEqual(proposer(context)['component'],'volume_mode')
        self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):proposer({**context,'training':'different'})
        self.assertEqual(len(calls),1)
        override=BudgetedCloudProposer(self.storage,request=fake,override_id='owner-20261105-01')
        override({**context,'training':'different'})
        self.assertEqual(len(calls),2)
        with self.assertRaises(ValueError):override({**context,'training':'third'})
        self.assertEqual(len(calls),2)
    def test_queue_restart_and_single_holdout_reservation(self):
        from application.backtest_lab.learning_journal import LearningJournal
        from application.backtest_lab.learning_loop import evaluate_holdout
        journal=LearningJournal(self.path/'queue.db')
        job=journal.enqueue({'instrument':'SOL','cycle':1})
        self.assertEqual(job,journal.enqueue({'cycle':1,'instrument':'SOL'}))
        self.assertTrue(journal.claim(job));journal.close()
        journal=LearningJournal(self.path/'queue.db')
        self.assertFalse(journal.claim(job));self.assertTrue(journal.claim(job,recover=True))
        journal.finish(job,'COMPLETED',{'ok':True})
        self.assertEqual(journal.get(job)['attempt'],2)
        first=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts')
        looked=evaluate_holdout(self.repo,journal,first['experiment_id'],self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts')
        self.assertEqual(looked['state'],'COMPLETED')
        again=evaluate_holdout(self.repo,journal,first['experiment_id'],self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts')
        self.assertEqual(again['state'],'HOLDOUT_ALREADY_CONSUMED')
        split=split_sessions(self.manifest); last=self.manifest.sessions[split['holdout'][1]].key
        self.assertFalse(journal.reserve_holdout('overlap','candidate',instrument='SOL',start=last,end=last))
        self.assertTrue(journal.reserve_holdout('interrupted-window','candidate'))
        journal.close();journal=LearningJournal(self.path/'queue.db')
        self.assertFalse(journal.reserve_holdout('interrupted-window','other-candidate'))
        failed=journal.enqueue({'instrument':'SOL','cycle':2})
        self.assertTrue(journal.claim(failed));journal.finish(failed,'FAILED',{'error_category':'ValueError'})
        self.assertTrue(journal.claim(failed));journal.finish(failed,'COMPLETED',{'ok':True})
        self.assertEqual(journal.get(failed)['attempt'],2)
        journal.close()
    def test_sector_pool_does_not_mix_different_configurations_or_duplicate_instruments(self):
        from application.backtest_lab.sector_learning import pooled
        def report(instrument,candidate):
            exp={'experiment_id':instrument,'component':'volume_mode','baseline_hash':'base',
                 'candidate_hash':candidate,'results':[]}
            return {'instrument':instrument,'classification':{'sector':'Banks'},'experiments':[exp,exp]}
        groups=pooled([report('AAA','same'),report('BBB','same'),report('CCC','other')])['groups']
        self.assertEqual(sorted(x['instrument_count'] for x in groups),[1,2])
        a=report('AAA','same'); b=report('BBB','same')
        for x in (a,b):
            x['experiments'][0]['results']=[{'stage':'IN_SAMPLE','metrics':{'control_net':1,'candidate_net':2},
                                              'sample_counts':{'control_trades':1,'candidate_trades':2}}]
        self.assertEqual(pooled([a,b])['groups'][0]['stage_totals']['IN_SAMPLE']['candidate_net'],4)
    def test_funnel_counts_only_cumulative_passes(self):
        from application.backtest_lab.learning_loop import _summary
        obs=[{'trace':[{'c':'trend','state':'PASS'},{'c':'volume','state':'FAIL'}]},
             {'trace':[{'c':'trend','state':'UNKNOWN'},{'c':'volume','state':'PASS'}]},
             {'trace':[{'c':'trend','state':'PASS'},{'c':'volume','state':'PASS'}]}]
        result=_summary({'observations':obs,'trades':[],'signals':[]})
        self.assertEqual(result['cumulative_rule_funnel'],{'trend':2,'volume':1})
    def test_factorial_plan_has_four_distinct_matched_cells(self):
        from application.backtest_lab.learning_loop import factorial_plan,run_factorial_training,trial_weight
        design,cells=factorial_plan(self.base,'volume_mode','horizon')
        self.assertEqual(len(design.factors),2)
        self.assertEqual(len({x.config_hash for x in cells}),4)
        self.assertTrue(all(x.profile_id==self.base.profile_id for x in cells))
        result=run_factorial_training(self.repo,self.manifest,self.charts,self.base,'volume_mode','horizon',artifact_dir=self.path/'artifacts')
        self.assertEqual(result['state'],'COMPLETED')
        record=self.repo.get_experiment(result['experiment_id'],'1')
        self.assertEqual(len(record['results']),4);self.assertEqual(trial_weight(record['definition']),4)
        self.assertEqual(run_factorial_training(self.repo,self.manifest,self.charts,self.base,'volume_mode','horizon',artifact_dir=self.path/'artifacts')['state'],'ALREADY_COMPLETED')
    def test_interruption_after_run_record_resumes_without_another_proposal(self):
        from unittest.mock import patch
        calls=[]
        def proposer(context):
            calls.append(1)
            return {'component':'volume_mode','value':'off','rationale':'coverage'}
        with patch.object(self.repo,'record_result',side_effect=RuntimeError('simulated interruption')):
            with self.assertRaises(RuntimeError):
                run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=proposer)
        self.storage.close();self.storage=SQLiteRepository(self.path/'research.db')
        self.repo=DurableExperimentRepository(self.storage,account_id='research',namespace='component-test')
        result=run_cycle(self.repo,self.manifest,self.charts,self.base,artifact_dir=self.path/'artifacts',proposer=proposer)
        self.assertEqual(result['state'],'COMPLETED');self.assertEqual(len(calls),1)
        self.assertEqual(len(self.repo.get_experiment(result['experiment_id'],'1')['results']),2)

if __name__=='__main__':unittest.main()
