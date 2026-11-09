"""Read-only import adapters. No broker session, credential or network access."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from .intraday_store import IntradayCache, normalize_bar


def manual_viewpoint_rows(instrument, raw_rows, received_at, *, unit='ZAR_CENTS', interval_minutes=30):
    """Prepare displayed chart rows without inventing timezone or bar boundaries.

    The UI's date label and rounded volume stay in raw_payload. A receipt time is
    supplied by the actual importer; no source event timestamp is inferred.
    """
    if not isinstance(raw_rows, list) or not raw_rows or len(raw_rows) > 2000:
        raise ValueError('one to 2000 observed rows required')
    records = []
    for row in raw_rows:
        if not isinstance(row, dict) or not isinstance(row.get('label'), str) or not row['label'].strip():
            raise ValueError('the visible source date label is required')
        if row.get('volume') not in (None, '') and row.get('volume_exact') is not True:
            raise ValueError('volume requires an explicit exact-value confirmation')
        fields = {f: row.get(f) for f in ('open','high','low','close','volume')}
        for key, value in fields.items():
            if isinstance(value, str): fields[key] = value.strip().replace(',', '') or None
        record = {'instrument':instrument, 'source':'IRESS_VIEWPOINT_MANUAL', 'interval_minutes':interval_minutes,
                  'bar_start':None, 'bar_end':None, 'source_timestamp':None,
                  'received_at':received_at.isoformat(), 'clock_semantics':'UNKNOWN',
                  'availability':'MANUAL', 'unit':unit, 'fields':fields,
                  'provisional':True, 'raw_payload':json.dumps(row, sort_keys=True)}
        normalized = normalize_bar(record)
        if normalized['invalid_fields'] or not any(value is not None for value in normalized['fields'].values()):
            raise ValueError('enter at least one valid observed field; rounded volume is not exact')
        records.append(record)
    return records


def eodhd_intraday_rows(instrument, symbol, payload, received_at, *, price_unit, unit_evidence, verified_mapping):
    """Parse documented 5m start-clock payload after an authorized API response.

    Mapping, scale and actual entitlement are caller-provided evidence. This is
    a parser only: it never contacts a provider or consumes quota.
    """
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JSE', symbol or ''):
        raise ValueError('exact JSE symbol required')
    if not isinstance(verified_mapping, dict) or verified_mapping.get(instrument) != symbol:
        raise ValueError('verified instrument mapping required')
    if price_unit not in ('ZAR','ZAR_CENTS') or not isinstance(unit_evidence,str) or not unit_evidence.strip():
        raise ValueError('verified price unit and evidence required')
    if not isinstance(payload, list) or len(payload) > 10000:
        raise ValueError('bounded provider array required')
    records=[]
    for row in payload:
        if not isinstance(row,dict) or type(row.get('timestamp')) is not int:
            raise ValueError('provider UTC start timestamp required')
        start=datetime.fromtimestamp(row['timestamp'],timezone.utc)
        record={'instrument':instrument, 'source':'EODHD', 'interval_minutes':5,
                'bar_start':start.isoformat(), 'bar_end':(start+timedelta(minutes=5)).isoformat(),
                'source_timestamp':start.isoformat(), 'received_at':received_at.isoformat(),
                'clock_semantics':'START', 'availability':'DELAYED', 'unit':price_unit,
                'fields':{f:row.get(f) for f in ('open','high','low','close','volume')},
                'provisional':start+timedelta(minutes=5)>received_at,
                'raw_payload':json.dumps({'symbol':symbol,'unit_evidence':unit_evidence,'row':row},sort_keys=True)}
        normalize_bar(record)
        records.append(record)
    return records


def retain(cache, records, *, evidence=False, pinned=False):
    if not isinstance(cache, IntradayCache): raise TypeError('intraday cache required')
    return [cache.put(row,evidence=evidence,pinned=pinned) for row in records]
