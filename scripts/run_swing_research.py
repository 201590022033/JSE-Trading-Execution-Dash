"""Explicit bounded research evaluation; same daily AI budget as scheduled runs."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import json
import argparse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_persistence import runtime_repository
from application.opportunities.swing_research import run_research

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sector', help='Optional exact research-sector label')
    parser.add_argument('--local-zebra',action='store_true', help='Use retained local v3 Zebra research sources')
    parser.add_argument('--historical',action='store_true', help='Allow older v1/v2 inputs as labelled historical research')
    parser.add_argument('--preview',action='store_true', help='Inspect local historical readiness without a model call')
    args=parser.parse_args()
    local_path=Path(__file__).resolve().parents[1]/'runtime/local-swing-data/latest.json'
    if args.preview:
        from application.opportunities.swing_historical_inputs import prepare_v3_research
        from application.opportunities.research_classification import classifications
        dataset=json.loads(local_path.read_bytes())
        result=prepare_v3_research(dataset,datetime.now(timezone.utc))
        keys=[k for k in result['charts'] if k!='ETF_STX40']
        labels=classifications(keys)['instruments']
        if args.sector:
            keys=[k for k in keys if labels[k]['sector']==args.sector]
        sessions=sorted({r['timestamp'] for key in keys for r in result['charts'][key]['bars']})
        state='NO_SECTOR_HISTORY' if not keys else 'HISTORICAL_RESEARCH_READY' if len(sessions)>=130 else 'MORE_HISTORY_REQUIRED'
        from application.opportunities.swing_research import swing_cloud_provider
        print(json.dumps({'state':state,'observed_sessions':len(sessions),
                          'sector_scope':args.sector or 'ALL','instruments':keys,'freshness':result['freshness'],
                          'instrument_freshness':{k:result['instrument_freshness'][k] for k in keys},
                          'source':result['source'],'limitations':result['limitations'],
                          'model_configured':bool(swing_cloud_provider()[1].key),
                          'model_called':False,'live_execution':False},sort_keys=True))
        sys.exit(0)
    repository = runtime_repository()
    try:
        override=json.loads(local_path.read_bytes()) if args.local_zebra else None
        result = run_research(repository, datetime.now(timezone.utc), sector=args.sector,dataset_override=override,allow_historical=args.historical)
        print(json.dumps({"state": result["state"], "sector_scope":result.get('sector_scope',args.sector or 'ALL'), "provider": (result.get("proposal") or {}).get("provider"),
                          "holdout_baseline": result.get("holdout_baseline"),
                          "holdout_variant": result.get("holdout_variant"), "live_execution": False}))
    finally:
        repository.close()
