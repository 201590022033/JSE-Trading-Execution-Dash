"""Explicit audited repair of duplicate IRESS display rows; strict parser unchanged."""
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import re
from copy import deepcopy

FIELDS = ('Open', 'High', 'Low', 'Close', 'Volume')
PERCENT = ('% Change', '% Change vs Average')
VERSION = 'iress-identical-ohlcv-duplicates-v1'


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def derive_iress_export(raw, instrument_id, acquired_at, now):
    from .source_resolution import parse_iress_export
    from .ost_data import catalog
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Bounded native export required')
    origin = catalog()[instrument_id]['ost_code']+'.JSE'
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    required = {'Date', *FIELDS}
    if (not required <= set(reader.fieldnames or ()) or set(reader.fieldnames)-required-set(PERCENT)
            or len(reader.fieldnames) != len(set(reader.fieldnames))):
        raise ValueError('Exact IRESS daily columns required')
    retained, duplicates, seen = [], [], {}
    for line, row in enumerate(reader, 2):
        if line > 10001:
            raise ValueError('Bounded native rows required')
        if None in row or any(not isinstance(row.get(field), str) or not row[field].strip() for field in ('Date', *FIELDS)):
            raise ValueError('Complete native Date and OHLCV cells required')
        try:
            units = {f: Decimal(row[f].replace(',', '').replace(' ', '').replace('\xa0', '')) for f in FIELDS}
            if any(not v.is_finite() or v != v.to_integral_value() or v < 0 for v in units.values()):
                raise ValueError('Integer cents and whole volume only')
            units = {f: int(v) for f, v in units.items()}
        except (InvalidOperation, TypeError, KeyError) as exc:
            raise ValueError('Exact native OHLCV required') from exc
        day = row['Date'].strip()
        if day in seen:
            old_line, old_row, old_units = seen[day]
            if old_units != units:
                raise ValueError('Conflicting duplicate OHLCV: source remains quarantined')
            duplicates.append({'source_date': day, 'kept_csv_line': old_line, 'removed_csv_line': line,
                'exact_ohlcv_units': units, 'derived_fields': {f: {'kept': old_row.get(f), 'removed': row.get(f)} for f in PERCENT}})
        else:
            seen[day] = (line, row, units)
            retained.append({f: row[f] for f in ('Date', *FIELDS)})
    if not duplicates:
        raise ValueError('No duplicate repair required; use strict native parser')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=('Date', *FIELDS), lineterminator='\n')
    writer.writeheader(); writer.writerows(retained)
    derived = stream.getvalue().encode()
    chart = parse_iress_export(derived, instrument_id, origin, acquired_at, now)
    receipt = {'version': VERSION, 'instrument_id': instrument_id, 'origin_symbol': origin,
        'acquired_at': chart['acquired_at'], 'original_source_sha256': sha256(raw).hexdigest(),
        'derived_source_sha256': sha256(derived).hexdigest(), 'original_bytes': len(raw), 'derived_bytes': len(derived),
        'original_rows': len(retained)+len(duplicates), 'derived_rows': len(retained), 'duplicates': duplicates,
        'transformation': 'DROP_DERIVED_PERCENT_COLUMNS_AND_COLLAPSE_IDENTICAL_OHLCV_DUPLICATES',
        'source_semantics': 'UNVERIFIED', 'trading_weight': 0}
    receipt['receipt_sha256'] = _digest(receipt)
    return derived, receipt


