"""Watch-scoped, historical daily Zebra preparation and bounded public refresh.

Local prewarm reads existing captures only. Refresh is a separate explicit call;
its receipts report attempts, never turn manual OST/IRESS into automatic feeds.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from application.opportunities.zebra_screen_data import FIELDS, SOURCE_PRIORITY, load_zebra_screen_data

ROOT = Path(__file__).resolve().parents[2]
MAX_REFRESH_INSTRUMENTS = 5


def _keys(instruments, limit=None):
    if isinstance(instruments, (str, bytes)):
        raise ValueError('instrument sequence required')
    result = list(dict.fromkeys(instruments))
    if any(not isinstance(k, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}', k) for k in result):
        raise ValueError('invalid instrument identifier')
    if limit is not None and len(result) > limit:
        raise ValueError('refresh exceeds watch batch limit')
    return result


def prewarm_daily(instruments, *, root=None, now=None, max_rows=None, loader=load_zebra_screen_data):
    """Read only saved data for watches; preserve every selected field and receipt.

    Source diagnostics returned by Zebra count captures globally, so they are
    explicitly labelled archive-wide rather than presented as per-share failures.
    """
    keys = _keys(instruments)
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('timezone-aware time required')
    if not keys:
        return {'state': 'EMPTY', 'as_of': when.isoformat(), 'watches': {},
                'research_only': True, 'live_execution': False}
    data = loader(root=root, now=when, max_rows=max_rows, instruments=keys)
    watches = {}
    for key in keys:
        item = data.get('instruments', {}).get(key)
        rows = item['rows'] if item else []
        coverage = {f: sum(r.get(f) is not None for r in rows) for f in FIELDS}
        providers = {source: {'state': 'NO_RETAINED_FIELD', 'field_observations': 0,
                              'latest_acquired_at': None} for source in SOURCE_PRIORITY}
        states = Counter()
        for row in rows:
            for field in FIELDS:
                detail = row['fields'][field]
                states[detail['state']] += 1
                candidates = [detail, *detail.get('alternatives', [])]
                for c in candidates:
                    name = c.get('source')
                    if name not in providers or c.get('value') is None:
                        continue
                    p = providers[name]
                    p['state'] = 'RETAINED_HISTORICAL_FIELDS'
                    p['field_observations'] += 1
                    stamp = c.get('acquired_at')
                    if stamp and (p['latest_acquired_at'] is None or stamp > p['latest_acquired_at']):
                        p['latest_acquired_at'] = stamp
        for source in ('OST', 'IRESS'):
            providers[source]['automatic_feed'] = 'UNVERIFIED_MANUAL_CAPTURE'
        watches[key] = {'state': 'AVAILABLE' if rows else 'NO_RETAINED_HISTORY',
                        'instrument': key, 'latest_session': item.get('latest_session') if item else None,
                        'expected_session': data.get('expected_session'), 'sessions': len(rows),
                        'coverage': coverage, 'field_states': dict(states), 'sources': providers,
                        'history': item, 'historical_not_quote': True}
    return {'state': 'AVAILABLE' if any(x['sessions'] for x in watches.values()) else 'UNAVAILABLE',
            'as_of': data.get('as_of', when.isoformat()), 'watches': watches,
            'archive_source_diagnostics': data.get('source_diagnostics', {}),
            'availability': data.get('availability'), 'research_only': True, 'live_execution': False}


def _capture_yahoo(keys, mapping, folder):
    from application.opportunities.radar_price_capture import capture
    from jse_adapter import YahooFinanceFetcher
    result = capture({'source_leads': [{'instrument_ids': keys, 'source_id': 'strategy-radar-m2'}]},
                     YahooFinanceFetcher(), folder / 'radar-public-prices', limit=len(keys),
                     screen_issuers={k: mapping[k] for k in keys if k == mapping[k]})
    output = {}
    for row in result['results']:
        record = dict(row)
        if row.get('state') == 'CAPTURED':
            path = folder / 'radar-public-prices' / row['file']
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('capture receipt hash mismatch')
            record['acquired_at'] = json.loads(raw)['acquired_at']
        output[row['instrument']] = record
    for key in result.get('unmapped_instruments', []):
        output[key] = {'instrument': key, 'state': 'IDENTITY_UNAVAILABLE'}
    return output


def _capture_sharedata(key, code, folder):
    from scripts.capture_sharedata_prices import capture
    return capture(code, folder / 'sharedata-prices')


def refresh_daily(instruments, *, root=None, yahoo_capture=_capture_yahoo,
                  sharedata_capture=_capture_sharedata):
    """Attempt public capture for up to five watches and persist a receipt.

    Explicitly invoked by an owning scheduler/request, never by prewarm/read.
    Caller batches larger pinned sets and controls cadence. No EODHD or broker
    calls. Each provider failure is independent; prior captures are untouched.
    """
    keys = _keys(instruments, MAX_REFRESH_INSTRUMENTS)
    root = Path(root) if root is not None else ROOT
    folder = root / 'runtime/local-swing-data'
    from application.opportunities.zebra_instruments import mappings
    mapping = mappings(folder / 'radar-public-prices')
    started = datetime.now(timezone.utc).isoformat()
    results = {key: {'YAHOO': {'state': 'IDENTITY_UNAVAILABLE'},
                     'SHAREDATA': {'state': 'IDENTITY_UNAVAILABLE'},
                     'OST': {'state': 'MANUAL_CAPTURE_AUTOMATION_UNVERIFIED'},
                     'IRESS': {'state': 'MANUAL_CAPTURE_AUTOMATION_UNVERIFIED'}} for key in keys}
    eligible = [key for key in keys if key in mapping]
    if eligible:
        try:
            yahoo = yahoo_capture(eligible, mapping, folder)
            for key in eligible:
                results[key]['YAHOO'] = yahoo.get(key, {'state': 'NO_RESULT'})
        except Exception as exc:
            for key in eligible:
                results[key]['YAHOO'] = {'state': 'FAILED', 'error_type': type(exc).__name__}
        for key in eligible:
            try:
                capture = sharedata_capture(key, mapping[key], folder)
                results[key]['SHAREDATA'] = {'state': 'CAPTURED', **capture}
            except Exception as exc:
                results[key]['SHAREDATA'] = {'state': 'FAILED', 'error_type': type(exc).__name__}
    receipt = {'schema': 'strategy-radar-daily-refresh-v1', 'started_at': started,
               'finished_at': datetime.now(timezone.utc).isoformat(), 'results': results,
               'research_only': True, 'live_execution': False}
    raw = (json.dumps(receipt, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    target = folder / 'strategy-radar-refresh-receipts' / (sha256(raw).hexdigest() + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle:
        handle.write(raw)
    return {**receipt, 'receipt': str(target)}
