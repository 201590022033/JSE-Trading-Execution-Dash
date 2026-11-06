"""Retain native ViewPoint Time Series OHLC without promoting rounded volume."""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path
import re

from .public_research import _available_at
from .swing_data_quality import real_ohlc

SYMBOLS = {'SOL.JSE':'SASOL', 'BTI.JSE':'BTI', 'FSR.JSE':'FSR', 'ABG.JSE':'ABSPJ',
           'STX40.JSE':'ETF_STX40', 'STXFIN.JSE':'ETF_STXFIN',
           'STXRES.JSE':'ETF_STXRES', 'STXIND.JSE':'ETF_STXIND'}


def parse(raw, symbol, acquired_at, now, *, after_close=False):
    if symbol not in SYMBOLS or not isinstance(raw, bytes) or not 0 < len(raw) <= 2500000:
        raise ValueError('explicit supported IRESS symbol and bounded bytes required')
    if acquired_at.tzinfo is None or now.tzinfo is None or acquired_at > now:
        raise ValueError('actual aware acquisition time required')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not {'Date', 'Open', 'High', 'Low', 'Close', 'Volume'} <= set(reader.fieldnames or ()):
        raise ValueError('native Time Series fields required')
    seen, bars, excluded = set(), [], []
    for count, row in enumerate(reader):
        if count >= 10000:
            raise ValueError('too many rows')
        session = datetime.strptime(row['Date'], '%d-%b-%Y').date().isoformat()
        if session in seen:
            raise ValueError('duplicate session')
        seen.add(session)
        # The original receipt, not a later reprocessing time, determines what
        # was complete when captured. Never promote the intraday row later.
        from .radar_price_capture import usable_close
        if not (usable_close(session, acquired_at) if after_close else _available_at(session) <= acquired_at):
            continue
        try:
            values = {key: Decimal(row[key.title()].replace(',', '')) / 100
                      for key in ('open', 'high', 'low', 'close')}
            if not all(v.is_finite() for v in values.values()):
                raise ValueError('invalid price')
        except (InvalidOperation, KeyError, AttributeError) as exc:
            raise ValueError('exact numeric OHLC required') from exc
        bar = {'timestamp': session, **{k: float(v) for k, v in values.items()}, 'volume': None}
        if not real_ohlc(bar):
            # ViewPoint emits zero-OHL placeholder rows on some non-trading
            # dates. Keep their identities visible; never convert them to bars.
            excluded.append({'session': session, 'reason': 'INVALID_OR_ZERO_OHLC'})
            continue
        bars.append(bar)
    bars.sort(key=lambda b: b['timestamp'])
    if not bars:
        raise ValueError('no completed bars')
    return {'schema': 'iress-price-only-v2-after-close' if after_close else 'iress-price-only-v1', 'instrument': SYMBOLS[symbol], 'origin_symbol': symbol,
            'provider': 'IRESS_TIME_SERIES', 'acquired_at': acquired_at.isoformat(),
            'source_sha256': sha256(raw).hexdigest(), 'price_units': 'ZAR',
            'volume_basis': 'ROUNDED_SOURCE_VOLUME_NOT_IMPORTED',
            'historical_availability': 'UNVERIFIED', 'research_only': True,
            'live_execution': False, 'calendar_completeness': 'UNVERIFIED',
            'excluded_rows': sorted(excluded, key=lambda x: x['session']), 'bars': bars}


def register(path, folder, now, *, after_close=False):
    path, folder = Path(path), Path(folder)
    match = re.fullmatch(r'Time Series \(([A-Z0-9]+\.JSE)\)_.+\.csv', path.name, re.IGNORECASE)
    if not match or match.group(1).upper() not in SYMBOLS:
        raise ValueError('supported native IRESS Time Series filename required')
    symbol = match.group(1).upper()
    acquired = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    raw = path.read_bytes()
    result = parse(raw, symbol, acquired, now, after_close=after_close)
    base = folder / ('price-only-after-close' if after_close else 'price-only')
    archive = base / 'raw'
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / (result['source_sha256'] + '.csv')
    if target.exists() and target.read_bytes() != raw:
        raise ValueError('source hash collision')
    if not target.exists():
        target.write_bytes(raw)
    receipt = base / (result['source_sha256'] + '.json')
    if receipt.exists():
        previous = json.loads(receipt.read_text(encoding='utf-8'))
        if previous['source_sha256'] != result['source_sha256'] or parse(raw, symbol, datetime.fromisoformat(previous['acquired_at']), now, after_close=after_close) != previous:
            raise ValueError('existing receipt does not match source')
        return previous
    receipt.write_text(json.dumps(result, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    return result


def latest(folder, now):
    """Revalidate raw bytes against every receipt; select latest acquisition."""
    root = Path(folder) / 'price-only'
    valid = []
    for path in root.glob('*.json'):
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            digest = saved['source_sha256']
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                continue
            raw = (root / 'raw' / (digest + '.csv')).read_bytes()
            acquired = datetime.fromisoformat(saved['acquired_at'])
            parsed = parse(raw, saved['origin_symbol'], acquired, now)
            if parsed == saved and path.stem == digest and saved['instrument'] == 'SASOL':
                valid.append(parsed)
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            continue
    return max(valid, key=lambda x: x['acquired_at'], default=None)
