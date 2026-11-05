"""Register an operator-supplied Moneyweb daily-close CSV for local research.

The CSV's actual format and units must be supplied explicitly; this importer
does not log in, download data, infer a ticker from prices, or claim that a
locally supplied file was independently authenticated by Moneyweb.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.radar_price_capture import usable_close
from application.opportunities.zebra_instruments import mappings


def normalize(raw, *, date_column, close_column, unit, date_format, received_at):
    if len(raw)>5_000_000: raise ValueError('CSV exceeds 5 MB')
    if unit not in ('ZAR','ZAR_CENTS'): raise ValueError('explicit ZAR or ZAR_CENTS required')
    received=datetime.fromisoformat(received_at.replace('Z','+00:00'))
    if received.tzinfo is None: raise ValueError('timezone-aware receipt time required')
    text=raw.decode('utf-8-sig'); reader=csv.DictReader(io.StringIO(text,newline=''))
    fields=reader.fieldnames or []
    if len(set(fields)) != len(fields) or date_column not in fields or close_column not in fields or date_column == close_column:
        raise ValueError('explicit unique date and close column names required')
    rows=[]; excluded=0
    for index,item in enumerate(reader):
        if index >= 30000: raise ValueError('CSV exceeds 30000 observations')
        day=datetime.strptime(item[date_column].strip(),date_format).date().isoformat()
        try:
            price=Decimal(item[close_column].strip().replace(',',''))
            if not price.is_finite() or price<=0: raise ValueError('positive close required')
        except (InvalidOperation,AttributeError,KeyError): raise ValueError('invalid close')
        if not usable_close(day,received): excluded+=1; continue
        rows.append({'session':day,'close':str(price/(100 if unit=='ZAR_CENTS' else 1))})
    rows.sort(key=lambda row:row['session'])
    if not rows or any(a['session']==b['session'] for a,b in zip(rows,rows[1:])):
        raise ValueError('nonempty unique completed sessions required')
    return rows,excluded


def register(path, *, instrument, symbol, source_url, date_column, close_column, unit,
             date_format='%Y-%m-%d', root=ROOT, clock=None):
    instrument=instrument.upper(); symbol=symbol.upper(); root=Path(root)
    if not re.fullmatch('[A-Z0-9_]{2,16}',instrument): raise ValueError('instrument identifier required')
    registry=mappings(root/'runtime/local-swing-data/radar-public-prices')
    if registry.get(instrument) != symbol: raise ValueError('instrument and registered JSE symbol must agree')
    parsed=urlsplit(source_url)
    if parsed.scheme!='https' or parsed.hostname not in ('moneyweb.co.za','www.moneyweb.co.za') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('public Moneyweb HTTPS source URL without query or credentials required')
    path=Path(path); raw=path.read_bytes(); received=(clock or (lambda:datetime.now(timezone.utc)))()
    if received.tzinfo is None or received > datetime.now(timezone.utc): raise ValueError('actual nonfuture receipt required')
    rows,excluded=normalize(raw,date_column=date_column,close_column=close_column,unit=unit,
                            date_format=date_format,received_at=received.isoformat())
    folder=root/'runtime/local-swing-data/moneyweb-prices'; rawdir=folder/'raw'; rawdir.mkdir(parents=True,exist_ok=True)
    rawhash=sha256(raw).hexdigest(); original=rawdir/(rawhash+'.csv')
    if not original.exists(): original.write_bytes(raw)
    data={'schema':'moneyweb-close-capture-v1','provider':'MONEYWEB','instrument':instrument,'symbol':symbol,
          'source_url':source_url,'identity_basis':'OPERATOR_SELECTED_SYMBOL_NOT_PROVIDER_AUTHENTICATED',
          'source_authenticity':'OPERATOR_SUPPLIED_EXPORT_NOT_INDEPENDENTLY_VERIFIED',
          'raw_sha256':rawhash,'source_filename':path.name,'received_at':received.isoformat(),
          'downloaded_at':None,'download_time_basis':'NOT_OBSERVED_LOCAL_IMPORT_TIME_ONLY',
          'date_column':date_column,'close_column':close_column,'input_units':unit,'date_format':date_format,
          'excluded_uncompleted_rows':excluded,'rows':rows,'research_only':True,'live_execution':False}
    result=(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode()
    digest=sha256(result).hexdigest(); out=folder/(instrument+'-'+digest+'.json')
    if not out.exists(): out.write_bytes(result)
    return {'path':str(out),'capture_sha256':digest,'raw_sha256':rawhash,'sessions':len(rows),
            'first_session':rows[0]['session'],'last_session':rows[-1]['session'],
            'received_at':received.isoformat(),'state':'IMPORTED_AWAITING_CROSS_SOURCE_IDENTITY_CHECK'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path');p.add_argument('--instrument',required=True)
    p.add_argument('--symbol',required=True);p.add_argument('--source-url',required=True)
    p.add_argument('--date-column',required=True);p.add_argument('--close-column',required=True)
    p.add_argument('--unit',choices=('ZAR','ZAR_CENTS'),required=True);p.add_argument('--date-format',default='%Y-%m-%d')
    a=p.parse_args(); result=register(a.path,instrument=a.instrument,symbol=a.symbol,source_url=a.source_url,
         date_column=a.date_column,close_column=a.close_column,unit=a.unit,date_format=a.date_format)
    try:
        from scripts.reconcile_zebra_prices import build
        result['comparison']=build(a.symbol.upper(),a.instrument.upper())
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result['comparison']={'state':'FAILED_CAPTURE_RETAINED','error_type':type(exc).__name__}
    print(json.dumps(result))