def validate_receipts(receipts, charts):
    if not isinstance(receipts, dict) or not receipts or set(receipts)-set(charts):
        raise ValueError('Transform receipts require matching separate research charts')
    result = {}
    for key, receipt in receipts.items():
        fields = {'version', 'instrument_id', 'origin_symbol', 'acquired_at', 'original_source_sha256',
            'derived_source_sha256', 'original_bytes', 'derived_bytes', 'original_rows', 'derived_rows',
            'duplicates', 'transformation', 'source_semantics', 'trading_weight', 'receipt_sha256'}
        if not isinstance(receipt, dict) or set(receipt) != fields:
            raise ValueError('Strict bounded transformation receipt required')
        for name, maximum in [('original_bytes', 2_500_000), ('derived_bytes', 2_500_000), ('original_rows', 10000), ('derived_rows', 10000)]:
            if type(receipt[name]) is not int or not 1 <= receipt[name] <= maximum:
                raise ValueError('Bounded positive source transformation counts required')
        duplicates = receipt['duplicates']
        if (not isinstance(duplicates, list) or not duplicates or receipt['original_rows']-receipt['derived_rows'] != len(duplicates)
                or receipt['transformation'] != 'DROP_DERIVED_PERCENT_COLUMNS_AND_COLLAPSE_IDENTICAL_OHLCV_DUPLICATES'
                or type(receipt['trading_weight']) is not int or receipt['trading_weight'] != 0):
            raise ValueError('Exact duplicate-only transformation contract required')
        removed = set()
        for entry in duplicates:
            if (not isinstance(entry, dict) or set(entry) != {'source_date', 'kept_csv_line', 'removed_csv_line', 'exact_ohlcv_units', 'derived_fields'}
                    or not isinstance(entry['source_date'], str)
                    or any(type(entry[n]) is not int for n in ('kept_csv_line', 'removed_csv_line'))
                    or not 2 <= entry['kept_csv_line'] < entry['removed_csv_line'] <= receipt['original_rows']+1
                    or entry['removed_csv_line'] in removed):
                raise ValueError('Unambiguous original duplicate row positions required')
            removed.add(entry['removed_csv_line'])
            units, derived_fields = entry['exact_ohlcv_units'], entry['derived_fields']
            if (not isinstance(units, dict) or set(units) != set(FIELDS)
                    or any(type(v) is not int or v < 0 for v in units.values())
                    or not isinstance(derived_fields, dict) or set(derived_fields) != set(PERCENT)
                    or any(not isinstance(v, dict) or set(v) != {'kept', 'removed'}
                        or any(x is not None and not isinstance(x, str) for x in v.values()) for v in derived_fields.values())):
                raise ValueError('Exact OHLCV and derived display-column audit required')
        expected = receipt.get('receipt_sha256')
        content = {k: v for k, v in receipt.items() if k != 'receipt_sha256'}
        chart = charts[key]
        if (receipt.get('version') != VERSION or expected != _digest(content) or receipt.get('instrument_id') != key
                or receipt.get('derived_source_sha256') != chart['provenance']['source_sha256']
                or receipt.get('acquired_at') != chart['provenance']['acquired_at']
                or receipt.get('origin_symbol') != chart['provenance']['origin_symbol']
                or any(not isinstance(receipt[n], str) or not re.fullmatch('[0-9a-f]{64}', receipt[n]) for n in ('original_source_sha256', 'derived_source_sha256', 'receipt_sha256'))
                or not receipt.get('duplicates') or receipt.get('source_semantics') != 'UNVERIFIED'):
            raise ValueError('Unchanged hash-bound native/derived transform receipt required')
        result[key] = deepcopy(receipt)
    return result


def install_derived_iress(raw, instrument_id, acquired_at, now, folder=None):
    from .source_resolution import install_iress_candidate, read_candidates
    from .ost_data import ROOT, atomic_json
    folder = folder or ROOT
    derived, receipt = derive_iress_export(raw, instrument_id, acquired_at, now)
    archive = folder/'alternative-exports'; archive.mkdir(parents=True, exist_ok=True)
    for label, value, digest in [('native', raw, receipt['original_source_sha256']), ('derived', derived, receipt['derived_source_sha256'])]:
        path = archive/f'{instrument_id}-IRESS-{label}-{digest}.csv'
        if path.exists() and path.read_bytes() != value:
            raise ValueError('Immutable source archive conflict')
        if not path.exists(): path.write_bytes(value)
    # Persist the transformation before candidate installation; a failed install
    # cannot expose a candidate without its original raw lineage.
    transforms = folder/'source-transforms.json'
    saved = json.loads(transforms.read_text()) if transforms.exists() else {}
    history = folder/'transform-receipts'; history.mkdir(exist_ok=True)
    immutable_receipt = history/(receipt['receipt_sha256']+'.json')
    if not immutable_receipt.exists(): atomic_json(immutable_receipt, receipt)
    active = saved.setdefault(receipt['derived_source_sha256'], receipt)
    atomic_json(transforms, saved)
    chart = install_iress_candidate(derived, instrument_id, receipt['origin_symbol'], active['acquired_at'], now, folder)
    candidates = read_candidates(folder)
    candidates['charts'][instrument_id]['IRESS']['transform_receipt_sha256'] = active['receipt_sha256']
    atomic_json(folder/'alternative-sources.json', candidates)
    return {'chart': chart, 'transform': active, 'acquisition_attempt': receipt,
            'state': 'DERIVED_CONTENT_REUSED_NO_RECEIPT_REFRESH' if active != receipt else 'AUDITED_DERIVED_SOURCE_INSTALLED'}
