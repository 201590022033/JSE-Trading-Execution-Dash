"""Point-in-time, matched-signal target projections for retrospective research."""
from dataclasses import asdict
from datetime import timedelta
from decimal import Decimal
from statistics import mean, median
from application.backtest_lab.component_replay import run_components
from application.backtest_lab.components import signal_for
from domain.backtest.momentum_target_engine import Costs, Signal, replay

VARIANTS = ('fixed_2r', 'momentum', 'momentum_volume', 'momentum_sector')


def prepare_peers(peer_charts, horizon):
    """Precompute peer windows; each retains its real outcome end date."""
    result=[]
    for instrument,segments in sorted(peer_charts.items()):
        for rows in segments:
            cache=[features(rows,j) for j in range(len(rows))]
            for j in range(15,len(rows)-horizon-1):
                f=cache[j]
                if not f:continue
                try:
                    entry=float(rows[j+1]['close'])
                    excursion=max(0.,(max(float(r['high']) for r in rows[j+2:j+horizon+2])-entry)/f['atr'])
                    result.append({'instrument':instrument,'signal_day':rows[j]['timestamp'][:10],
                                   'outcome_day':rows[j+horizon+1]['timestamp'][:10],
                                   'momentum_atr':f['momentum_atr'],'change_atr':f['momentum_change_atr'],
                                   'excursion_atr':excursion})
                except (ValueError,TypeError,KeyError):continue
    return result


def peer_projection(rows,i,horizon,peer_cases,feature_cache=None):
    current=feature_cache[i] if feature_cache is not None else features(rows,i)
    result={'variant':'momentum_peers','features':current,'sample_count':0,
            'status':'FIXED_TARGET_FALLBACK','basis':'SAME_CURRENT_SECTOR_NOT_NECESSARILY_SAME_INDUSTRY'}
    if current is None:return result
    day=rows[i]['timestamp'][:10]
    eligible=[p for p in peer_cases if p['outcome_day']<=day and
              (p['momentum_atr']>=0)==(current['momentum_atr']>=0) and
              (p['change_atr']>=0)==(current['momentum_change_atr']>=0)]
    values=sorted(p['excursion_atr'] for p in eligible);result['sample_count']=len(values)
    result['peer_counts']={name:sum(p['instrument']==name for p in eligible) for name in sorted({p['instrument'] for p in eligible})}
    if not values:result['reason']='NO_MATURED_PEER_COMPARABLES';return result
    mid=median(values);result.update(range_atr=[values[int((len(values)-1)*.25)],values[int((len(values)-1)*.75)]],estimated_move_atr=mid)
    if mid<=0:result['reason']='NONPOSITIVE_PROJECTED_MOVE';return result
    result.update(status='PROJECTED',target_distance=mid*current['atr'])
    return result


def timed_context(items,instrument,decision_at,*,days=30,signal_session=None):
    """Mark source text known by acquisition and receipt, including date-only notices."""
    from datetime import date,datetime,timezone,timedelta
    from application.backtest_lab.research_context import _at
    cutoff=_at(decision_at)
    if cutoff is None:raise ValueError('aware decision required')
    signal_day=date.fromisoformat(signal_session) if signal_session else cutoff.date()
    available=[];retrospective=[];unknown=0;later=0
    for item in items:
        if item.get('instrument')!=instrument:continue
        published=item.get('publication_date') or ((item.get('published_at') or '')[:10] or None)
        try:
            age=(signal_day-date.fromisoformat(published)).days if published else None
        except (TypeError,ValueError):age=None
        clocks=[_at(item.get(k)) for k in ('acquired_at','source_received_at','received_at')]
        if any(t is None for t in clocks):
            unknown+=1
            if age is not None and 0<=age<=days:retrospective.append({'source_id':item.get('source_id'),'headline':item.get('headline'),
                'provider':item.get('provider'),'url':item.get('url'),'publication_date':published,
                'acquired_at':item.get('acquired_at'),'received_at':item.get('received_at'),'reason':'RECEIPT_CLOCK_UNKNOWN'})
            continue
        known=max(clocks);pub=_at(item.get('published_at'))
        if pub is not None:known=max(known,pub)
        elif item.get('publication_date') and item['publication_date']>known.date().isoformat():
            unknown+=1;continue
        if known>cutoff:
            later+=1
            if age is not None and 0<=age<=days:retrospective.append({'source_id':item.get('source_id'),'headline':item.get('headline'),
                'provider':item.get('provider'),'url':item.get('url'),'publication_date':published,
                'acquired_at':item.get('acquired_at'),'received_at':item.get('received_at'),'reason':'CAPTURED_AFTER_SIGNAL'})
            continue
        if cutoff-known<=timedelta(days=days):
            available.append({'source_id':item.get('source_id'),'headline':item.get('headline'),
                              'provider':item.get('provider'),'url':item.get('url'),
                              'published_at':item.get('published_at'),'publication_date':item.get('publication_date'),
                              'publication_precision':item.get('publication_precision'),'known_at':known.isoformat(),
                              'acquired_at':item.get('acquired_at'),'received_at':item.get('received_at')})
    return {'known_recent':available,'retrospective_recent':retrospective,'later_records':later,'unknown_clock_records':unknown,
            'basis':'FIRST_ACTUAL_CAPTURE_AND_RECEIPT_NOT_INFERRED_PUBLICATION_TIME'}


