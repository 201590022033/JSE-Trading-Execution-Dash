"""Field-level, availability-first Zebra research windows (v2).

The retained capture clock is real; historical bar availability is reconstructed.
This module never changes the frozen v1 evaluator or fabricates OHLCV.
"""
from datetime import date, timedelta
from math import isfinite
from application.opportunities.session_freshness import next_session

VERSION='zebra-field-windows-v2'
FIELDS=('open','high','low','close','volume')
SECTOR_PROXY={'Financials':'ETF_STXFIN','Financial':'ETF_STXFIN','Financial Services':'ETF_STXFIN','Banks':'ETF_STXFIN',
              'Mining':'ETF_STXRES','Resources':'ETF_STXRES','Energy':'ETF_STXRES',
              'Industrials':'ETF_STXIND','Industrial':'ETF_STXIND'}
# Existing studies must be reproducible with their original benchmark inputs.
LEGACY_STUDY_INSTRUMENTS = frozenset({'SASOL', 'BTI', 'FSR', 'ABSPJ', 'NEWGOLD'})
BROAD_BENCHMARK = 'ETF_STX40'


def reference_segments(rows, reference_rows, required=('open','high','low','close')):
    """Historical research windows using observed reference sessions.

    A reference session missing from the stock ends the window. Gaps absent
    from both sources remain calendar-uncertain and are not manufactured.
    This is an observed-session research calendar, not a verified exchange one.
    """
    if not set(required).issubset(FIELDS):raise ValueError('unknown field')
    reference=sorted({r['session'] for r in reference_rows if r.get('close') is not None})
    from bisect import bisect_right, bisect_left
    result=[];current=[];previous=None
    for row in sorted(rows,key=lambda r:r['session']):
        day=row['session'];date.fromisoformat(day)
        if previous and bisect_right(reference,previous)<bisect_left(reference,day):
            if current:result.append(current);current=[]
        usable=all(row.get(f) is not None for f in required)
        if set(required)==set(FIELDS):usable=usable and capabilities(row)['ohlcv']
        elif set(required)=={'open','high','low','close'}:
            usable=usable and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']
        if usable:current.append(row)
        elif current:result.append(current);current=[]
        previous=day
    if current:result.append(current)
    return result


def valid_segments(rows, required=('close',)):
    """Return all usable windows, splitting at missing fields or known JSE sessions."""
    if not set(required).issubset(FIELDS): raise ValueError('unknown field')
    segments=[]; current=[]; previous=None
    for row in sorted(rows,key=lambda r:r['session']):
        day=row['session']; date.fromisoformat(day)
        expected=next_session(previous) if previous else None
        if previous and expected is None:
            # On unreviewed years, only uninterrupted weekdays/weekends are
            # joined. A possible holiday gap splits rather than being guessed.
            candidate=date.fromisoformat(previous)+timedelta(days=1)
            while candidate.weekday()>=5: candidate+=timedelta(days=1)
            expected=candidate.isoformat()
        if current and day != expected:
            segments.append(current); current=[]
        usable=all(row.get(f) is not None for f in required)
        if set(required)==set(FIELDS): usable=usable and capabilities(row)['ohlcv']
        elif set(required)=={'high','low','close'}: usable=usable and capabilities(row)['hlc']
        if usable: current.append(row)
        elif current: segments.append(current); current=[]
        previous=day
    if current: segments.append(current)
    return segments


def capabilities(row):
    missing=[x for x in FIELDS if row.get(x) is None]
    hlc=all(row.get(f) is not None for f in ('high','low','close'))
    hlc=hlc and row['low'] <= row['close'] <= row['high']
    ohlcv=not missing and hlc and row['low'] <= row['open'] <= row['high']
    return {'missing':missing,'close_only':row.get('close') is not None,
            'hlc':bool(hlc),'ohlcv':bool(ohlcv)}


