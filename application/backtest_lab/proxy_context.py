"""Descriptive, provider-labelled cross-asset overlays on retained trades."""
from datetime import date
from math import isfinite

def prior_return(rows,session,lookback=5):
    """Only earlier dated completed rows, never assume a same-day close time."""
    date.fromisoformat(session)
    usable=[]
    for r in rows:
        try:
            day=r['session'];date.fromisoformat(day);close=float(r['close'])
            if day<session and not r.get('current_session_not_completed') and isfinite(close) and close>0:
                usable.append((day,close))
        except (KeyError,TypeError,ValueError,OverflowError):continue
    usable.sort()
    if len(usable)<lookback+1:return None
    window=usable[-lookback-1:]
    if len({x[0] for x in window})!=len(window):return None
    return {'start_session':window[0][0],'end_session':window[-1][0],
            'return':window[-1][1]/window[0][1]-1}

def compare(artifact,proxies):
    """Compare existing trade outcomes; exclusion does not resimulate the book."""
    control=artifact.get('control') or {}; signals={s['id']:s for s in control.get('signals',[])}
    cases=[]
    for trade in control.get('trades',[]):
        signal=signals.get(trade['id'])
        if not signal:continue
        context={name:prior_return(source.get('rows',[]),signal['session']) for name,source in proxies.items()}
        cases.append({'instrument':trade['instrument'],'signal_session':signal['session'],
          'entry_session':trade['entry_session'],'exit_session':trade['exit_session'],
          'net_pnl':float(trade['net_pnl']),'context':context})
    comparisons={}
    for name in proxies:
        matched=[x for x in cases if x['context'][name] is not None]
        selected=[x for x in matched if x['context'][name]['return']>0]
        def summary(rows):return {'trades':len(rows),'net_pnl':round(sum(x['net_pnl'] for x in rows),2)}
        comparisons[name]={'matched_price_only':summary(matched),'positive_proxy_filter':summary(selected),
                           'coverage':len(matched),'unmatched':len(cases)-len(matched)}
    return {'cases':cases,'comparisons':comparisons,'model_context_eligible':False,
        'basis':'RETROSPECTIVE_POSTHOC_TRADE_SUBSET_NOT_PORTFOLIO_REPLAY',
        'limitations':['HISTORICAL_RECEIPTS_NOT_ARCHIVED','SESSION_CLOSE_TIME_NOT_VERIFIED',
                       'NO_CAUSAL_CLAIM','FILTER_DOES_NOT_RESIMULATE_CASH'], 'live_execution':False}
