"""Explicit one-attempt sector-family proposal using training-only frozen evidence."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json, os, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_config import project_environment
from scripts.local_runtime import configuration, verify_database
from runtime_persistence import runtime_repository
from application.backtest_lab.blueprint import _read
from application.backtest_lab.sector_hypothesis import prepare, prompt, validate, evaluate_choice
from application.opportunities.swing_research import ACCOUNT, initialize, swing_cloud_provider, proposal_failure_code, digest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True);parser.add_argument('--sector',required=True);parser.add_argument('--preview',action='store_true')
    args=parser.parse_args(); run=_read(Path('runtime/local-backtest/lab'),args.run_id)
    context, report=prepare(run,args.sector)
    if args.preview:
        print(json.dumps({'state':'READY','training_context':context,'model_called':False,'live_execution':False}));sys.exit()
    now=datetime.now(timezone.utc);folder=Path('runtime/local-migration/fresh-20261015')
    env=project_environment();env.update(json.loads((folder/'environment.json').read_text()))
    url,identity=configuration(env,json.loads((folder/'bootstrap-acceptance.json').read_text()),now);verify_database(url,identity)
    os.environ['DATABASE_URL']=url
    router,provider=swing_cloud_provider()
    if not provider.key:
        print(json.dumps({'state':'AI_NOT_CONFIGURED','model_called':False,'live_execution':False}));sys.exit()
    repository=runtime_repository()
    try:
        initialize(repository)
        run_key='sector-family-'+digest({'run_id':args.run_id,'sector':args.sector,'context':context})
        existing=repository.paper_record(run_key)
        if existing:
            print(json.dumps({'state':'ALREADY_RECORDED','result':existing,'model_called':False,'live_execution':False}));sys.exit()
        reservation='swing-ai-budget-'+now.date().isoformat()
        with repository.paper_account_transaction(ACCOUNT):
            if repository.paper_record(reservation):
                print(json.dumps({'state':'DAILY_AI_BUDGET_USED','model_called':False,'live_execution':False}));sys.exit()
            repository.save_paper_record(reservation,ACCOUNT,'research-ai-budget',now.isoformat(),{'reserved':True,'purpose':'sector_family'})
        try:
            choice=validate(router._request(provider,prompt(context)),context['strategy_ids'])
            result={'state':'PROPOSED_AND_COMPARED','proposal':choice,
                'comparison':evaluate_choice(report,args.sector,choice),'failure_code':None}
        except Exception as exc:
            result={'state':'AI_PROPOSAL_UNAVAILABLE_OR_REJECTED','proposal':None,'failure_code':proposal_failure_code(exc)}
        result.update({'run_id':args.run_id,'sector':args.sector,'created_at':now.isoformat(),
            'training_context':context,'windows':report['windows'],'limitations':report['limitations'],
            'model':provider.model,'research_only':True,'live_execution':False})
        repository.save_paper_record(run_key,ACCOUNT,'sector-family-proposal',now.isoformat(),result)
        print(json.dumps(result))
    finally: repository.close()
