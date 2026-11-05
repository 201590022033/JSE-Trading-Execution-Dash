"""Retain one bounded EODHD research probe without storing its API key."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.africa_api_credentials import load_key
from application.opportunities.radar_price_capture import latest_close_history, usable_close
from application.opportunities.zebra_instruments import mappings


def sharedata_reference(folder, code, digest=None):
    from scripts.capture_sharedata_prices import verify_identity_receipt
    paths = list((folder/'sharedata-prices').glob(code+'-'+(digest or '*')+'.json'))
    if not paths: raise ValueError('ShareData reference unavailable')
    path = max(paths, key=lambda p:p.stat().st_mtime_ns)
    raw = path.read_bytes(); digest = sha256(raw).hexdigest(); item = json.loads(raw)
    if (path.stem != code+'-'+digest or item.get('symbol') != code or item.get('provider') != 'SHAREDATA'
            or item.get('currency') != 'ZAR' or item.get('schema') != 'sharedata-chart-capture-v1'):
        raise ValueError('ShareData reference identity mismatch')
    verify_identity_receipt(item, folder/'sharedata-prices')
    for receipt in item['raw_responses']:
        source=(folder/'sharedata-prices/raw'/(receipt['raw_sha256']+'.json')).read_bytes()
        if sha256(source).hexdigest() != receipt['raw_sha256']: raise ValueError('ShareData reference raw mismatch')
    return {'provider':'SHAREDATA','source_sha256':digest,'rows':item['rows']}


def unit_check(result, data, folder, instrument, code):
    try:
        public = latest_close_history(folder/'radar-public-prices', instrument)
        reference = {'provider':'YAHOO','source_sha256':public['source_sha256'],'rows':public['rows']}
    except (OSError, ValueError, KeyError, TypeError):
        reference = sharedata_reference(folder, code)
    cents = lambda v: Decimal(str(v)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    peer = {r['session']: cents(r['close']) for r in reference['rows'] if r.get('close') is not None}
    overlap = [r for r in data if r['date'] in peer and r.get('close') is not None][-60:]
    for label, divisor in [('ZAR', 1), ('ZAR_CENTS', 100)]:
        matches = sum(cents(Decimal(str(r['close'])) / divisor) == peer[r['date']] for r in overlap)
        result['cross_checks'][label] = {'overlap': len(overlap), 'matches': matches}
    candidates = [label for label, item in result['cross_checks'].items() if item['matches'] >= 20]
    if len(candidates) == 1: result['price_unit'] = candidates[0]
    result['reference_sha256'] = reference['source_sha256']
    result['reference_provider'] = reference['provider']
    result.pop('cross_check_error', None)


def rows_for_unit(raw, unit, acquired_at):
    """Normalize observed bars; retain missing fields and exclude live sessions."""
    data = json.loads(raw)
    if not isinstance(data, list) or unit not in ('ZAR', 'ZAR_CENTS'):
        raise ValueError('history and price unit required')
    acquired = datetime.fromisoformat(acquired_at.replace('Z', '+00:00'))
    if acquired.tzinfo is None: raise ValueError('acquisition time required')
    rows = []
    for item in data:
        day = datetime.strptime(item['date'], '%Y-%m-%d').date().isoformat()
        if not usable_close(day, acquired) or item.get('close') is None: continue
        row = {'session': day}
        for field in ('open', 'high', 'low', 'close'):
            try:
                value = Decimal(str(item[field]))
                if not value.is_finite() or value <= 0: raise ValueError('invalid price')
                row[field] = str(value / (100 if unit == 'ZAR_CENTS' else 1))
            except (KeyError, ValueError, TypeError, ArithmeticError):
                row[field] = None
        volume = item.get('volume')
        row['volume'] = volume if type(volume) is int and volume >= 0 else None
        if row['close'] is not None: rows.append(row)
    rows.sort(key=lambda r: r['session'])
    if any(a['session'] == b['session'] for a, b in zip(rows, rows[1:])):
        raise ValueError('duplicate sessions')
    return rows


def load_eodhd_history(folder, instrument, code):
    """Reproduce the captured bars and price scale from retained source bytes."""
    folder = Path(folder)
    paths = list((folder/'eodhd').glob(instrument+'-*.json'))
    if not paths: raise ValueError('EODHD capture unavailable')
    path = max(paths, key=lambda p:p.stat().st_mtime_ns)
    receipt = path.read_bytes(); receipt_hash = sha256(receipt).hexdigest(); item = json.loads(receipt)
    if (path.stem != instrument+'-'+receipt_hash or item.get('instrument') != instrument
            or item.get('symbol') != code+'.JSE' or item.get('state') != 'CAPTURED_RESEARCH_ONLY'
            or item.get('price_unit') not in ('ZAR', 'ZAR_CENTS')):
        raise ValueError('EODHD receipt identity or unit mismatch')
    raw = (folder/'eodhd/raw'/(item['raw_sha256']+'.json')).read_bytes()
    if sha256(raw).hexdigest() != item['raw_sha256']: raise ValueError('EODHD raw hash mismatch')
    reference_hash = item['reference_sha256']
    if item.get('reference_provider', 'YAHOO') == 'SHAREDATA':
        ref = sharedata_reference(folder, code, reference_hash)
        peer_rows = ref['rows']
    else:
        refs = list((folder/'radar-public-prices').glob(instrument+'-*'+reference_hash+'.json'))
        if len(refs) != 1: raise ValueError('EODHD reference unavailable')
        contents = refs[0].read_bytes()
        if sha256(contents).hexdigest() != reference_hash: raise ValueError('EODHD reference hash mismatch')
        ref = json.loads(contents)
        if ref.get('provider') != 'YAHOO' or ref.get('instrument') != instrument or ref.get('symbol') != code+'.JO':
            raise ValueError('EODHD reference identity mismatch')
        peer_rows = [{'session':r['timestamp'][:10], 'close':r.get('close')} for r in ref['chart']['bars']]
    cents = lambda n: Decimal(str(n)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    peer = {r['session']:cents(r['close']) for r in peer_rows if r.get('close') is not None}
    rows = rows_for_unit(raw,item['price_unit'],item['acquired_at'])
    overlap = [r for r in rows if r['session'] in peer][-60:]
    if sum(cents(r['close']) == peer[r['session']] for r in overlap) < 20:
        raise ValueError('EODHD price scale not established')
    return {'instrument':instrument,'provider':'EODHD','symbol':code,'source_sha256':receipt_hash,
            'raw_sha256':item['raw_sha256'],'acquired_at':item['acquired_at'],
            'price_unit':item['price_unit'],'rows':rows,'upstream_independence':'UNVERIFIED'}


def probe(instrument, root=ROOT):
    import requests
    root = Path(root)
    folder = root / 'runtime/local-swing-data'
    code = mappings(folder / 'radar-public-prices').get(instrument)
    if not code:
        raise ValueError('registered instrument required')
    key = load_key(target='JSETrading/EODHD/Research')
    if not key:
        return {'state': 'KEY_NOT_CONFIGURED'}
    try:
        response = requests.get('https://eodhd.com/api/eod/' + code + '.JSE',
                                params={'api_token': key, 'fmt': 'json', 'period': 'd'},
                                timeout=20, allow_redirects=False)
    except requests.RequestException as exc:
        return {'state': 'NETWORK_FAILED', 'error_type': type(exc).__name__}
    acquired = datetime.now(timezone.utc)
    if response.status_code != 200:
        return {'state': 'PROVIDER_REJECTED', 'http_status': response.status_code}
    raw = response.content
    if not isinstance(raw, bytes) or len(raw) > 3000000 or key.encode() in raw:
        return {'state': 'UNSAFE_OR_INVALID_RESPONSE'}
    data = json.loads(raw)
    if not isinstance(data, list):
        return {'state': 'INVALID_RESPONSE'}
    folder = folder / 'eodhd'
    (folder / 'raw').mkdir(parents=True, exist_ok=True)
    digest = sha256(raw).hexdigest()
    rawpath = folder / 'raw' / (digest + '.json')
    if not rawpath.exists(): rawpath.write_bytes(raw)
    rows = [r for r in data if usable_close(r['date'], acquired)]
    result = {'state': 'CAPTURED_RESEARCH_ONLY' if rows else 'EMPTY_HISTORY',
              'instrument': instrument, 'symbol': code + '.JSE', 'acquired_at': acquired.isoformat(),
              'raw_sha256': digest, 'sessions': len(rows), 'upstream_independence': 'UNVERIFIED',
              'price_unit': 'UNVERIFIED', 'cross_checks': {}}
    if rows:
        try:
            unit_check(result,rows,root/'runtime/local-swing-data',instrument,code)
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
            result['cross_check_error'] = 'REFERENCE_UNAVAILABLE_OR_INVALID'
    encoded = (json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode()
    receipt = sha256(encoded).hexdigest()
    (folder / (instrument + '-' + receipt + '.json')).write_bytes(encoded)
    return result


if __name__ == '__main__':
    print(json.dumps(probe(sys.argv[1]), sort_keys=True))
