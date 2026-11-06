"""Matched setup, target-economics and exit experiments on frozen inputs."""
from collections import Counter,defaultdict
from dataclasses import asdict,replace
from datetime import timedelta
from decimal import Decimal
from statistics import median
from application.backtest_lab.components import Components,evaluate,signal_for
from application.backtest_lab.momentum_targets import features
from application.backtest_lab.zebra_field_windows import reference_segments
from domain.backtest.target_design_engine import Costs,Signal,replay


def source_rows(source):
    return [{'session':r['session'],**{k:(r.get('fields',{}).get(k) or {}).get('value')
             for k in ('open','high','low','close','volume')}} for r in source]


def peer_signals(instrument,rows,benchmark,config):
    """Call the real evaluator only for bars that can meet its entry trigger."""
    charts={instrument:rows,'ETF_STX40':benchmark};reference=[{'session':r['timestamp'][:10],'close':r['close']} for r in benchmark]
    found=[]
    for i in range(51,len(rows)):
        try:
            close=float(rows[i]['close'])
            if config.family=='box' and close<=max(float(r['high']) for r in rows[i-8:i]):continue
            if config.family=='pull' and close<=float(rows[i-1]['high']):continue
            trace,stop=evaluate(config,instrument,i,charts,reference_sessions=reference)
            if trace and all(x.get('ok') is True for x in trace) and stop is not None:found.append(i)
        except (TypeError,ValueError,KeyError):continue
    return found


def examples(rows,indices,horizon,instrument,scope):
    cache=[features(rows,i) for i in range(len(rows))];result=[]
    for i in indices:
        if i+horizon+1>=len(rows) or cache[i] is None:continue
        try:
            entry=float(rows[i+1]['close']);hi=max(float(x['high']) for x in rows[i+2:i+horizon+2])
            result.append({'instrument':instrument,'scope':scope,'signal_date':rows[i]['timestamp'][:10],
              'outcome_date':rows[i+horizon+1]['timestamp'][:10],'momentum':cache[i]['momentum_atr'],
              'change':cache[i]['momentum_change_atr'],'excursion_atr':max(0,(hi-entry)/cache[i]['atr'])})
        except (KeyError,TypeError,ValueError):continue
    return result


def matched_projection(rows,index,cases,scope):
    f=features(rows,index);day=rows[index]['timestamp'][:10]
    result={'status':'FIXED_TARGET_FALLBACK','sample_count':0,'scope':scope,'features':f}
    if f is None:return result
    matched=[c for c in cases if c['scope']==scope and c['outcome_date']<=day and
             (c['momentum']>=0)==(f['momentum_atr']>=0) and (c['change']>=0)==(f['momentum_change_atr']>=0)]
    result['sample_count']=len(matched);result['instruments']=dict(Counter(c['instrument'] for c in matched))
    if not matched:result['reason']='NO_MATURED_MATCHING_SETUPS';return result
    values=sorted(c['excursion_atr'] for c in matched);middle=median(values)
    result['median_atr']=middle;result['range_atr']=[values[int((len(values)-1)*.25)],values[int((len(values)-1)*.75)]]
    if middle<=0:result['reason']='NONPOSITIVE_ESTIMATE';return result
    result.update(status='PROJECTED',target_distance=middle*f['atr']);return result


def summarize_groups(trades,signal_regimes):
    buckets=defaultdict(list)
    for t in trades:
        buckets[('year',t['entry_session'][:4])].append(t)
        buckets[('regime',signal_regimes.get(t['id'],'UNKNOWN'))].append(t)
    return [{'type':kind,'name':name,'trades':len(group),'net':round(sum(float(t['net_pnl']) for t in group),2),
             'wins':sum(float(t['net_pnl'])>0 for t in group)} for (kind,name),group in sorted(buckets.items())]


