"""Price-only USD/ZAR component comparison; no synthetic volume or portfolio."""
from hashlib import sha256
import json
from math import isfinite
from datetime import date
from pathlib import Path


def build(raw, source_hash):
    if sha256(raw).hexdigest()!=source_hash: raise ValueError('source hash mismatch')
    data=json.loads(raw)
    if data.get('symbol')!='ZAR=X' or data.get('product')!='USD_ZAR_SPOT_REFERENCE' or data.get('expected_units')!='ZAR_PER_USD':
        raise ValueError('USD/ZAR spot reference identity required')
    rows=[]
    for item in data['rows']:
        if item.get('current_session_not_completed'): continue
        session=item.get('session')
        try:
            if date.fromisoformat(session).isoformat()!=session: raise ValueError('session')
        except (ValueError,TypeError): raise ValueError('invalid session identity')
        values={}
        for key in ('close','high','low'):
            try:
                v=float(item[key]);values[key]=v if isfinite(v) and v>0 else None
            except (ValueError,TypeError,KeyError):values[key]=None
        if (values['close'] is not None and values['high'] is not None and values['high']<values['close']): values['high']=None
        if (values['close'] is not None and values['low'] is not None and values['low']>values['close']): values['low']=None
        rows.append({'session':session,**values})
    if len(rows)<100 or any(a['session']>=b['session'] for a,b in zip(rows,rows[1:])):
        raise ValueError('ordered observed history required')
    n=len(rows); a=n*60//100; b=n*80//100; purge=6
    windows={'train':(0,a-1),'validation':(a+purge,b-1)}
    studies=[]
    for name,lookback in (('control_20',20),('candidate_10',10)):
        for horizon in (3,4,5):
            results={}
            for stage,(start,end) in windows.items():
                checked=0; missing=0; signals=[]
                for i in range(max(start,lookback),end+1):
                    # The entry is the next observed close; the entire outcome
                    # must mature within the same training/validation window.
                    if i+1+horizon>end: continue
                    prior=[x['high'] for x in rows[i-lookback:i]]
                    if any(x is None for x in prior) or any(rows[j]['close'] is None for j in (i,i+1,i+1+horizon)):
                        missing+=1; continue
                    checked+=1; level=max(prior); value=rows[i]['close']
                    if value>level:
                        entry=rows[i+1];exit=rows[i+1+horizon]
                        signals.append({'signal_session':rows[i]['session'],'level':level,'signal_close':value,
                            'entry_session':entry['session'],'exit_session':exit['session'],
                            'gross_return_pct':100*(exit['close']/entry['close']-1)})
                results[stage]={'checked':checked,'unavailable_windows':missing,'signals':signals,'signal_count':len(signals),
                    'mean_gross_return_pct':sum(x['gross_return_pct'] for x in signals)/len(signals) if signals else None}
            studies.append({'id':name,'entry_lookback':lookback,'horizon_observed_sessions':horizon,'results':results})
    return {'schema':'fx-component-study-v1','instrument':'USDZAR','source_sha256':source_hash,
        'source_acquired_at':data['acquired_at'],'source_symbol':data['symbol'],'units':'ZAR_PER_USD',
        'data_window':[rows[0]['session'],rows[-1]['session']],
        'windows':{k:[rows[start]['session'],rows[end]['session']] for k,(start,end) in windows.items()},
        'holdout_start':rows[b+purge]['session'],'holdout_results':'NOT_ACCESSED',
        'trials':studies,'model_calls':0,'research_only':True,'live_execution':False,
        'limitations':['HISTORICAL_AVAILABILITY_RECONSTRUCTED','OBSERVED_SESSIONS_NOT_VERIFIED_FX_CALENDAR',
            'GROSS_PRICE_RETURNS_NO_COSTS','NO_ACTUAL_BROKER_VEHICLE','NO_POSITION_OR_VOLUME_ASSUMPTIONS',
            'SIX_PREDECLARED_COMPARISONS_NOT_VALIDATED']}


def freeze(raw_path, output):
    raw_path=Path(raw_path);raw=raw_path.read_bytes();digest=sha256(raw).hexdigest()
    if not raw_path.stem.endswith(digest): raise ValueError('source filename does not match bytes')
    result=build(raw,digest)
    encoded=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    report_hash=sha256(encoded).hexdigest();folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(report_hash+'.json')
    if target.exists() and target.read_bytes()!=encoded:raise ValueError('report collision')
    if not target.exists():
        with target.open('xb') as handle:handle.write(encoded)
    return report_hash,result