def _sector_assignment(item, as_of):
    """Select a dated, source-attributed mapping or a labelled fallback.

    Sector-history entries need an effective start and evidence; undated current
    categories remain a retrospective research proxy, never historical fact.
    """
    if as_of is not None: date.fromisoformat(as_of)
    matches=[]
    if as_of:
        for entry in item.get('sector_history',[]):
            try:
                start=entry['effective_from']; end=entry.get('effective_to')
                date.fromisoformat(start)
                if end: date.fromisoformat(end)
                if entry.get('evidence') and start<=as_of and (not end or as_of<=end): matches.append(entry)
            except (TypeError,ValueError,KeyError): continue
    sector=matches[0]['sector'] if len(matches)==1 else item.get('sector')
    basis='DATED_SECTOR_MAPPING' if len(matches)==1 else 'CURRENT_SECTOR_PROXY_NOT_HISTORICAL_MEMBERSHIP'
    if len(matches)>1: basis='OVERLAPPING_DATED_MAPPINGS_CURRENT_PROXY'
    result={'as_of':as_of,'sector':sector,'sector_basis':basis}
    if len(matches)==1:
        result['mapping']={k:matches[0].get(k) for k in ('effective_from','effective_to','evidence','acquired_at','mapping_archive_sha256')}
        acquired=matches[0].get('acquired_at')
        result['mapping_knowledge']=('ACQUIRED_AFTER_SESSION_RETROSPECTIVE' if acquired and acquired[:10]>as_of else
                                     'ACQUIRED_ON_SESSION_TIME_NOT_CHECKED' if acquired and acquired[:10]==as_of else
                                     'ACQUIRED_BEFORE_SESSION' if acquired else 'ACQUISITION_UNKNOWN')
    else:
        result['mapping_knowledge']='CURRENT_CLASSIFICATION_RETROSPECTIVE'
    return result


def benchmark_for(item, instruments, as_of=None):
    """Preserve the original ETF selection for existing research studies."""
    result = _sector_assignment(item, as_of)
    preferred = SECTOR_PROXY.get(result['sector'])

    def available(key):
        rows = instruments.get(key, {}).get('rows', [])
        return bool(rows) if not as_of else any(r.get('session') == as_of and r.get('close') is not None for r in rows)

    if preferred and available(preferred):
        return {**result,'instrument':preferred,'basis':result['sector_basis']}
    if available(BROAD_BENCHMARK):
        return {**result,'instrument':BROAD_BENCHMARK,'basis':'BROAD_MARKET_FALLBACK',
                'preferred_sector_proxy':preferred}
    return {**result,'instrument':None,'basis':'NO_BENCHMARK_STOCK_ONLY',
            'preferred_sector_proxy':preferred}


def constructed_proxy_allowed(sector):
    """Telecommunications currently uses the broad market ETF."""
    return sector != 'Telecommunications'


def broad_benchmark_label(sector):
    label = f'Broad ETF {BROAD_BENCHMARK}'
    return label if constructed_proxy_allowed(sector) else f'{label} · Telecommunications benchmark'


def benchmark_input_keys(root, instruments):
    """Load retained research peers plus the established ETF references."""
    from pathlib import Path
    from application.opportunities.research_classification import classifications, sector_members
    from application.opportunities.zebra_instruments import mappings

    selected = set(instruments)
    registered = mappings(Path(root) / 'runtime/local-swing-data/radar-public-prices')
    labels = classifications(set(registered) | selected)['instruments']
    peers = {peer for key in selected - LEGACY_STUDY_INSTRUMENTS
             if constructed_proxy_allowed(labels[key]['sector'])
             for peer in sector_members(labels, labels[key]['sector'])}
    return selected | peers | set(SECTOR_PROXY.values()) | {BROAD_BENCHMARK}


