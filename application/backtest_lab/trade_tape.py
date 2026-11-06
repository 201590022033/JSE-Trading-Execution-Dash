"""Append-only snapshots of observed trades; no participant or side inference."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path


def capture(instrument, rows, *, source, captured_at, root, source_sha256=None):
    when=datetime.fromisoformat(captured_at.replace('Z','+00:00'))
    if when.tzinfo is None: raise ValueError('capture time must include timezone')
    if not instrument or not source or not rows: raise ValueError('instrument, source and trades required')
    clean=[]
    for r in rows:
        event=datetime.fromisoformat(r['traded_at'])
        if event.tzinfo is None or event>when: raise ValueError('event time must include timezone and precede capture')
        qty=int(r['quantity']);cents=int(r['price_cents'])
        if qty<=0 or cents<=0: raise ValueError('positive integer quantity and price required')
        clean.append({'traded_at':event.isoformat(),'time_precision':r.get('time_precision','minute'),
                      'quantity':qty,'price_cents':cents,'reported_value_zar':r.get('reported_value_zar')})
    total=sum(r['quantity'] for r in clean); notional=sum(r['quantity']*r['price_cents'] for r in clean)
    minute={}
    for r in clean:
        key=r['traded_at'][:16];m=minute.setdefault(key,{'trades':0,'shares':0,'notional_cents':0})
        m['trades']+=1;m['shares']+=r['quantity'];m['notional_cents']+=r['quantity']*r['price_cents']
    payload={'schema':'trade-tape-snapshot-v1','instrument':instrument,'source':source,'source_sha256':source_sha256,'captured_at':when.isoformat(),
             'rows':clean,'summary':{'prints':len(clean),'shares':total,'notional_zar':str(Decimal(notional)/100),
             'vwap_cents':str(Decimal(notional)/total),'min_cents':min(r['price_cents'] for r in clean),
             'max_cents':max(r['price_cents'] for r in clean),'largest_print_shares':max(r['quantity'] for r in clean),
             'minutes':minute},'limitations':['TEN_PRINT_SNAPSHOT_NOT_COMPLETE_TAPE','MINUTE_TIMESTAMPS_NOT_SEQUENCE',
             'NO_TRADE_IDS','NO_PARTICIPANT_OR_AGGRESSOR_IDENTITIES','NO_HISTORICAL_BID_ASK'], 'live_execution':False}
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest();folder=Path(root);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(digest+'.json')
    if not path.exists():path.write_bytes(raw)
    return digest,payload
