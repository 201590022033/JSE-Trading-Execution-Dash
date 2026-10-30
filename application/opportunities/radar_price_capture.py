"""Capture bounded public price histories for explicitly linked radar issuers.

These are separate local research observations, not canonical prices or orders.
"""
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import math
import re
from .public_research import public_share_catalog


def usable_close(stamp, acquired):
    """Research cutoff: after 17:20 SAST; provider finality is not certified."""
    day = datetime.fromisoformat(stamp.replace('Z', '+00:00')).date()
    close = datetime.combine(day, time(17, 20), tzinfo=timezone(timedelta(hours=2)))
    return close <= acquired


def radar_instruments(radar, catalog=None, limit=10):
    catalog = public_share_catalog() if catalog is None else catalog
    found = {}
    watches = [w for w in radar.get('watches', [])
               if w.get('state') not in {'EXPIRED_UNREVIEWED', 'SPLIT_INTO_EVENT_WATCHES', 'OCCURRED', 'NOT_OBSERVED', 'INCORRECT_LINK'}]
    for item in watches + radar.get('source_leads', []):
        for key in item.get('instrument_ids', []):
            if key in catalog:
                found.setdefault(key, []).append(item.get('record_id') or item.get('source_id'))
    return [(key, found[key]) for key in sorted(found)[:limit]]


def capture(radar, fetcher, output, *, clock=None, limit=10):
    clock = clock or (lambda: datetime.now(timezone.utc))
    catalog = public_share_catalog()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    eligible = radar_instruments(radar, catalog, len(catalog))
    active_items = [w for w in radar.get('watches', []) if w.get('state') not in {
        'EXPIRED_UNREVIEWED', 'SPLIT_INTO_EVENT_WATCHES', 'OCCURRED', 'NOT_OBSERVED', 'INCORRECT_LINK'}] + radar.get('source_leads', [])
    unmapped = sorted({key for item in active_items for key in item.get('instrument_ids', []) if key not in catalog})
    def last_capture(item):
        existing = sorted(output.glob(item[0]+'-*.json'))
        return existing[-1].name.split('-')[1] if existing else ''
    # Never let the same alphabetically first names starve newer issuers.
    eligible.sort(key=lambda item: (last_capture(item), item[0]))
    for key, references in eligible[:limit]:
        started = clock()
        try:
            symbol = catalog[key]['yahoo_symbol']
            chart = fetcher.get_chart(symbol, '5y')
            acquired = clock()
            if chart.get('symbol') != symbol or chart.get('currency') != 'ZAR' or chart.get('interval') != '1d':
                raise ValueError('provider identity or currency mismatch')
            # Retain the complete normalized provider response, including the
            # intraday row. Its use is separately bounded by acquisition time.
            eligible_rows = [r for r in chart['bars'] if usable_close(r['timestamp'], acquired)]
            if not eligible_rows:
                raise ValueError('no completed close observations')
            payload = {'schema': 'radar-public-price-capture-v1', 'instrument': key,
                'symbol': symbol, 'provider': 'YAHOO', 'started_at': started.isoformat(),
                'acquired_at': acquired.isoformat(), 'radar_references': references,
                'completed_sessions': len(eligible_rows), 'last_completed_session': eligible_rows[-1]['timestamp'][:10],
                'chart': chart, 'history_window': '5y', 'raw_provider_bytes_retained': False,
                'close_cutoff': '17:20_SAST_ASSUMED_PROVIDER_FINALITY_UNVERIFIED',
                'price_basis': 'UNVERIFIED', 'historical_availability': 'RECONSTRUCTED',
                'purpose': 'RESEARCH_ONLY_NOT_CURRENT_QUOTE', 'live_execution': False}
            raw = (json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8')
            digest = sha256(raw).hexdigest()
            path = output / (key+'-'+acquired.strftime('%Y%m%dT%H%M%S%fZ')+'-'+digest+'.json')
            with path.open('xb') as handle:
                handle.write(raw)
            results.append({'instrument': key, 'state': 'CAPTURED', 'file': path.name,
                            'sha256': digest, 'completed_sessions': len(eligible_rows),
                            'last_completed_session': payload['last_completed_session']})
        except Exception as exc:
            results.append({'instrument': key, 'state': 'FAILED', 'error_type': type(exc).__name__})
    state = ('NO_LINKED_ISSUERS' if not eligible and not unmapped else
             'COMPLETE' if len(eligible) <= limit and not unmapped and all(r['state'] == 'CAPTURED' for r in results) else 'PARTIAL')
    return {'state': state,
            'selected': len(results), 'deferred': max(0, len(eligible)-limit), 'unmapped_instruments': unmapped,
            'limit': limit, 'results': results, 'live_execution': False}


def latest_close_history(output, instrument):
    """Read retained normalized closes without expiring the historical rows."""
    catalog = public_share_catalog()
    if instrument not in catalog or not re.fullmatch(r'[A-Z0-9_]+', instrument):
        raise ValueError('registered instrument required')
    candidates = sorted(Path(output).glob(instrument+'-*.json'), reverse=True)
    if not candidates:
        raise FileNotFoundError('no capture for instrument')
    path = candidates[0]
    raw = path.read_bytes()
    if len(raw) > 3000000 or path.stem.split('-')[-1] != sha256(raw).hexdigest():
        raise ValueError('capture integrity mismatch')
    payload = json.loads(raw)
    chart = payload['chart']
    if (payload['instrument'] != instrument or payload['provider'] != 'YAHOO'
            or chart['symbol'] != catalog[instrument]['yahoo_symbol'] or chart['currency'] != 'ZAR'):
        raise ValueError('source identity mismatch')
    acquired = datetime.fromisoformat(payload['acquired_at'])
    from .swing_data_quality import real_ohlc
    rows = []
    for row in chart['bars']:
        close = row.get('close')
        if (usable_close(row['timestamp'], acquired) and isinstance(close, (int, float))
                and not isinstance(close, bool) and math.isfinite(close) and close > 0):
            rows.append({'session': row['timestamp'][:10], 'close': close,
                         'open': row.get('open'), 'high': row.get('high'), 'low': row.get('low'),
                         'volume': row.get('volume'), 'ohlc_valid': real_ohlc(row)})
    if any(a['session'] >= b['session'] for a, b in zip(rows, rows[1:])):
        raise ValueError('ordered unique sessions required')
    return {'state': 'AVAILABLE', 'instrument': instrument, 'provider': 'YAHOO',
            'acquired_at': payload['acquired_at'], 'source_sha256': sha256(raw).hexdigest(),
            'rows': rows, 'availability': 'RECONSTRUCTED_HISTORICAL',
            'close_cutoff': payload['close_cutoff'], 'research_only': True, 'live_execution': False}