def features(rows, i, benchmark=None):
    """Trailing observations only; no filling in missing volume or benchmark."""
    if i < 15:
        return None
    try:
        closes = [float(r['close']) for r in rows[i-15:i+1]]
        true_ranges = [max(float(rows[k]['high'])-float(rows[k]['low']),
                           abs(float(rows[k]['high'])-float(rows[k-1]['close'])),
                           abs(float(rows[k]['low'])-float(rows[k-1]['close']))) for k in range(i-13,i+1)]
        atr = mean(true_ranges)
        if atr <= 0 or min(closes) <= 0: return None
        # Five-day directional movement and its change versus the prior five.
        momentum = (closes[-1]-closes[-6])/atr
        previous = (closes[-6]-closes[-11])/atr
        volume = None
        if i >= 20:
            vals = [rows[k].get('volume') for k in range(i-20,i+1)]
            if all(v is not None for v in vals) and mean(float(v) for v in vals[:-1]) > 0:
                volume = float(vals[-1])/mean(float(v) for v in vals[:-1])
        sector = None
        if benchmark:
            mapping = benchmark if isinstance(benchmark,dict) else {r['timestamp'][:10]:r.get('close') for r in benchmark}
            a,b = mapping.get(rows[i-5]['timestamp'][:10]),mapping.get(rows[i]['timestamp'][:10])
            if a is not None and b is not None and float(a)>0: sector=float(b)/float(a)-1
        return {'atr':atr,'momentum_atr':momentum,'momentum_change_atr':momentum-previous,
                'relative_volume':volume,'benchmark_return5':sector}
    except (KeyError,TypeError,ValueError,ZeroDivisionError):
        return None


def projection(rows, i, horizon, variant, benchmark=None, feature_cache=None):
    """Compare same-instrument earlier regimes, with fully matured outcomes.

    Entry is the next observed close; the following horizon highs are measured.
    These excursions are descriptive, not executable profits or hit probabilities.
    """
    current=feature_cache[i] if feature_cache is not None else features(rows,i,benchmark)
    result={'variant':variant,'features':current,'sample_count':0,'status':'FIXED_TARGET_FALLBACK'}
    if current is None:return result
    field={'momentum_volume':'relative_volume','momentum_sector':'benchmark_return5'}.get(variant)
    if field and current[field] is None:
        result['reason']='OPTIONAL_CONTEXT_MISSING';return result
    examples=[]
    # j + 1 is entry, j + 2..j + horizon + 1 are subsequent bars.
    for j in range(15,i-horizon):
        historical=feature_cache[j] if feature_cache is not None else features(rows,j,benchmark)
        if not historical:continue
        if (historical['momentum_atr']>=0)!=(current['momentum_atr']>=0):continue
        if (historical['momentum_change_atr']>=0)!=(current['momentum_change_atr']>=0):continue
        if field and (historical[field] is None or (historical[field]>= (1 if field=='relative_volume' else 0)) != (current[field]>= (1 if field=='relative_volume' else 0))):continue
        try:
            entry=float(rows[j+1]['close']); high=max(float(r['high']) for r in rows[j+2:j+horizon+2])
            excursion=max(0.,(high-entry)/historical['atr'])
            examples.append(excursion)
        except (KeyError,TypeError,ValueError):continue
    result['sample_count']=len(examples)
    if not examples:result['reason']='NO_MATURED_COMPARABLES';return result
    values=sorted(examples); mid=median(values)
    result.update(range_atr=[values[int((len(values)-1)*.25)],values[int((len(values)-1)*.75)]],
                  estimated_move_atr=mid)
    if mid<=0:result['reason']='NONPOSITIVE_PROJECTED_MOVE';return result
    result.update(status='PROJECTED',target_distance=mid*current['atr'])
    return result


