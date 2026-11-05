"""Fixed exploratory swing variants on retained Zebra histories; no model or orders."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.opportunities.swing_historical_inputs import prepare_v3_research
from application.opportunities.swing_research import BASELINE, evaluate
from application.opportunities.research_classification import classifications

VARIANTS = (
    ('baseline', dict(BASELINE), None),
    ('volume_0_8', {**BASELINE, 'volume_min': 0.8}, None),
    ('close_above_ema50', dict(BASELINE), 'CLOSE_ABOVE_EMA50'),
)

def windows(dates):
    if len(dates) < 150: raise ValueError('150 observed sessions required')
    a, b = len(dates)*3//5, len(dates)*4//5
    return [{'name': n, 'start': dates[i], 'end': dates[j-1]} for n,i,j in
            (('training',50,a), ('validation',a,b), ('holdout',b,len(dates)))]

def run(history, sector):
    charts=history['charts']; universe=sorted(k for k in charts if k!='ETF_STX40')
    labels=classifications(universe)['instruments']
    instruments=[k for k in universe if labels[k]['sector']==sector]
    if not instruments: raise ValueError('unknown or empty sector')
    dates=sorted({r['timestamp'] for k in instruments for r in charts[k]['bars']})
    periods=windows(dates)
    out=[]; cache={}
    for name,params,entry in VARIANTS:
        scores={}
        for w in periods:
            scores[w['name']]=evaluate(charts,params,w['start'],w['end'],sector=sector,universe=universe,research_entry=entry,feature_cache=cache)
        out.append({'id':name,'parameters':params,'trend':entry or 'BASELINE_TREND','windows':scores})
    return {'schema':'sector-swing-exploration-v1','sector':sector,'instruments':instruments,
        'windows':periods,'variants':out,'source_receipts':history['source_receipts'],
        'input_sha256':hashlib.sha256(json.dumps(charts,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        'limitations':history['limitations']+['FIXED_EXPLORATORY_VARIANTS_NOT_PRE_REGISTERED',
         'NONOVERLAP_PER_INSTRUMENT_NOT_SHARED_PORTFOLIO', 'NO_AI_PROPOSAL_OR_MODEL_TRAINING',
         'SHADOW_STOP_AND_EXIT_POLICY_WITH_RESEARCH_ENTRY_VARIANTS', 'HYPOTHETICAL_COST_SCENARIOS'],
        'research_only':True,'live_execution':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--sector');g.add_argument('--all',action='store_true');args=p.parse_args()
    now=datetime.now(timezone.utc)
    history=prepare_v3_research(json.loads(Path('runtime/local-swing-data/latest.json').read_bytes()),now)
    keys=sorted(k for k in history['charts'] if k!='ETF_STX40')
    sectors=sorted({v['sector'] for v in classifications(keys)['instruments'].values()}) if args.all else [args.sector]
    for sector in sectors:
        try:
            result=run(history,sector);result['created_at']=datetime.now(timezone.utc).isoformat()
            raw=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            path=Path('runtime/local-backtest/sector-exploration')/(hashlib.sha256(raw).hexdigest()+'.json')
            path.parent.mkdir(parents=True,exist_ok=True)
            if not path.exists(): path.write_bytes(raw)
            print(json.dumps({'state':'AVAILABLE','path':str(path),'sector':sector,'windows':result['windows'],
                'summary':{v['id']:{w:v['windows'][w]['sample_count'] for w in ('training','validation','holdout')} for v in result['variants']},
                'live_execution':False}),flush=True)
        except ValueError as exc:
            if not args.all: raise
            print(json.dumps({'state':'UNAVAILABLE','sector':sector,'reason':str(exc)}),flush=True)
