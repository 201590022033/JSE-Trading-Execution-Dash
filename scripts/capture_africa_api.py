"""Capture bounded Africa API JSE history; never print or persist the API key."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.opportunities.africa_api_credentials import load_key
from application.opportunities.radar_price_capture import latest_close_history, usable_close
from application.opportunities.zebra_instruments import mappings

BASE='https://api.africa-api.com/v1/markets/tickers/JSE/'


def rows_for_unit(raw, unit, acquired_at):
    data=json.loads(raw); entries=data.get('data')
    if not isinstance(entries,list) or len(entries)>5000: raise ValueError('unexpected history response')
    acquired=datetime.fromisoformat(acquired_at.replace('Z','+00:00'))
    if acquired.tzinfo is None or unit not in ('ZAR','ZAR_CENTS'): raise ValueError('unit and acquisition required')
    rows=[]
    for item in entries:
        day=datetime.strptime(item['trade_date'],'%Y-%m-%d').date().isoformat()
        if not usable_close(day,acquired) or item.get('close_price') is None: continue
        row={'session':day,'source_code':item.get('source_code'),'provider_created_at':item.get('created_at')}
        invalid=[]
        for field in ('open','high','low','close'):
            value=item.get(field+'_price')
            if value is None: row[field]=None; continue
            try:
                number=Decimal(str(value))
                if not number.is_finite() or number<=0: raise ValueError('invalid price')
                row[field]=str(number/(100 if unit=='ZAR_CENTS' else 1))
            except (InvalidOperation,ValueError,TypeError):
                row[field]=None; invalid.append(field)
        volume=item.get('volume')
        if volume is not None and (type(volume) is not int or volume<0): volume=None; invalid.append('volume')
        if row['close'] is None: continue
        if invalid: row['invalid_fields']=invalid
        row['volume']=volume; rows.append(row)
    rows.sort(key=lambda r:r['session'])
    if not rows or any(a['session']==b['session'] for a,b in zip(rows,rows[1:])):
        raise ValueError('no unique completed observations')
    return rows


def probe(instrument, root=ROOT, *, key_reader=load_key, fetch=None, clock=None):
    import requests
    root=Path(root); folder=root/'runtime/local-swing-data'; registry=mappings(folder/'radar-public-prices')
    clock=clock or (lambda:datetime.now(timezone.utc)); started=clock()
    def finish(result):
        result={**result,'started_at':started.isoformat(),'finished_at':clock().isoformat()}
        directory=folder/'africa-api/attempts'; directory.mkdir(parents=True,exist_ok=True)
        path=directory/(instrument+'-'+uuid4().hex+'.json')
        with path.open('x',encoding='utf-8') as out:
            json.dump(result,out,sort_keys=True,allow_nan=False); out.write('\n')
        return result
    code=registry.get(instrument)
    if not code: raise ValueError('registered instrument required')
    secret=key_reader()
    if not secret: return finish({'instrument':instrument,'state':'KEY_NOT_CONFIGURED','requests':0})
    fetch=fetch or requests.get
    rawdir=folder/'africa-api/raw'; rawdir.mkdir(parents=True,exist_ok=True)
    receipts=[]; contents=[]
    for kind,url,params in [('identity',BASE+code,{}),('history',BASE+code+'/history',{'limit':1500})]:
        try:
            result=fetch(url,headers={'Authorization':'Bearer '+secret,'Accept':'application/json'},
                         params=params,timeout=20,allow_redirects=False)
        except requests.RequestException as exc:
            return finish({'instrument':instrument,'state':'NETWORK_FAILED','error_type':type(exc).__name__,'requests':len(receipts)+1})
        acquired=clock()
        if result.status_code != 200:
            return finish({'instrument':instrument,'state':'PROVIDER_REJECTED','http_status':result.status_code,'requests':len(receipts)+1})
        raw=result.content
        if not isinstance(raw,bytes) or len(raw)>3_000_000: return finish({'instrument':instrument,'state':'INVALID_RESPONSE','requests':len(receipts)+1})
        if secret.encode('utf-8') in raw:
            return finish({'instrument':instrument,'state':'UNSAFE_RESPONSE_NOT_RETAINED','requests':len(receipts)+1})
        digest=sha256(raw).hexdigest(); path=rawdir/(digest+'.json')
        if not path.exists(): path.write_bytes(raw)
        receipts.append({'kind':kind,'url':url,'params':params,'raw_sha256':digest,'acquired_at':acquired.isoformat()})
        contents.append(raw)
    identity=json.loads(contents[0]).get('data',{})
    if identity.get('exchange_code')!='JSE' or identity.get('symbol')!=code:
        return finish({'instrument':instrument,'state':'IDENTITY_MISMATCH','requests':2})
    acquired=receipts[-1]['acquired_at']; candidates={}; reference=None
    try:
        for unit in ('ZAR','ZAR_CENTS'): candidates[unit]=rows_for_unit(contents[1],unit,acquired)
        public=latest_close_history(folder/'radar-public-prices',instrument)
        reference={'provider':'YAHOO','capture_sha256':public['source_sha256'],'acquired_at':public['acquired_at']}
        peer={r['session']:Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) for r in public['rows']}
        checks={}
        for unit,rows in candidates.items():
            overlap=[r for r in rows if r['session'] in peer][-60:]
            matches=sum(Decimal(r['close']).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==peer[r['session']] for r in overlap)
            checks[unit]={'overlap':len(overlap),'matches':matches,'mismatches':len(overlap)-matches}
        eligible=[unit for unit,check in checks.items() if check['matches']>=20]
        chosen=eligible[0] if len(eligible)==1 else None
    except (OSError,ValueError,KeyError,TypeError,InvalidOperation):
        chosen=None; checks={}
    record={'schema':'africa-api-history-capture-v1','instrument':instrument,'symbol':code,'provider':'AFRICA_API',
            'exchange':'JSE','acquired_at':acquired,'raw_responses':receipts,'currency':'ZAR',
            'price_unit':chosen or 'UNVERIFIED','unit_cross_checks':checks,
            'unit_reference':reference,
            'basis':'RECONSTRUCTED_HISTORY_UPSTREAM_AND_ADJUSTMENTS_UNVERIFIED',
            'rows':candidates.get(chosen,[]) if chosen else [],'research_only':True,'live_execution':False}
    encoded=(json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    digest=sha256(encoded).hexdigest(); path=folder/'africa-api'/(instrument+'-'+digest+'.json')
    if not path.exists(): path.write_bytes(encoded)
    return finish({'instrument':instrument,'state':'CAPTURED_UNIT_CROSSCHECKED' if chosen else 'CAPTURED_UNIT_UNRESOLVED',
            'requests':2,'capture_sha256':digest,'acquired_at':acquired,'unit':chosen,
            'sessions':len(record['rows']),'unit_cross_checks':checks})


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('instrument')
    args=parser.parse_args()
    try: print(json.dumps(probe(args.instrument.upper()),sort_keys=True))
    except Exception as exc: print(json.dumps({'state':'PROBE_FAILED','error_type':type(exc).__name__})); raise SystemExit(1)
