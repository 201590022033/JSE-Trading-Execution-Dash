"""Bounded EODHD research capture, using the provider's current UTC quota."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.africa_api_credentials import load_key
from application.opportunities.zebra_instruments import mappings
from scripts.capture_eodhd_history import probe
from scripts.reconcile_zebra_prices import build


def remaining_quota(usage, today, reserve=1):
    limit = int(usage['dailyRateLimit'])
    spent = int(usage['apiRequests']) if str(usage['apiRequestsDate'])[:10] == today else 0
    return max(0, limit - spent - reserve)


def ordered_instruments(registry, previous):
    return sorted(registry.items(), key=lambda pair:(previous.get(pair[0], ''), pair[0]))


def refresh(max_calls=20, reserve=1, root=ROOT):
    import requests
    key = load_key(target='JSETrading/EODHD/Research')
    if not key: return {'state':'KEY_NOT_CONFIGURED'}
    try:
        response = requests.get('https://eodhd.com/api/user', params={'api_token':key,'fmt':'json'},
                                timeout=20,allow_redirects=False)
    except requests.RequestException as exc:
        return {'state':'USAGE_UNAVAILABLE','error_type':type(exc).__name__}
    if response.status_code != 200: return {'state':'USAGE_UNAVAILABLE','http_status':response.status_code}
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        quota = min(max_calls, remaining_quota(response.json(), today, reserve))
    except (ValueError, TypeError, KeyError): return {'state':'USAGE_INVALID'}
    root = Path(root)
    folder = root/'runtime/local-swing-data/eodhd'; folder.mkdir(parents=True,exist_ok=True)
    journal = folder/'batch-attempts.jsonl'; already = set(); previous = {}
    if journal.exists():
        for line in journal.read_text(encoding='utf-8').splitlines():
            try:
                entry=json.loads(line)
                if entry.get('utc_day') == today: already.add(entry['instrument'])
                previous[entry['instrument']] = max(previous.get(entry['instrument'], ''), entry.get('utc_day',''))
            except (ValueError,KeyError,TypeError):
                return {'state':'ATTEMPT_JOURNAL_INVALID'}
    registry = mappings(root/'runtime/local-swing-data/radar-public-prices')
    results=[]
    # Never-captured instruments first; later batches rotate toward the oldest
    # attempt so a limited quota cannot starve the end of the alphabet.
    for instrument, code in ordered_instruments(registry, previous):
        if len(results) >= quota: break
        if instrument in already: continue
        existing=list(folder.glob(instrument+'-*.json'))
        if existing:
            try:
                last=json.loads(max(existing,key=lambda p:p.stat().st_mtime_ns).read_bytes())
                if last.get('acquired_at','')[:10] == today: continue
            except (OSError,ValueError,TypeError): pass
        try: result=probe(instrument,root)
        except (OSError,ValueError,KeyError,TypeError,ArithmeticError) as exc:
            result={'state':'CAPTURE_FAILED','error_type':type(exc).__name__}
        entry={'utc_day':today,'instrument':instrument,'symbol':code,'capture':result}
        if result.get('state') == 'CAPTURED_RESEARCH_ONLY':
            try:
                report=build(code,instrument,root)
                entry['zebra']=report.get('eodhd',{'state':'UNKNOWN'})
            except (OSError,ValueError,KeyError,TypeError,ArithmeticError) as exc:
                entry['zebra']={'state':'REBUILD_FAILED','error_type':type(exc).__name__}
        with journal.open('a',encoding='utf-8') as out:
            out.write(json.dumps(entry,sort_keys=True,allow_nan=False)+'\n')
        results.append(entry)
        print(json.dumps({'instrument':instrument,'capture':result.get('state'),
                          'zebra':entry.get('zebra',{}).get('state')},sort_keys=True),flush=True)
        if result.get('state') in ('KEY_NOT_CONFIGURED','NETWORK_FAILED','UNSAFE_OR_INVALID_RESPONSE','CAPTURE_FAILED'):
            break
        if result.get('state')=='PROVIDER_REJECTED' and result.get('http_status') in (401,403,429): break
    remaining = sum(not list(folder.glob(instrument+'-*.json')) for instrument in registry)
    return {'state':'BATCH_COMPLETE','utc_day':today,'quota_at_start':quota,'attempted':len(results),
            'without_retained_capture':remaining,
            'results':results}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-calls',type=int,default=20)
    parser.add_argument('--reserve',type=int,default=1)
    args=parser.parse_args()
    if args.max_calls < 0 or args.reserve < 0: parser.error('nonnegative limits required')
    print(json.dumps(refresh(args.max_calls,args.reserve),sort_keys=True),flush=True)
