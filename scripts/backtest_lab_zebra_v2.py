"""Freeze an availability-first, multi-share Zebra replay, offline and research only."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.backtest_lab.zebra_field_windows import FIELDS, valid_segments, benchmark_for, evaluate_mixed
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.strategies import PROFILES
from application.opportunities.zebra_screen_data import load_zebra_screen_data
from domain.backtest.engine import Costs, Signal, replay


def build(data, selected=None, segment_index=-1):
    charts={}; manifests=[]; coverage={}; proxies={}; field_lineage={}
    instruments=data['instruments']
    for key,item in sorted(instruments.items()):
        if item.get('asset_class')!='cash_equity' or (selected and key not in selected): continue
        segments=valid_segments(item['rows'],FIELDS)
        usable=[s for s in segments if len(s)>=52]
        coverage[key]={'segments':len(segments),'eligible_segments':len(usable),
                       'eligible_windows':[[s[0]['session'],s[-1]['session']] for s in usable],
                       'observed_rows':len(item['rows']),'selected_segment':None}
        if not usable: continue
        # Each segment is replayable independently; never join across gaps.
        if not -len(usable) <= segment_index < len(usable): continue
        segment=usable[segment_index]; coverage[key]['selected_segment']=[segment[0]['session'],segment[-1]['session']]
        rows=[{'timestamp':r['session'],**{f:r[f] for f in FIELDS},
               '_source':r.get('fields',{}).get('close',{}).get('source')} for r in segment]
        sources=[r.get('fields',{}) for r in segment]; field_lineage[key]=sources
        receipts=[v for row in sources for v in row.values() if isinstance(v,dict) and v.get('source_sha256')]
        if not receipts: continue
        latest=max(receipts,key=lambda r:r.get('acquired_at',''))
        provenance={'provider':'ZEBRA_FIELD_BRANCH','source_sha256':latest['source_sha256'],
                    'acquired_at':latest['acquired_at']}
        charts[key]=rows;manifests.append(from_chart(key,{'bars':rows,'provenance':provenance}))
        proxies[key]=benchmark_for(item,instruments)
    if not manifests: raise ValueError('no complete contiguous 52-session OHLCV research segment')
    for name,item in instruments.items():
        if item.get('asset_class') in ('index_etf','listed_etf'):
            charts[name]=[{'timestamp':r['session'],'close':r['close']} for r in item['rows'] if r.get('close') is not None]
    as_of=max(b.available_at for m in manifests for b in m.bars)+timedelta(days=8)
    costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
    results=[]
    for sid,name,profile,version in PROFILES:
        signals=[];traces=[];rejected=[];count=0;passed=None;last_conditions=[]
        for m in manifests:
            rows=charts[m.instrument]; local=dict(charts)
            benchmark=proxies[m.instrument]['instrument']
            local['ETF_STX40']=charts.get(benchmark,[]) if benchmark else []
            for i in range(50,len(rows)):
                conditions,stop=evaluate_mixed(sid,m.instrument,i,local)
                if not conditions: continue
                last_conditions=conditions;count+=1
                if passed is None: passed=[0]*len(conditions)
                for k in range(len(conditions)):
                    if all(c['ok'] for c in conditions[:k+1]):passed[k]+=1
                if not all(c['ok'] for c in conditions):
                    rejected.append({'inst':m.instrument,'session':rows[i]['timestamp'],'trace':conditions})
                elif stop is not None:
                    ident=m.instrument+'-'+rows[i]['timestamp']
                    signals.append(Signal(ident,m.instrument,rows[i]['timestamp'],m.bars[i].available_at+timedelta(seconds=1),
                        Decimal(str(stop)),Decimal(420000),Decimal(12000),horizon=3,target_r=Decimal(2),
                        strategy_profile_id=profile,strategy_profile_version=version))
                    traces.append({'id':ident,'inst':m.instrument,'session':rows[i]['timestamp'],'stop':stop,'trace':conditions})
        output=replay(manifests,signals,as_of=as_of,initial_cash=Decimal(1000000),costs=costs)
        trades=output['trades'];eq=output['equity'];peak=1000000;dd=0
        for e in eq:
            v=float(e['equity']);peak=max(peak,v);dd=min(dd,v/peak-1)
        net=float(eq[-1]['equity'])-1000000 if eq else 0
        results.append({'id':sid,'name':name,'source':'Zebra field research v2',
            'desc':'Fixed three-session horizon or 2R; no EMA21-close exit.',
            'strategy_profile_id':profile,'strategy_profile_version':version,
            'conds':[c['c'] for c in last_conditions],'funnel':{'checked':count,'passed':passed or []},
            'sum':{'signals':len(signals),'traded':len(trades),'win':round(sum(float(t['net_pnl'])>0 for t in trades)/len(trades)*100) if trades else None,
                   'net':round(net,2),'mdd':round(dd*100,2),'stocks':len({t['instrument'] for t in trades}),
                   'verdict':'Incubate: fewer than 30 trades, inconclusive' if len(trades)<30 else 'Watchlist: research only'},
            'engine_config_hash':output['config_hash'],'run':{'signals':traces,'rejected_bars':rejected,
                'decisions':output['decisions'],'trades':trades,'equity':eq}})
    bars={m.instrument:[[r['timestamp'],r['open'],r['high'],r['low'],r['close']] for r in charts[m.instrument]] for m in manifests}
    meta={'grade':'ASSUMPTION_LIMITED','limitations':['FULL_FILL_ASSUMPTION','CLOSE_PROXY_NOT_BROKER_FILL',
        'DAILY_INTRABAR_PATH_UNKNOWN','RECONSTRUCTED_HISTORICAL_AVAILABILITY',
        'PRICE_ADJUSTMENT_AND_CORPORATE_ACTIONS_UNVERIFIED','ONE_SELECTED_SEGMENT_PER_INSTRUMENT',
        'SECTOR_CLASSIFICATION_IS_CURRENT_RESEARCH_PROXY'],
        'cost_basis':costs.basis,'initial_cash':1000000,'created_at':as_of.isoformat(),
        'created_at_basis':'RECONSTRUCTED_REPLAY_AS_OF_NOT_WALL_CLOCK','data_basis':'ZEBRA_FIELD_RESEARCH_V2',
        'coverage':coverage,'sector_benchmarks':proxies,'field_lineage':field_lineage,'live_execution':False}
    identity={'bars':bars,'strategies':results,'meta':meta}
    digest=sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {**identity,'meta':{**meta,'config_hash':digest}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--instrument',action='append');p.add_argument('--output-dir')
    p.add_argument('--segment-index',type=int,default=-1,help='Eligible segment index per instrument (default: latest)')
    args=p.parse_args()
    folder=Path(args.output_dir or os.environ.get('LOCAL_BACKTEST_REPORT_DIR',''))/'lab'
    if not args.output_dir and not os.environ.get('LOCAL_BACKTEST_REPORT_DIR'):p.error('set output directory')
    run=build(load_zebra_screen_data(),set(args.instrument) if args.instrument else None,args.segment_index)
    folder.mkdir(parents=True,exist_ok=True);target=folder/(run['meta']['config_hash']+'.json')
    raw=(json.dumps(run,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
    if target.exists() and target.read_bytes()!=raw:raise ValueError('frozen report collision')
    if not target.exists():target.write_bytes(raw)
    print(json.dumps({'path':str(target),'run_id':target.stem,'instruments':list(run['bars']),
      'checked':{s['id']:s['funnel']['checked'] for s in run['strategies']},
      'trades':{s['id']:s['sum']['traded'] for s in run['strategies']}},ensure_ascii=True))
if __name__=='__main__':main()
