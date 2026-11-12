"""Read-only import adapters. No broker session, credential or network access."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import csv
import io
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
        if not any(value is not None for value in normalized['fields'].values()):
            raise ValueError('enter at least one valid observed field; rounded volume is not exact')
        records.append(record)
    return records


def viewpoint_table_csv(raw, instrument, symbol, received_at, *, file_name, file_modified_at=None,
                        interval_minutes=5, accept_operator_conventions=False):
    """Parse a ViewPoint chart-table export using the owner's accepted conventions."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('bounded CSV bytes required')
    if accept_operator_conventions is not True:
        raise ValueError('operator acceptance of the CSV conventions is required')
    if not isinstance(file_name, str) or not file_name.lower().endswith('.csv') or len(file_name) > 200:
        raise ValueError('CSV filename required')
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JSE', symbol or ''):
        raise ValueError('exact JSE chart symbol required')
    if type(interval_minutes) is not int or interval_minutes not in (5, 30):
        raise ValueError('five or thirty minute chart interval required')
    if received_at.tzinfo is None or received_at.utcoffset() is None:
        raise ValueError('timezone-aware import receipt required')
    if file_modified_at is not None and (file_modified_at.tzinfo is None or file_modified_at.utcoffset() is None):
        raise ValueError('timezone-aware file modification time required')

    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        required = {'Date', 'Open', 'High', 'Low', 'Close', 'Volume'}
        if not required.issubset(set(reader.fieldnames or ())):
            raise ValueError('ViewPoint Date/OHLCV columns required')
        records, seen = [], set()
        for index, row in enumerate(reader):
            if index >= 2000:
                raise ValueError('at most 2000 chart rows are supported')
            stamp = row.get('Date')
            if not isinstance(stamp, str) or not stamp.endswith('Z'):
                raise ValueError('UTC Z timestamps required in the Date column')
            source_time = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if source_time in seen:
                raise ValueError('duplicate chart timestamp')
            seen.add(source_time)
            raw_fields = {}
            for field in ('Open', 'High', 'Low', 'Close'):
                value = Decimal(row[field].replace(',', ''))
                if not value.is_finite() or value <= 0:
                    raise ValueError('positive numeric OHLC values required')
                raw_fields[field.lower()] = str(value)
            volume = row['Volume']
            if not re.fullmatch(r'(?:\d+|\d{1,3}(?:,\d{3})+)', volume or ''):
                raise ValueError('numeric Volume column required')
            raw_fields['volume'] = volume.replace(',', '')
            raw_row = {key: value for key, value in row.items() if key is not None}
            bar_end = source_time + timedelta(minutes=interval_minutes)
            record = {
                'instrument': instrument, 'source': 'IRESS_VIEWPOINT_TABLE_CSV',
                'interval_minutes': interval_minutes,
                'bar_start': source_time.isoformat(), 'bar_end': bar_end.isoformat(),
                'source_timestamp': source_time.isoformat(),
                'received_at': received_at.isoformat(), 'clock_semantics': 'START',
                'source_timestamp_basis': 'UTC Date column; interval start accepted by owner',
                'normalization_basis': 'OPERATOR_ACCEPTED_VIEWPOINT_CSV_CONVENTION_V1',
                'availability': 'MANUAL', 'unit': 'ZAR_CENTS',
                'fields': raw_fields,
                'provisional': bar_end > received_at,
                'raw_payload': json.dumps({
                    'format': 'IRESS_VIEWPOINT_TABLE_CSV',
                    'file_name': file_name,
                    'file_modified_at': file_modified_at.isoformat() if file_modified_at else None,
                    'timestamp': stamp,
                    'raw_values': raw_row,
                    'qualification': {
                        'state': 'OPERATOR_ACCEPTED_CONVENTION',
                        'price_unit': 'ZAR_CENTS',
                        'volume_unit': 'SHARES_AS_EXPORTED',
                        'bar_boundary': 'START',
                        'use_for_scoring': True,
                        'basis': 'Price magnitude matches retained JSE daily rand scale; UTC timestamps advance at the selected chart interval.',
                    },
                }, sort_keys=True),
            }
            normalize_bar(record)
            records.append(record)
    except (UnicodeError, csv.Error, InvalidOperation, KeyError, TypeError, AttributeError) as exc:
        raise ValueError('invalid ViewPoint chart-table CSV') from exc
    if not records:
        raise ValueError('CSV must contain at least one chart row')
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
