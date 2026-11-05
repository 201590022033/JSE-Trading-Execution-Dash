"""Retain public ShareData chart responses for explicitly named JSE research shares."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.radar_price_capture import usable_close

FIELDS = ('date', 'open', 'high', 'low', 'close', 'volume')
BASE = 'https://www.sharedata.co.za/V2/Controls/Chart/InteractiveChart/JSONdata.aspx'


class ChartIdentity(HTMLParser):
    def __init__(self):
        super().__init__(); self.symbol = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == 'input' and values.get('id') == 'IC_JSECode':
            self.symbol = values.get('value')


def verify_identity_receipt(capture, folder):
    """Check retained provider chart identity when the capture contains it."""
    receipt = capture.get('identity_receipt')
    if receipt is None:
        return False  # Older captures are explicitly legacy; overlap still applies.
    raw = (Path(folder)/'raw'/(receipt['raw_sha256']+'.html')).read_bytes()
    if sha256(raw).hexdigest() != receipt['raw_sha256']:
        raise ValueError('ShareData identity source hash mismatch')
    parsed = ChartIdentity(); parsed.feed(raw.decode('utf-8',errors='replace'))
    if parsed.symbol != capture['symbol']:
        raise ValueError('ShareData identity source mismatch')
    return True


def capture(code, output):
    if not re.fullmatch('[A-Z][A-Z0-9]{1,7}', code): raise ValueError('explicit JSE share code required')
    output = Path(output); rawdir = output/'raw'; rawdir.mkdir(parents=True, exist_ok=True)
    chart_url = 'https://www.sharedata.co.za/v2/Scripts/Chart.aspx?'+urlencode({'c':code,'x':'JSE'})
    with urlopen(Request(chart_url,headers={'User-Agent':'Mozilla/5.0'}), timeout=20) as response:
        chart_raw = response.read(2_000_001)
    identity_acquired = datetime.now(timezone.utc).isoformat()
    if len(chart_raw) > 2_000_000: raise ValueError('oversized identity response')
    parsed = ChartIdentity(); parsed.feed(chart_raw.decode('utf-8',errors='replace'))
    if parsed.symbol != code: raise ValueError('ShareData chart did not confirm instrument code')
    identity_hash = sha256(chart_raw).hexdigest(); identity_path = rawdir/(identity_hash+'.html')
    if not identity_path.exists(): identity_path.write_bytes(chart_raw)
    arrays, receipts = {}, []
    for field in FIELDS:
        url = BASE+'?'+urlencode({'c':code, 'All':'ALL', 'p':field})
        req = Request(url, headers={'User-Agent':'Mozilla/5.0',
            'Referer':f'https://www.sharedata.co.za/v2/Scripts/Chart.aspx?c={code}&x=JSE'})
        with urlopen(req, timeout=20) as response:
            raw = response.read(2_000_001)
        acquired = datetime.now(timezone.utc)
        if len(raw) > 2_000_000: raise ValueError('oversized chart response')
        digest = sha256(raw).hexdigest(); target = rawdir/(digest+'.json')
        if not target.exists(): target.write_bytes(raw)
        values = json.loads(raw)
        if not isinstance(values, list) or not values: raise ValueError('empty or unavailable chart data')
        arrays[field] = values
        receipts.append({'field':field, 'url':url, 'raw_sha256':digest, 'acquired_at':acquired.isoformat()})
    if len({len(values) for values in arrays.values()}) != 1:
        raise ValueError('source arrays have different lengths')
    rows = []
    for i, epoch in enumerate(arrays['date']):
        day = datetime.fromtimestamp(epoch/1000, timezone.utc).date().isoformat()
        if not usable_close(day, datetime.fromisoformat(receipts[0]['acquired_at'])): continue
        row = {'session':day}
        for field in ('open','high','low','close'):
            value = arrays[field][i]
            row[field] = str(Decimal(str(value))/100) if value is not None else None
        row['volume'] = arrays['volume'][i]
        rows.append(row)
    if not rows or any(a['session'] >= b['session'] for a,b in zip(rows,rows[1:])):
        raise ValueError('ordered completed rows required')
    result = {'schema':'sharedata-chart-capture-v1','provider':'SHAREDATA','symbol':code,
        'currency':'ZAR','provider_price_units':'ZAR_CENTS','normalized_price_units':'ZAR',
        'identity_receipt':{'url':chart_url,'raw_sha256':identity_hash,'acquired_at':identity_acquired},
        'retrieval_started_at':receipts[0]['acquired_at'],'acquired_at':receipts[-1]['acquired_at'],
        'raw_responses':receipts,'rows':rows,'research_only':True}
    raw = (json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    digest = sha256(raw).hexdigest(); target = output/(code+'-'+digest+'.json')
    if not target.exists(): target.write_bytes(raw)
    return {'path':str(target),'capture_sha256':digest,'rows':len(rows),'first':rows[0]['session'],
            'last':rows[-1]['session'],'acquired_at':result['acquired_at']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('code'); parser.add_argument('--output',default=str(ROOT/'runtime/local-swing-data/sharedata-prices'))
    args=parser.parse_args(); print(json.dumps(capture(args.code,args.output)))
