"""Retain native ViewPoint Time Series OHLC without promoting rounded volume."""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
from pathlib import Path

from .public_research import _available_at
from .swing_data_quality import real_ohlc


def parse(raw, symbol, acquired_at, now):
    if symbol != 'SOL.JSE' or not isinstance(raw, bytes) or not 0 < len(raw) <= 2500000:
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
        if _available_at(session) > acquired_at:
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
    return {'schema': 'iress-price-only-v1', 'instrument': 'SASOL', 'origin_symbol': symbol,
            'provider': 'IRESS_TIME_SERIES', 'acquired_at': acquired_at.isoformat(),
            'source_sha256': sha256(raw).hexdigest(), 'price_units': 'ZAR',
            'volume_basis': 'ROUNDED_SOURCE_VOLUME_NOT_IMPORTED',
            'historical_availability': 'UNVERIFIED', 'research_only': True,
            'live_execution': False, 'calendar_completeness': 'UNVERIFIED',
            'excluded_rows': sorted(excluded, key=lambda x: x['session']), 'bars': bars}


def register(path, folder, now):
    path, folder = Path(path), Path(folder)
    if not path.name.startswith('Time Series (SOL.JSE)_') or path.suffix.lower() != '.csv':
        raise ValueError('native SOL.JSE Time Series filename required')
    acquired = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    raw = path.read_bytes()
    result = parse(raw, 'SOL.JSE', acquired, now)
    archive = folder / 'price-only' / 'raw'
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / (result['source_sha256'] + '.csv')
    if target.exists() and target.read_bytes() != raw:
        raise ValueError('source hash collision')
    if not target.exists():
        target.write_bytes(raw)
    receipt = folder / 'price-only' / (result['source_sha256'] + '.json')
    if receipt.exists():
        previous = json.loads(receipt.read_text(encoding='utf-8'))
        if previous['source_sha256'] != result['source_sha256'] or parse(raw, 'SOL.JSE', datetime.fromisoformat(previous['acquired_at']), now) != previous:
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
            if parsed == saved and path.stem == digest:
                valid.append(parsed)
        except (OSError, ValueError, TypeError, KeyError, UnicodeError):
            continue
    return max(valid, key=lambda x: x['acquired_at'], default=None)