def study(parent,manifest,charts,peer_charts,*,source_id):
    """Freeze one bounded research family; no model, training or execution."""
    cfg=Components(**parent['config']);rows=charts[manifest.instrument];lookup={r['timestamp'][:10]:i for i,r in enumerate(rows)}
    sig_ids=parent['calculations']['fixed_2r'];signals=[];index_by_id={};regimes={};estimates={}
    reference=[{'session':r['timestamp'][:10],'close':r['close']} for r in charts.get('ETF_STX40',[])]
    for sid in sorted(sig_ids):
        day=sid[-10:];i=lookup[day];trace,stop=evaluate(cfg,manifest.instrument,i,charts,reference_sessions=reference)
        if not trace or not all(x.get('ok') is True for x in trace) or stop is None:raise ValueError('frozen signal does not reproduce')
        old=signal_for(cfg,manifest.instrument,day,manifest.bars[i].available_at+timedelta(seconds=1),stop)
        signals.append(Signal(**asdict(old)));index_by_id[sid]=i
        f=features(rows,i);regimes[sid]=('UP' if f and f['momentum_atr']>=0 else 'DOWN')+' / '+('ACCELERATING' if f and f['momentum_change_atr']>=0 else 'SLOWING') if f else 'UNKNOWN'
    own=examples(rows,sorted(index_by_id.values()),cfg.horizon,manifest.instrument,'same_share')
    peer_cases=[];peer_counts={};target_industry=parent.get('target_industry')
    for name,segments in sorted(peer_charts.items()):
        industry=parent['peer_taxonomy'][name].get('industry');scope='same_industry' if target_industry and industry==target_industry else 'broader_sector'
        peer_counts[name]={'industry':industry,'scope':scope,'signals':0}
        for segment in segments:
            ix=peer_signals(name,segment,charts.get('ETF_STX40',[]),cfg);peer_counts[name]['signals']+=len(ix)
            peer_cases.extend(examples(segment,ix,cfg.horizon,name,scope))
    for s in signals:
        i=index_by_id[s.id]
        estimates[s.id]={scope:matched_projection(rows,i,own+peer_cases,scope) for scope in ('same_share','same_industry','broader_sector')}
    definitions={'fixed_2r':{},'matched_same_share':{'scope':'same_share'},
      'matched_same_industry':{'scope':'same_industry'},'matched_sector':{'scope':'broader_sector'},
      'matched_floor_net_1r':{'scope':'same_share','policy':'FLOOR'},
      'matched_reject_below_net_1r':{'scope':'same_share','policy':'REJECT'},
      'fixed_2r_atr_trail':{'trail':'ATR'},'fixed_2r_ema21_exit':{'exit_mode':'EMA21_CLOSE'},
      'fixed_2r_volume_filter':{'filter':'volume'},'fixed_2r_benchmark_filter':{'filter':'benchmark'}}
    costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
    bench={r['timestamp'][:10]:r['close'] for r in charts.get('ETF_STX40',[])};variants={}
    for name,spec in definitions.items():
        selected=[];skips=Counter()
        for s in signals:
            i=index_by_id[s.id];f=features(rows,i);kind=spec.get('filter')
            if kind=='volume':
                v=f.get('relative_volume') if f else None;threshold=1.2 if cfg.family=='box' else 1.1
                if v is None:skips['MISSING_VOLUME']+=1;continue
                if v<threshold:skips['VOLUME_BELOW_THRESHOLD']+=1;continue
            if kind=='benchmark':
                a=bench.get(rows[i-20]['timestamp'][:10]) if i>=20 else None;b=bench.get(rows[i]['timestamp'][:10])
                if a is None or b is None or float(a)<=0:skips['MISSING_BENCHMARK']+=1;continue
                if float(rows[i]['close'])/float(rows[i-20]['close'])-float(b)/float(a)<=0:skips['BENCHMARK_NOT_OUTPERFORMED']+=1;continue
            result=estimates[s.id].get(spec.get('scope')) or {};distance=result.get('target_distance')
            selected.append(replace(s,target_distance=Decimal(str(distance)) if distance else None,
              target_policy=spec.get('policy','UNCHANGED') if distance else 'UNCHANGED',trail=spec.get('trail','NONE'),
              exit_mode=spec.get('exit_mode','HORIZON_OR_TARGET')))
        res=replay([manifest],selected,as_of=max(b.available_at for b in manifest.bars)+timedelta(days=8),
                   initial_cash=Decimal(1000000),costs=costs)
        trades=res['trades'];eq=[float(x['equity']) for x in res['equity']];peak=0.;draw=0.
        for v in eq:
            peak=max(peak,v)
            if peak:draw=min(draw,v/peak-1)
        variants[name]={'signals':len(selected),'trades':len(trades),'net':round(sum(float(t['net_pnl']) for t in trades),2),
            'wins':sum(float(t['net_pnl'])>0 for t in trades),'max_drawdown_pct':round(draw*100,2),
            'target_hits':sum(t['reason'] in ('TARGET','GAP_TARGET_LIMIT') for t in trades),
            'filtered':dict(skips),'exit_reasons':dict(Counter(t['reason'] for t in trades)),
            'groups':summarize_groups(trades,regimes),'decisions':res['decisions'],'closed_trades':trades}
    return {'schema':'target-design-study-v1','source_report_id':source_id,'instrument':manifest.instrument,
      'family':cfg.family,'horizon':cfg.horizon,'window':parent['window'],'config':asdict(cfg),'peer_counts':peer_counts,
      'estimates':estimates,'variants':variants,'cost_basis':costs.basis,'live_execution':False,
      'limitations':['RESEARCH_NOT_PROMOTION','HYPOTHETICAL_COSTS','RECONSTRUCTED_HISTORICAL_AVAILABILITY',
        'UNKNOWN_HISTORICAL_CORPORATE_ACTIONS','CURRENT_PEER_CLASSIFICATION','OBSERVED_SESSION_CALENDAR',
        'STRATEGY_MATCHED_MFE_NOT_PROFIT','EXPLORATORY_NOT_OUT_OF_SAMPLE']}
