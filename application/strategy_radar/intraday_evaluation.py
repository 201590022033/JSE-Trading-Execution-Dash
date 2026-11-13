"""Deterministic intraday shadow profiles built on M3 source-aware bars.

Research only. No execution, provider requests, model calls or strategy promotion.
Five entry components are evaluated on four contiguous, completed same-session
bars. Every value remains attributable to the selected M3 field evidence.
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from statistics import mean
from .intraday_store import merge_bars, normalize_bar, _time, _session, SAST, _is_viewpoint_source

PROFILES = {
    'intraday_5m_research_v1': {'strategy_version':'1.0.0', 'timeframe_minutes':5},
    'intraday_30m_research_v1': {'strategy_version':'1.0.0', 'timeframe_minutes':30},
}


def _decimal(value):
    try:
        x = Decimal(str(value))
        return x if x.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _trace(rule_id, mandatory, passed, value, threshold, provenance, reason):
    return {'id':rule_id, 'mandatory':mandatory,
            'state':'UNKNOWN' if passed is None else 'PASS' if passed else 'FAIL',
            'value':str(value) if value is not None else None,
            'threshold':str(threshold) if threshold is not None else None,
            'provenance':provenance, 'reason':reason}


def _usable_bars(records, instrument, interval, now):
    eligible=[]
    for record in records:
        if not isinstance(record,dict) or record.get('instrument') != instrument or record.get('interval_minutes') != interval:
            continue
        # Retain the exact knowledge available at this evaluation time.
        try:
            if _time(record['received_at']) <= now:
                normalize_bar(record)
                eligible.append(record)
        except (ValueError, KeyError, TypeError):
            continue
    return merge_bars(eligible)['bars']


def _field(bar, name, historical_replay=False):
    field=bar['fields'][name]
    selected=field['selected']
    if selected is None:
        return None, []
    evidence=[{'field':name, 'bar_start':bar['bar_start'], 'bar_end':bar['bar_end'],
               'source':selected['source'], 'source_timestamp':selected['source_timestamp'],
               'received_at':selected['received_at'], 'availability':selected['availability'],
               'selection_policy':selected.get('selection_policy'),
               'source_timestamp_basis':selected.get('source_timestamp_basis'),
               'normalization_basis':selected.get('normalization_basis'),
               'derived_inputs_sha256':selected.get('derived_inputs_sha256'),
               'derived_inputs':selected.get('derived_inputs'),
               'field_state':field['state'], 'alternatives':field['alternatives'],
               'revisions':field['revisions']}]
    # A selected source is not enough to confirm a condition if that exact field
    # is disputed, provisional, stale or has unqualified historical/unknown data.
    preferred_viewpoint_conflict = (
        field['state'] == 'CONFLICT'
        and selected.get('selection_policy') == 'VIEWPOINT_PREFERRED'
    )
    fallback_from_unusable_viewpoint = (
        field['state'] == 'CONFLICT'
        and selected.get('selection_policy') == 'FALLBACK_SOURCE'
        and bool(field['alternatives'])
        and any(_is_viewpoint_source(candidate.get('source')) for candidate in field['alternatives'])
        and all(candidate.get('provisional')
                or candidate.get('availability') in ('STALE', 'UNKNOWN', 'HISTORICAL')
                for candidate in field['alternatives'])
    )
    if (selected.get('provisional') or
            (field['state'] != 'AVAILABLE' and not (
                preferred_viewpoint_conflict or fallback_from_unusable_viewpoint
            )) or
            selected['availability'] not in (('LIVE','DELAYED','MANUAL','HISTORICAL') if historical_replay else ('LIVE','DELAYED','MANUAL'))):
        return None, evidence
    value=_decimal(selected['value'])
    if value is None:
        return None, evidence
    return value, evidence


def _series(bars, field, historical_replay=False):
    values=[]; provenance=[]
    for bar in bars:
        value, source = _field(bar,field,historical_replay)
        provenance.extend(source)
        if value is None:
            return None, provenance
        values.append(value)
    return values,provenance


def _daily(gate, now, historical_replay=False):
    """A completed close requires a reviewed session, close and receipt clocks."""
    if gate is None:
        return True, [], None
    try:
        if not isinstance(gate,dict) or gate.get('completed') is not True or not gate.get('source') or gate.get('availability') not in (('LIVE','DELAYED','MANUAL','HISTORICAL') if historical_replay else ('LIVE','DELAYED','MANUAL')) or gate.get('field_state','AVAILABLE') != 'AVAILABLE':
            raise ValueError('daily close not confirmed')
        source, received, completed = (_time(gate[k]) for k in ('source_time','received_at','completed_at'))
        from datetime import date
        session=date.fromisoformat(gate['session'])
        close=datetime.combine(session,datetime.min.time(),tzinfo=SAST).replace(hour=17)
        if _session(session) is not True or source < close or completed < close or source > received or received > now or completed > received:
            raise ValueError('daily close unavailable at evaluation')
        value,threshold=_decimal(gate.get('value')),_decimal(gate.get('threshold'))
        if value is None or threshold is None or value<=0 or threshold<=0:
            raise ValueError('daily close or threshold missing')
        evidence=[{'field':'daily_close','session':session.isoformat(),'source':gate['source'],
                   'source_timestamp':source.isoformat(),'completed_at':completed.isoformat(),
                   'received_at':received.isoformat(),'availability':gate['availability'],'value':str(value),'threshold':str(threshold)}]
        return value > threshold,evidence,None
    except (KeyError,TypeError,ValueError):
        evidence = [{k: str(gate[k]) if gate.get(k) is not None else None
                     for k in ('source','session','source_time','received_at','completed_at',
                               'availability','field_state','value','threshold')} ] if isinstance(gate,dict) else []
        if evidence:
            evidence[0]['field']='daily_close'
            evidence[0]['usable']=False
        return None, evidence, 'Daily close not confirmed or not yet available'


def evaluate_intraday(profile_id, instrument, raw_records, as_of, *, benchmark_records=(), daily_gate=None, developing_fraction=0.8, historical_replay=False):
    """Evaluate only records whose actual receipt is no later than `as_of`.

    `daily_gate` may specify a required close above threshold: value, threshold,
    source, session (YYYY-MM-DD), source_time, completed_at, received_at and
    completed=True. Unknown and provisional never count as passing.
    """
    if type(historical_replay) is not bool:
        raise ValueError('historical_replay must be boolean')
    if profile_id not in PROFILES:
        raise ValueError('unknown intraday profile')
    if not isinstance(instrument,str) or not instrument:
        raise ValueError('instrument required')
    now=_time(as_of)
    fraction=_decimal(developing_fraction)
    if fraction is None or not Decimal(0)<fraction<=Decimal(1):
        raise ValueError('developing fraction must be in (0,1]')
    profile=PROFILES[profile_id]; interval=profile['timeframe_minutes']
    local_now=now.astimezone(SAST)
    session_open=(_session(local_now.date()) is True and local_now.replace(hour=9, minute=0, second=0, microsecond=0)<=local_now<local_now.replace(hour=17, minute=0, second=0, microsecond=0))
    bars=_usable_bars(raw_records,instrument,interval,now)
    bars=[b for b in bars if not b['provisional'] and _time(b['bar_end'])<=now]
    bars.sort(key=lambda b:b['bar_start'])
    selected=bars[-4:]
    reason=None
    if not session_open:
        reason='JSE session closed or calendar unverified'
    elif not selected:
        reason='No verified interval bars available'
    elif now-_time(selected[-1]['bar_end']) > timedelta(minutes=interval*2):
        reason='Latest completed bar is stale at evaluation time'
    elif len(selected)<4:
        reason='Four completed contiguous bars are required'
    else:
        for index,bar in enumerate(selected):
            if (_time(bar['bar_start']).astimezone(SAST).date()!=_time(selected[-1]['bar_start']).astimezone(SAST).date() or
                (index and _time(bar['bar_start'])!=_time(selected[index-1]['bar_end']))):
                reason='Four completed contiguous bars in one verified session are required'
                break
    rules=[]
    if reason:
        for name,mandatory in [('entry',True),('trend',True),('momentum',True),('volume',False),('benchmark',False)]:
            rules.append(_trace(name,mandatory,None,None,None,[],reason))
    else:
        close,close_p=_series(selected,'close',historical_replay)
        current,current_p=_field(selected[-1],'close',historical_replay)
        prev,prev_p=_field(selected[-2],'close',historical_replay)
        high,high_p=_field(selected[-2],'high',historical_replay)
        intraday_entry = None if current is None or high is None else current>high
        daily_ok,daily_p,daily_reason=_daily(daily_gate,now,historical_replay)
        # A failed mandatory subcondition is definitive; an unknown is not pass.
        entry = False if intraday_entry is False or daily_ok is False else None if intraday_entry is None or daily_ok is None else True
        rules.append(_trace('entry',True,entry,current,high,current_p+high_p+daily_p,
                            daily_reason or 'Latest completed close above prior bar high; optional daily close gate'))
        avg=mean(close[-4:-1]) if close else None
        rules.append(_trace('trend',True,None if close is None else current>avg,current,avg,close_p,'Close above mean of prior three closes'))
        rules.append(_trace('momentum',True,None if current is None or prev is None else current>prev,current,prev,current_p+prev_p,'Close above previous close'))
        volume,volume_p=_series(selected,'volume',historical_replay)
        baseline=mean(volume[:-1])*Decimal('1.2') if volume else None
        rules.append(_trace('volume',False,None if volume is None or baseline<=0 else volume[-1]>=baseline,volume[-1] if volume else None,baseline,volume_p,'Volume at least 1.2 times prior three-bar mean'))
        # Benchmark requires exact matching intervals; no forward fill or assumed price.
        benchmark = _usable_bars(benchmark_records, benchmark_records[0].get('instrument') if benchmark_records else '', interval, now)
        by_interval={(x['bar_start'],x['bar_end']):x for x in benchmark if not x['provisional'] and _time(x['bar_end'])<=now}
        paired=[by_interval.get((b['bar_start'],b['bar_end'])) for b in selected]
        benchmark_first,benchmark_first_p=_field(paired[0],'close',historical_replay) if all(paired) else (None,[])
        benchmark_last,benchmark_last_p=_field(paired[-1],'close',historical_replay) if all(paired) else (None,[])
        first,first_p=_field(selected[0],'close',historical_replay)
        stock_return=(current/first-1) if current is not None and first is not None and first>0 else None
        bench_return=(benchmark_last/benchmark_first-1) if benchmark_last is not None and benchmark_first is not None and benchmark_first>0 else None
        benchmark_p=benchmark_first_p+benchmark_last_p
        rules.append(_trace('benchmark',False,None if stock_return is None or bench_return is None else stock_return>bench_return,
                            stock_return,bench_return,first_p+current_p+benchmark_p,'Three-interval return above aligned benchmark return'))
    passed=sum(r['state']=='PASS' for r in rules); unknown=sum(r['state']=='UNKNOWN' for r in rules)
    required=int((Decimal(len(rules))*fraction).to_integral_value(rounding=ROUND_CEILING))
    mandatory=[r for r in rules if r['mandatory']]
    if all(r['state']=='PASS' for r in mandatory): state='ENTRY_MET'
    elif passed>=required: state='DEVELOPING'
    elif unknown==len(rules): state='UNKNOWN'
    else: state='WATCHING'
    ref_close = None if reason else _field(selected[-1],'close',historical_replay)[0]
    stop = ref_close * Decimal('0.98') if ref_close is not None else None
    target = ref_close + (ref_close-stop)*2 if ref_close is not None else None
    return {'instrument':instrument,'strategy_id':profile_id,'strategy_version':profile['strategy_version'],
            'timeframe_minutes':interval,'evaluated_at':now.isoformat(),'state':state,'rules':rules,
            'passed':passed,'applicable':len(rules),'unknown':unknown,'required_for_developing':required,
            'component_plan':{'stop':'2% below completed close','target':'2R','trailing':'NONE','exit':'3 bars or target/stop',
                              'reference_close':str(ref_close) if ref_close is not None else None,
                              'stop_price':str(stop) if stop is not None else None,
                              'target_price':str(target) if target is not None else None,
                              'mode':'RESEARCH_ASSUMPTION','execution':False},
            'session_state':'OPEN' if session_open else 'CLOSED_OR_UNVERIFIED',
            'evaluation_mode':'HISTORICAL_SHADOW_NOT_CURRENT' if historical_replay else 'SHADOW', 'live_signal':False, 'research_only':True}