def constructed_sector_proxy(sessions, observations):
    """Compound equal-weighted returns over aligned, selected member closes.

    Each observation is keyed by its actual session. A gap drops a member's
    return on both adjacent pairs rather than assigning a multi-day return to
    one session. An all-member gap breaks the level chain.
    """
    rows = {}
    level = None
    previous = None
    segment = None
    for day in sessions:
        members = {}
        returns = []
        for name, history in sorted(observations.items()):
            current = history.get(day)
            prior = history.get(previous)
            if current is None or previous is not None and prior is None:
                continue
            members[name] = [prior, current] if previous is not None else [current]
            if prior is not None:
                returns.append(current['value'] / prior['value'] - 1)
        daily_return = sum(returns) / len(returns) if returns else None
        if not members:
            level = None
            segment = None
        elif level is None:
            segment = day
            level = 100.0
        elif daily_return is not None:
            level *= 1 + daily_return
        provisional = any(o.get('provisional') or o.get('state') == 'CONFLICT_NO_CONSENSUS'
                          for pair in members.values() for o in pair)
        quality = ('NO_DATA' if not members else 'PARTIAL' if len(members) < len(observations) or provisional
                   else 'SINGLE_SOURCE' if len(members) == 1 else 'CONFIRMED')
        rows[day] = {'session': day, 'close': level, 'segment': segment, 'daily_return': daily_return,
                     'members': sorted(members), 'observations': members, 'data_quality': quality,
                     'provisional': provisional}
        previous = day
    return rows


def constructed_label(sector, members, subject):
    count = len(members)
    noun = 'member' if count == 1 else 'members'
    thin = ' · thin' if count < 3 else ''
    return f'{sector} constructed proxy · {count} {noun} ({", ".join(members)}){thin} · excludes {subject}'


def _selected_closes(rows):
    selected = {}
    for row in rows:
        value = row.get('close')
        if isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(value) and value > 0:
            detail = row.get('fields', {}).get('close', {})
            selected[row['session']] = {**{k: detail[k] for k in
                                        ('source', 'acquired_at', 'source_sha256', 'field_source_sha256', 'state')
                                        if k in detail}, 'value': value}
    return selected


def research_benchmarks(instrument, instruments, sessions, *, lookback=1):
    """Resolve a trajectory of labelled benchmark choices over a local snapshot.

    Input fields come from Zebra's capture-cutoff selection. No future-session
    closes are used, and current sector membership remains retrospective.
    Return the assignments and full underlying series separately so a replay
    can use a coherent benchmark for the full lookback at every decision.
    """
    from application.opportunities.research_classification import sector_members

    item = instruments[instrument]
    assignments = {day: _sector_assignment(item, day) for day in sessions}
    labels = {key: record for key, record in instruments.items()
              if record.get('asset_class') in (None, 'cash_equity')}
    sectors = sorted({a['sector'] for a in assignments.values() if a['sector']})
    peers_by_sector = {sector: [member for member in sector_members(labels, sector) if member != instrument]
                       for sector in sectors}
    etfs = {BROAD_BENCHMARK, *SECTOR_PROXY.values()}
    relevant = etfs | {peer for peers in peers_by_sector.values() for peer in peers}
    closes = {key: _selected_closes(instruments.get(key, {}).get('rows', [])) for key in relevant}
    series = {key: {day: {'session': day, 'close': value['value']}
                    for day, value in closes.get(key, {}).items()} for key in etfs}
    proxy_keys = {}
    eligible_members = {}
    for sector, peers in peers_by_sector.items():
        if not constructed_proxy_allowed(sector) or not peers:
            continue
        proxy = f'CONSTRUCTED_{sector.upper().replace(" ", "_")}_EX_{instrument}'
        series[proxy] = constructed_sector_proxy(sessions, {peer: closes[peer] for peer in peers})
        proxy_keys[sector] = proxy
        eligible_members[proxy] = peers

    def aligned(key, day, start):
        rows = series.get(key, {})
        first, last = rows.get(start), rows.get(day)
        return bool(first and last and first['close'] is not None and last['close'] is not None
                    and first.get('segment') == last.get('segment'))

    result = {}
    for i, day in enumerate(sessions):
        assignment = assignments[day]
        sector = assignment['sector']
        preferred = SECTOR_PROXY.get(sector)
        proxy = proxy_keys.get(sector)
        start = sessions[max(0, i - lookback)]
        if aligned(preferred, day, start):
            result[day] = {**assignment, 'instrument': preferred, 'basis': assignment['sector_basis'],
                           'label': f'Sector ETF {preferred}'}
        elif aligned(proxy, day, start):
            row = series[proxy][day]
            result[day] = {**assignment, 'instrument': proxy, 'basis': 'CONSTRUCTED_SECTOR_PROXY',
                           'label': constructed_label(sector, row['members'], instrument),
                           'members': row['members'], 'member_count': len(row['members']),
                           'eligible_members': eligible_members[proxy],
                           'data_quality': row['data_quality'], 'leave_one_out': instrument,
                           'thin': len(row['members']) < 3, 'membership_basis': 'CURRENT_RESEARCH_GROUP'}
        elif aligned(BROAD_BENCHMARK, day, start):
            result[day] = {**assignment, 'instrument': BROAD_BENCHMARK, 'basis': 'BROAD_MARKET_FALLBACK',
                           'preferred_sector_proxy': preferred, 'label': broad_benchmark_label(sector)}
        else:
            result[day] = {**assignment, 'instrument': None, 'basis': 'NO_BENCHMARK_STOCK_ONLY',
                           'preferred_sector_proxy': preferred, 'label': 'No benchmark data', 'data_quality': 'NO_DATA'}
    return result, series


