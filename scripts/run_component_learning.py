"""Run bounded component cycles on retained Zebra stock histories."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.components import Components
from application.backtest_lab.learning_loop import run_cycle, run_factorial_training, _artifact, trial_weight
from application.backtest_lab.learning_journal import LearningJournal
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.zebra_field_windows import FIELDS,valid_segments
from application.opportunities.zebra_screen_data import load_zebra_screen_data
from persistence.experiment_repo import DurableExperimentRepository
from persistence.sqlite_repository import SQLiteRepository

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',default='runtime/local-backtest/component-learning')
    p.add_argument('--instrument',default='SASOL');p.add_argument('--cycles',type=int,default=2)
    p.add_argument('--family',choices=('swing','box','pull','vcp'),default='swing',
                   help='Choose the existing strategy family; the instrument trial budget stays shared')
    p.add_argument('--cloud',action='store_true',help='Explicitly use the existing single daily swing AI budget')
    p.add_argument('--override-id',help='One separately recorded owner-authorized cloud attempt')
    p.add_argument('--factorial',action='store_true',help='Register four volume/horizon interaction cells')
    p.add_argument('--status-only',action='store_true',help='Refresh read-only summaries without a trial or model call')
    p.add_argument('--no-context',action='store_true',help='Use the price-only control')
    a=p.parse_args()
    if not 1<=a.cycles<=3: p.error('cycles must be 1 to 3')
    if a.override_id and not a.cloud:p.error('--override-id requires --cloud')
    if a.status_only and (a.cloud or a.factorial):p.error('--status-only cannot run trials or models')
    from application.opportunities.research_classification import classifications
    from application.backtest_lab.zebra_field_windows import SECTOR_PROXY
    import re
    if not re.fullmatch(r'[A-Z0-9_]{2,16}',a.instrument):p.error('canonical instrument required')
    classification=classifications([a.instrument])['instruments'][a.instrument]
    sector=SECTOR_PROXY.get(classification['sector']) or ('ETF_STXIND' if a.instrument=='BTI' else 'ETF_STX40')
    data=load_zebra_screen_data(instruments={a.instrument,sector,'ETF_STX40'})
    stock=data['instruments'][a.instrument]
    segments=[s for s in valid_segments(stock['rows'],('open','high','low','close')) if len(s)>=100]
    if not segments: raise ValueError('no eligible stock history segment')
    seg=segments[-1]
    proxy=data['instruments'].get(sector) or data['instruments'].get('ETF_STX40')
    charts={a.instrument:[{'timestamp':r['session'],**{f:r[f] for f in FIELDS}} for r in seg]}
    if proxy: charts['ETF_STX40']=[{'timestamp':r['session'],'close':r['close']} for r in proxy['rows'] if r.get('close') is not None]
    source=next(v for row in reversed(seg) for v in row.get('fields',{}).values() if isinstance(v,dict) and v.get('source_sha256'))
    manifest=from_chart(a.instrument,{'bars':charts[a.instrument],'provenance':{'provider':'ZEBRA_FIELD_BRANCH',
        'source_sha256':source['source_sha256'],'acquired_at':source['acquired_at']}})
    root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    context_items=[];context_report_id=None
    if not a.no_context:
        from hashlib import sha256
        reports=ROOT/'runtime/local-backtest/context-research'
        if reports.is_dir():
            for path in sorted(reports.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
                try:
                    raw=path.read_bytes()
                    if len(raw)>16_000_000 or sha256(raw).hexdigest()!=path.stem:continue
                    report=json.loads(raw)
                    if report.get('schema')=='m5-sens-coverage-v1' and report.get('instrument')==a.instrument:
                        context_items=report.get('relevant_sources',[]);context_report_id=path.stem;break
                except (OSError,ValueError,TypeError):continue
    store=SQLiteRepository(root/'experiments.sqlite');cloud_store=None;proposer=None
    try:
        if a.cloud:
            from runtime_persistence import runtime_repository
            from application.backtest_lab.cloud_component_proposer import BudgetedCloudProposer
            cloud_store=runtime_repository();proposer=BudgetedCloudProposer(cloud_store,override_id=a.override_id)
        if store.paper_account('component-research') is None:store.create_paper_account('component-research',{'mode':'PAPER'})
        # Keep the initial prototype records isolated; the later code-hashed
        # implementation starts its own namespace without deleting any evidence.
        repo=DurableExperimentRepository(store,account_id='component-research',namespace='component-learning-v3')
        rows=store._job_sql('SELECT payload FROM paper_records WHERE account_id=?',('component-research',),rows=True)
        namespaces={json.loads(row[0]).get('namespace') for row in rows if json.loads(row[0]).get('schema')=='durable-experiment-record-v1'}
        namespaces.discard(None);namespaces.discard('component-learning-v3')
        prior_trials=sum(trial_weight(d) for ns in namespaces
            for d in DurableExperimentRepository(store,account_id='component-research',namespace=ns).list_experiments()
            if d.instrument_scope==(a.instrument,) and d.created_by=='component-learning-v1')
        current_budget=8-prior_trials
        if current_budget<1 and not a.status_only:raise ValueError('historical component trial budget exhausted')
        training_volume=all(row.get('volume') is not None for row in seg[:len(seg)*60//100])
        if a.family=='swing':
            base=Components(benchmark_mode='outperform' if proxy else 'off',
                            volume_mode='threshold' if training_volume else 'off')
        else:
            profiles={'box':('box_breakout_daily_research',1.2),
                      'pull':('pullback_daily_research',1.1),'vcp':('vcp_daily_research',1.3)}
            profile,threshold=profiles[a.family]
            base=Components(family=a.family,profile_id=profile,profile_version='1.0.0',
                entry='family_default',momentum=False,benchmark_mode='off',stop_mode='family',
                volume_mode='threshold' if training_volume else 'off',volume_min=threshold)
        # Immutable per-field source observations, including the benchmark,
        # remain linked to this run even if the Zebra selection later changes.
        inputs=_artifact(root/'inputs',{'instrument':a.instrument,'rows':seg,
            'benchmark':sector if proxy is data['instruments'].get(sector) else 'ETF_STX40' if proxy else None,
            'benchmark_rows':proxy.get('rows',[]) if proxy else []})
        previous_status={}
        status_path=root/(a.instrument+('' if a.family=='swing' else '_'+a.family.upper())+'.json')
        if a.status_only and status_path.is_file():previous_status=json.loads(status_path.read_text(encoding='utf-8'))
        outcomes=previous_status.get('outcomes',[]);jobs=previous_status.get('jobs',[])
        from scripts.local_runtime import process_lock
        from hashlib import sha256
        code={str(p):sha256((ROOT/p).read_bytes()).hexdigest() for p in (
            'application/backtest_lab/learning_loop.py','application/backtest_lab/components.py',
            'application/backtest_lab/component_replay.py','application/backtest_lab/cloud_component_proposer.py',
            'application/backtest_lab/learning_journal.py','application/backtest_lab/research_context.py','domain/backtest/component_engine.py')}
        with process_lock(root/'worker.lock'):
            journal=LearningJournal(root/'queue.sqlite')
            try:
                for cycle in range(1,1 if a.status_only else a.cycles+1):
                    spec={'instrument':a.instrument,'cycle':cycle,'data':manifest.sha256,'input_artifact':inputs.sha256,
                          'code':code,'mode':'cloud' if a.cloud else 'deterministic','override_id':a.override_id,
                          'context_report':context_report_id}
                    job=journal.enqueue(spec)
                    if journal.claim(job,recover=True):
                        try:
                            result=run_cycle(repo,manifest,charts,base,artifact_dir=root/'artifacts',cycle=cycle,proposer=proposer,budget=current_budget,source_lineage=inputs,context_items=context_items)
                            journal.finish(job,'COMPLETED',result)
                        except Exception as exc:
                            journal.finish(job,'FAILED',{'error_category':type(exc).__name__})
                            raise
                    record=journal.get(job);jobs.append({'id':job,'state':record['state'],'attempt':record['attempt']})
                    outcomes.append(record['result'])
                if a.factorial and not training_volume:
                    outcomes.append({'state':'FACTORIAL_VOLUME_UNAVAILABLE','reason':'Price-only cycles remain available',
                                     'live_execution':False})
                if a.factorial and training_volume:
                    spec={'instrument':a.instrument,'kind':'factorial-volume-horizon','data':manifest.sha256,
                          'input_artifact':inputs.sha256,'code':code}
                    job=journal.enqueue(spec)
                    if journal.claim(job,recover=True):
                        try:
                            result=run_factorial_training(repo,manifest,charts,base,'volume_mode','horizon',
                                artifact_dir=root/'artifacts',budget=current_budget,source_lineage=inputs)
                            journal.finish(job,'COMPLETED',result)
                        except Exception as exc:
                            journal.finish(job,'FAILED',{'error_category':type(exc).__name__});raise
                    record=journal.get(job);jobs.append({'id':job,'state':record['state'],'attempt':record['attempt']})
                    outcomes.append(record['result'])
                holdout=journal.holdout_status(a.instrument);jobs=journal.jobs(a.instrument)
            finally:journal.close()
        details=[]
        for d in repo.list_experiments():
            if d.instrument_scope != (a.instrument,) or d.strategy_family != a.family:continue
            bundle=repo.get_experiment(d.experiment_id,d.experiment_version)
            details.append({'experiment_id':d.experiment_id,
                'component':d.changed_components[0] if len(d.changed_components)==1 else 'INTERACTION',
                'components':list(d.changed_components),
                'baseline_hash':d.baseline_id,'candidate_hash':d.treatment_config_hash,
                'results':[{'stage':r.evidence_stage.value,'metrics':dict(r.metrics),'sample_counts':dict(r.sample_counts),
                    'diagnostics':dict(r.regime_breakdown),'cost_sensitivity':dict(r.cost_sensitivity),'uncertainty':dict(r.uncertainty),
                    'artifacts':[x.sha256 for x in r.artifacts]} for r in bundle['results']],
                'decisions':[x.decision.value for x in bundle['decisions']]})
        status={'schema':'component-learning-status-v1','instrument':a.instrument,'family':a.family,'classification':classification,
            'sector_proxy':sector if proxy is data['instruments'].get(sector) else 'ETF_STX40' if proxy else None,
            'window':[seg[0]['session'],seg[-1]['session']],'outcomes':outcomes,'experiments':details,
            'jobs':jobs,'source_lineage_sha256':inputs.sha256,
            'context_report_sha256':context_report_id,'retained_context_sources':len(context_items),
            'holdout':holdout,'model_calls':previous_status.get('model_calls',0) if a.status_only else proposer.model_calls if proposer else 0,
            'historical_component_trials':prior_trials+sum(trial_weight(d) for d in repo.list_experiments() if d.instrument_scope==(a.instrument,)),
            'total_trial_budget':8,'live_execution':False}
        target=status_path;tmp=target.with_suffix('.tmp')
        tmp.write_text(json.dumps(status,sort_keys=True,indent=2),encoding='utf-8');tmp.replace(target)
        print(json.dumps(status,sort_keys=True))
    finally:
        store.close()
        if cloud_store is not None:cloud_store.close()
if __name__=='__main__':main()
