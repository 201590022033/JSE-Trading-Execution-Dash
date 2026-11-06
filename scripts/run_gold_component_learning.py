"""Run one bounded, no-model component cycle on retained JSE NewGold units."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.components import Components
from application.backtest_lab.learning_loop import _artifact, run_cycle
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.zebra_field_windows import valid_segments
from domain.backtest.products import GoldListed
from persistence.experiment_repo import DurableExperimentRepository
from persistence.sqlite_repository import SQLiteRepository
from scripts.backtest_gold_reference import load, ObservedGoldUnits
from scripts.local_runtime import process_lock

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold',required=True);parser.add_argument('--benchmark',required=True)
    parser.add_argument('--root',default=str(ROOT/'runtime/local-backtest/component-learning'))
    args=parser.parse_args();gold=load(args.gold,'GLD.JO');bench=load(args.benchmark,'STX40.JO')
    rows=[]
    for item in gold['rows']:
        if item['current_session_not_completed']:continue
        rows.append({'session':item['session'],**{field:(item[field]/100 if field!='volume' and item.get(field) is not None else item.get(field))
                    for field in ('open','high','low','close','volume')}})
    eligible=[segment for segment in valid_segments(rows,('open','high','low','close','volume')) if len(segment)>=100]
    if not eligible:raise ValueError('no eligible listed-gold research window')
    segment=eligible[-1]
    charts={'NEWGOLD':[{'timestamp':x['session'],**{k:x[k] for k in ('open','high','low','close','volume')}} for x in segment],
            'ETF_STX40':[{'timestamp':x['session'],'close':x['close']/100} for x in bench['rows']
                         if not x['current_session_not_completed'] and x.get('close')]}
    source_hash=Path(args.gold).stem.split('-')[-1]; benchmark_hash=Path(args.benchmark).stem.split('-')[-1]
    base=from_chart('NEWGOLD',{'bars':charts['NEWGOLD'],'provenance':{'provider':'YAHOO',
         'source_sha256':source_hash,'acquired_at':gold['acquired_at']}})
    manifest=ObservedGoldUnits(**{**vars(base),'product':'GOLD_ETF'})
    adapter=GoldListed('ZAR','ZAR',manifest.calendar_id,manifest.sessions,(),manifest.instrument)
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    lineage=_artifact(root/'inputs',{'instrument':'NEWGOLD','gold_source_sha256':source_hash,
        'benchmark_source_sha256':benchmark_hash,'gold_acquired_at':gold['acquired_at'],
        'benchmark_acquired_at':bench['acquired_at'],'rows':segment,'benchmark_rows':charts['ETF_STX40']})
    with process_lock(root/'worker.lock'):
        store=SQLiteRepository(root/'experiments.sqlite')
        try:
            if store.paper_account('component-research') is None:store.create_paper_account('component-research',{'mode':'PAPER'})
            repo=DurableExperimentRepository(store,account_id='component-research',namespace='component-learning-v3')
            outcome=run_cycle(repo,manifest,charts,Components(),artifact_dir=root/'artifacts',budget=8,
                              adapter=adapter,source_lineage=lineage)
            experiments=[]
            for definition in repo.list_experiments():
                if definition.instrument_scope != ('NEWGOLD',):continue
                bundle=repo.get_experiment(definition.experiment_id,definition.experiment_version)
                experiments.append({'experiment_id':definition.experiment_id,
                    'component':definition.changed_components[0] if len(definition.changed_components)==1 else 'INTERACTION',
                    'components':list(definition.changed_components),'baseline_hash':definition.baseline_id,
                    'candidate_hash':definition.treatment_config_hash,
                    'results':[{'stage':r.evidence_stage.value,'metrics':dict(r.metrics),'sample_counts':dict(r.sample_counts),
                                'diagnostics':dict(r.regime_breakdown),'cost_sensitivity':dict(r.cost_sensitivity),
                                'uncertainty':dict(r.uncertainty),'artifacts':[x.sha256 for x in r.artifacts]} for r in bundle['results']],
                    'decisions':[x.decision.value for x in bundle['decisions']]})
            status={'schema':'component-learning-status-v1','instrument':'NEWGOLD','classification':{'sector':'Gold listed ETF'},
                    'sector_proxy':'ETF_STX40','window':[segment[0]['session'],segment[-1]['session']],
                    'source_lineage_sha256':lineage.sha256,'outcomes':[outcome],'experiments':experiments,
                    'model_calls':0,'total_trial_budget':8,'live_execution':False,
                    'limitations':['JSE_LISTED_GOLD_UNITS_NOT_SPOT_GOLD','RECONSTRUCTED_HISTORICAL_AVAILABILITY',
                                   'EARLIER_FIXED_GOLD_DIAGNOSTICS_ARE_SEPARATE_FROM_THIS_JOURNAL']}
            target=root/'NEWGOLD.json';tmp=target.with_suffix('.tmp')
            tmp.write_text(json.dumps(status,sort_keys=True,indent=2),encoding='utf-8');tmp.replace(target)
            print(json.dumps({'state':outcome['state'],'experiment_id':outcome.get('experiment_id'),
                'window':status['window'],'experiments':len(experiments),'source_lineage_sha256':lineage.sha256,
                'model_calls':0,'live_execution':False}))
        finally:store.close()

if __name__=='__main__':main()