def describe(data, keys=None):
    instruments=data['instruments']; result={}
    for key,item in sorted(instruments.items()):
        if keys is not None and key not in keys: continue
        rows=item.get('rows',[])
        counts={f:sum(row.get(f) is not None for row in rows) for f in FIELDS}
        windows={name:[{'start':s[0]['session'],'end':s[-1]['session'],'observations':len(s)}
                       for s in valid_segments(rows,required)]
                 for name,required in [('close',('close',)),('hlc',('high','low','close')),
                                       ('ohlcv',FIELDS)]}
        close_segments=valid_segments(rows,('close',))
        last=close_segments[-1] if close_segments else []
        current=last[-1] if last else None
        # Do not use a prior segment when the latest row has no close.
        if current and rows and current['session'] != rows[-1]['session']: last=[]
        technical={'last_session':last[-1]['session'] if last else None,
                   'close':last[-1]['close'] if last else None,
                   'sma20':sum(r['close'] for r in last[-20:])/20 if len(last)>=20 else None,
                   'return20':last[-1]['close']/last[-21]['close']-1 if len(last)>=21 else None,
                   'consecutive_observations':len(last)}
        benchmark = benchmark_for(item, instruments, last[-1]['session'] if last else None)
        if last and key not in LEGACY_STUDY_INSTRUMENTS:
            sessions = [row['session'] for row in last]
            benchmarks, _ = research_benchmarks(key, instruments, sessions)
            benchmark = benchmarks[sessions[-1]]
        result[key]={'fields':counts,'windows':windows,'technical':technical,
                     'benchmark':benchmark,
                     'rows':[{**r,'capabilities':capabilities(r)} for r in rows]}
    return {'version':VERSION,'gap_policy':'SPLIT_AT_KNOWN_JSE_GAP_OR_UNREVIEWED_WEEKDAY_GAP',
            'availability':data.get('availability'),'instruments':result,'live_execution':False}


def evaluate_mixed(strategy,instrument,index,charts,*,reference_sessions=None):
    """Versioned research evaluation using v1 rules without its source veto.

    Caller supplies a complete contiguous OHLCV window. Original rows and v1
    remain untouched; source identity is still retained in the input.
    """
    from application.backtest_lab.strategies import evaluate
    rows=charts[instrument][:index+1]
    observed=[{**r,'session':r['timestamp'][:10]} for r in rows]
    segments=valid_segments(observed,FIELDS) if reference_sessions is None else reference_segments(observed,reference_sessions,FIELDS)
    rows=segments[-1] if segments and segments[-1][-1]['session']==rows[-1]['timestamp'][:10] else []
    if len(rows)<51:return [],None
    if any(not capabilities(r)['ohlcv'] for r in rows): return [],None
    local=dict(charts)
    local[instrument]=[{**r,'_source':'ZEBRA_FIELD_BRANCH'} for r in rows]
    trace,stop=evaluate(strategy,instrument,len(rows)-1,local)
    return [x for x in trace if x['c']!='Source continuity'],stop
