"""Field-level, availability-first Zebra research windows (v2).

The retained capture clock is real; historical bar availability is reconstructed.
This module never changes the frozen v1 evaluator or fabricates OHLCV.
"""
from datetime import date, timedelta
from application.opportunities.session_freshness import next_session

VERSION='zebra-field-windows-v2'
FIELDS=('open','high','low','close','volume')
SECTOR_PROXY={'Financials':'ETF_STXFIN','Financial':'ETF_STXFIN','Banks':'ETF_STXFIN',
              'Mining':'ETF_STXRES','Resources':'ETF_STXRES','Energy':'ETF_STXRES',
              'Industrials':'ETF_STXIND','Industrial':'ETF_STXIND'}


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


def benchmark_for(item, instruments):
    preferred=SECTOR_PROXY.get(item.get('sector'))
    if preferred and instruments.get(preferred,{}).get('rows'):
        return {'instrument':preferred,'basis':'CURRENT_SECTOR_PROXY_NOT_HISTORICAL_MEMBERSHIP'}
    if instruments.get('ETF_STX40',{}).get('rows'):
        return {'instrument':'ETF_STX40','basis':'BROAD_MARKET_FALLBACK'}
    return {'instrument':None,'basis':'NO_BENCHMARK_STOCK_ONLY'}


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
        result[key]={'fields':counts,'windows':windows,'technical':technical,'benchmark':benchmark_for(item,instruments),
                     'rows':[{**r,'capabilities':capabilities(r)} for r in rows]}
    return {'version':VERSION,'gap_policy':'SPLIT_AT_KNOWN_JSE_GAP_OR_UNREVIEWED_WEEKDAY_GAP',
            'availability':data.get('availability'),'instruments':result,'live_execution':False}


def evaluate_mixed(strategy,instrument,index,charts):
    """Versioned research evaluation using v1 rules without its source veto.

    Caller supplies a complete contiguous OHLCV window. Original rows and v1
    remain untouched; source identity is still retained in the input.
    """
    from application.backtest_lab.strategies import evaluate
    rows=charts[instrument][:index+1]
    segments=valid_segments([{**r,'session':r['timestamp'][:10]} for r in rows],FIELDS)
    rows=segments[-1] if segments and segments[-1][-1]['session']==rows[-1]['timestamp'][:10] else []
    if len(rows)<51:return [],None
    if any(not capabilities(r)['ohlcv'] for r in rows): return [],None
    local=dict(charts)
    local[instrument]=[{**r,'_source':'ZEBRA_FIELD_BRANCH'} for r in rows]
    trace,stop=evaluate(strategy,instrument,len(rows)-1,local)
    return [x for x in trace if x['c']!='Source continuity'],stop