def compare(config, manifest, charts, *, benchmark_name=None, decision_start=None, reference_sessions=None, peer_charts=None, source_items=None, base_result=None):
    """Replay four exit variants over the same signals and observed prices."""
    if config.target_r != 2 or config.exit_mode != 'HORIZON_OR_TARGET':
        raise ValueError('comparison requires fixed 2R control and horizon/target exit')
    base=base_result if base_result is not None else run_components(config,manifest,charts,decision_start=decision_start,reference_sessions=reference_sessions)
    if base_result is not None:
        original=dict(base['config']);requested=asdict(config)
        original.pop('horizon',None);requested.pop('horizon',None)
        if original!=requested or base.get('data_hash')!=manifest.sha256 or base.get('decision_start')!=decision_start:
            raise ValueError('cached signals must match input and all entry/stop settings')
    rows=charts[manifest.instrument]; index={r['timestamp'][:10]:i for i,r in enumerate(rows)}
    benchmark=charts.get('ETF_STX40') if benchmark_name else None
    reference_map={r['timestamp'][:10]:r.get('close') for r in benchmark} if benchmark else None
    feature_cache=[features(rows,i,reference_map) for i in range(len(rows))]
    peer_cases=prepare_peers(peer_charts or {},config.horizon)
    context_by_signal={item['id']:timed_context(source_items or [],manifest.instrument,
        (manifest.bars[index[item['session']]].available_at+timedelta(seconds=1)).isoformat(),
        signal_session=item['session']) for item in base['signals']}
    variants={}; details={}
    costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
    for variant in (*VARIANTS,'momentum_peers'):
        signals=[]; estimates={}
        for item in base['signals']:
            i=index[item['session']]
            original=signal_for(config,manifest.instrument,item['session'],manifest.bars[i].available_at+timedelta(seconds=1),item['stop'])
            estimate=({'variant':variant,'status':'FIXED_2R','sample_count':None} if variant=='fixed_2r'
                      else peer_projection(rows,i,config.horizon,peer_cases,feature_cache) if variant=='momentum_peers'
                      else projection(rows,i,config.horizon,variant,reference_map,feature_cache))
            distance=estimate.get('target_distance')
            signals.append(Signal(**asdict(original),target_distance=Decimal(str(distance)) if distance else None))
            estimates[item['id']]=estimate
        result=replay([manifest],signals,as_of=max(b.available_at for b in manifest.bars)+timedelta(days=8),
                      initial_cash=Decimal(1000000),costs=costs)
        trades=result['trades']; equity=[float(e['equity']) for e in result['equity']]
        peak=0.;mdd=0.
        for value in equity:
            peak=max(peak,value)
            if peak:mdd=min(mdd,value/peak-1)
        for trade in trades:
            estimate=estimates[trade['id']]; entry=float(trade['entry'])
            stop=next(x['stop'] for x in base['signals'] if x['id']==trade['id'])
            estimate['entry']=entry;estimate['stop']=stop
            estimate['target_price']=entry+(estimate.get('target_distance') or 2*(entry-stop))
        variants[variant]={'signals':len(signals),'trades':len(trades),'target_hits':sum(t['reason'] in ('TARGET','GAP_TARGET_LIMIT') for t in trades),
                           'net':round(sum(float(t['net_pnl']) for t in trades),2),'max_drawdown_pct':round(mdd*100,2),
                           'average_hold':sum(t['held'] for t in trades)/len(trades) if trades else None,
                           'projected_signals':sum(x['status']=='PROJECTED' for x in estimates.values()),
                           'decisions':result['decisions'],'closed_trades':trades,
                           'timed_context_subgroups':{label:{'trades':len(group),'net':round(sum(float(t['net_pnl']) for t in group),2)}
                               for label,group in (('known_recent', [t for t in trades if context_by_signal[t['id']]['known_recent']]),
                                                   ('no_known_recent', [t for t in trades if not context_by_signal[t['id']]['known_recent']]),
                                                   ('retrospective_recent', [t for t in trades if context_by_signal[t['id']]['retrospective_recent']]))}}
        details[variant]=estimates
    return {'schema':'momentum-target-comparison-v1','instrument':manifest.instrument,'family':config.family,
            'data_hash':manifest.sha256,'config':asdict(config),'benchmark':benchmark_name,
            'window':[rows[0]['timestamp'][:10],rows[-1]['timestamp'][:10]],'bars':rows,'variants':variants,'calculations':details,
            'timed_context':context_by_signal,'peer_instruments':sorted((peer_charts or {}).keys()),
            'limitations':['RETROSPECTIVE_RECONSTRUCTED_DATA','HYPOTHETICAL_COSTS','SAME_INSTRUMENT_COMPARABLES',
                           'OBSERVED_REFERENCE_SESSIONS_NOT_VERIFIED_EXCHANGE_CALENDAR','CORPORATE_ACTION_ADJUSTMENTS_NOT_VERIFIED',
                           'MFE_NOT_ACHIEVABLE_PROFIT','CURRENT_SECTOR_PROXY_MAY_BE_RETROSPECTIVE',
                           'PEER_SECTOR_MEMBERSHIP_CURRENT_NOT_HISTORICAL','SOURCE_CONTEXT_DESCRIPTIVE_NOT_CAUSAL'],
            'live_execution':False}
