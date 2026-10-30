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

# Research discovery only: adding this identity must not change the canonical
# trading universe. JSE BVT and Yahoo BVT.JO identify The Bidvest Group Limited.
RESEARCH_ISSUERS = {'BVT': {'name': 'The Bidvest Group Limited', 'sector': 'Industrials', 'yahoo_symbol': 'BVT.JO'}}


def research_catalog():
    return {**public_share_catalog(), **RESEARCH_ISSUERS}


def discovered_issuers(radar):
    """SENS codes are provisional candidates until Yahoo confirms identity."""
    items = {}
    for source in radar.get('sens_discovery', {}).get('sources', []):
        code = (source.get('provenance') or {}).get('share_code')
        if source.get('current') and isinstance(code, str) and re.fullmatch(r'[A-Z]{2,5}', code):
            items.setdefault(code, {'name':code, 'sector':'Unknown', 'yahoo_symbol':code+'.JO',
                                    'identity_basis':'SENS_CODE_YAHOO_METADATA'})
    return items


def usable_close(stamp, acquired):
    """Research cutoff: after 17:20 SAST; provider finality is not certified."""
    day = datetime.fromisoformat(stamp.replace('Z', '+00:00')).date()
    close = datetime.combine(day, time(17, 20), tzinfo=timezone(timedelta(hours=2)))
    return close <= acquired


def radar_instruments(radar, catalog=None, limit=10):
    catalog = {**discovered_issuers(radar), **research_catalog()} if catalog is None else catalog
    found = {}
    watches = [w for w in radar.get('watches', [])
               if w.get('state') not in {'EXPIRED_UNREVIEWED', 'SPLIT_INTO_EVENT_WATCHES', 'OCCURRED', 'NOT_OBSERVED', 'INCORRECT_LINK'}]
    for item in watches + radar.get('source_leads', []) + radar.get('calendar_upcoming', []):
        ids = list(item.get('instrument_ids', []))
        # Exact issuer wording can be linked even when an older radar scope
        # was frozen before the research-only Bidvest mapping existed.
        text = ' '.join(str(item.get(field, '')) for field in ('quote', 'headline', 'title'))
        if re.search(r'\bbidvest\b', text, re.IGNORECASE) and 'BVT' not in ids:
            ids.append('BVT')
        for key in ids:
            if key in catalog:
                found.setdefault(key, []).append(item.get('record_id') or item.get('source_id'))
    for source in radar.get('sens_discovery', {}).get('sources', []):
        key = (source.get('provenance') or {}).get('share_code')
        if source.get('current') and key in catalog:
            found.setdefault(key, []).append(source.get('source_id'))
    # A SENS code can differ from an existing local key (e.g. IMP / IMPJ).
    # Merge only an exact provider-symbol match; never guess from company names.
    registered = {v['yahoo_symbol']: k for k,v in research_catalog().items()}
    for key in list(found):
        target = registered.get(catalog[key]['yahoo_symbol'])
        if target and target != key and target in catalog:
            found.setdefault(target, []).extend(found.pop(key))
    return [(key, found[key]) for key in sorted(found)[:limit]]


def capture(radar, fetcher, output, *, clock=None, limit=10):
    clock = clock or (lambda: datetime.now(timezone.utc))
    catalog = {**discovered_issuers(radar), **research_catalog()}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    eligible = radar_instruments(radar, catalog, len(catalog))
    active_items = [w for w in radar.get('watches', []) if w.get('state') not in {
        'EXPIRED_UNREVIEWED', 'SPLIT_INTO_EVENT_WATCHES', 'OCCURRED', 'NOT_OBSERVED', 'INCORRECT_LINK'}] + radar.get('source_leads', []) + radar.get('calendar_upcoming', [])
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
            if catalog[key].get('identity_basis') and (chart.get('provider_symbol') != symbol or chart.get('instrument_type') != 'EQUITY' or chart.get('exchange') != 'JNB'):
                raise ValueError('provisional SENS code requires matching Yahoo equity metadata')
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
                'identity_basis': catalog[key].get('identity_basis', 'REGISTERED_RESEARCH_ISSUER'),
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
    catalog = research_catalog()
    if not re.fullmatch(r'[A-Z0-9_]+', instrument):
        raise ValueError('bounded instrument required')
    candidates = sorted(Path(output).glob(instrument+'-*.json'), reverse=True)
    if not candidates:
        raise FileNotFoundError('no capture for instrument')
    path = candidates[0]
    raw = path.read_bytes()
    if len(raw) > 3000000 or path.stem.split('-')[-1] != sha256(raw).hexdigest():
        raise ValueError('capture integrity mismatch')
    payload = json.loads(raw)
    chart = payload['chart']
    expected = catalog.get(instrument, {}).get('yahoo_symbol', instrument+'.JO')
    if (payload['instrument'] != instrument or payload['provider'] != 'YAHOO'
            or chart['symbol'] != expected or chart['currency'] != 'ZAR'):
        raise ValueError('source identity mismatch')
    if instrument not in catalog and (payload.get('identity_basis') != 'SENS_CODE_YAHOO_METADATA' or chart.get('provider_symbol') != expected or chart.get('instrument_type') != 'EQUITY' or chart.get('exchange') != 'JNB'):
        raise ValueError('unverified discovered source identity')
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
            'identity_basis': payload.get('identity_basis', 'REGISTERED_RESEARCH_ISSUER'),
            'rows': rows, 'availability': 'RECONSTRUCTED_HISTORICAL',
            'close_cutoff': payload['close_cutoff'], 'research_only': True, 'live_execution': False}
