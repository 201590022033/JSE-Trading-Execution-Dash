"""Field-qualified retained Zebra geometry; research, never a quote or order."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from math import isfinite
from pathlib import Path
import json

from application.opportunities.session_freshness import latest_expected_session, next_session

VERSION = 'swing-close-reference-v2'
STRATEGY = 'jse_swing_3_5d'
STRATEGY_VERSION = '1.1.0'
_ACCEPTED = {'SINGLE_SOURCE', 'AGREEMENT', 'THREE_PROVIDER_AGREEMENT'}
_CONFLICT = 'CONFLICT_NO_CONSENSUS'


def _eligible_alternatives(item, session, now):
    """Expose only alternatives actually received and qualified by evaluation."""
    raw = item.get('alternatives', [])
    if not isinstance(raw, list):
        return [], 1
    output, omitted = [], 0
    for candidate in raw:
        try:
            if not isinstance(candidate, dict):
                raise ValueError('candidate is not an object')
            source = candidate['source']
            value = float(candidate['value'])
            acquired = datetime.fromisoformat(candidate['acquired_at'].replace('Z', '+00:00'))
            if (not isinstance(source, str) or not source.strip() or not isfinite(value) or value <= 0
                    or acquired.tzinfo is None or acquired.utcoffset() is None
                    or not session + timedelta(hours=15) <= acquired <= now):
                raise ValueError('unqualified candidate')
            output.append({'source': source, 'value': value,
                           'acquired_at': acquired.astimezone(timezone.utc).isoformat(),
                           'source_sha256': candidate.get('source_sha256'),
                           'field_source_sha256': candidate.get('field_source_sha256'),
                           'upstream_independence': candidate.get('upstream_independence')})
        except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
            omitted += 1
    return output, omitted


def _field(row, name, now):
    """Keep only observed, qualified, causally received Zebra values."""
    try:
        item = row['fields'][name]
        value = float(item['value'])
        receipt = datetime.fromisoformat(item['acquired_at'].replace('Z', '+00:00'))
        session = datetime.fromisoformat(row['session']).replace(tzinfo=timezone.utc)
        if (item.get('state') not in _ACCEPTED | {_CONFLICT} or not isinstance(item.get('source'), str)
                or not item['source'].strip() or not receipt.tzinfo or receipt.utcoffset() is None
                or not session + timedelta(hours=15) <= receipt <= now
                or not isfinite(value) or value <= 0):
            return None
        alternatives, omitted = _eligible_alternatives(item, session, now) if item['state'] == _CONFLICT else ([], 0)
        return {'value': value, 'source': item['source'], 'state': item['state'],
                'received_at': receipt.astimezone(timezone.utc).isoformat(),
                'session': row['session'],
                'source_sha256': item.get('source_sha256'),
                'field_source_sha256': item.get('field_source_sha256'),
                'upstream_independence': item.get('upstream_independence'),
                'alternatives': alternatives, 'alternatives_omitted_count': omitted}
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
        return None


def _sources(observations):
    result = {}
    for name in ('high', 'low', 'close'):
        items = [row[name] for row in observations if row.get(name)]
        if not items:
            continue
        result[name] = {'sources': sorted({item['source'] for item in items}),
                        'first_received_at': min(item['received_at'] for item in items),
                        'last_received_at': max(item['received_at'] for item in items),
                        'field_states': sorted({item['state'] for item in items}),
                        'observations': [{'session': item['session'], 'value': item['value'],
                                          'source': item['source'], 'received_at': item['received_at'],
                                          'state': item['state'], 'source_sha256': item['source_sha256'],
                                          'field_source_sha256': item['field_source_sha256'],
                                          'upstream_independence': item['upstream_independence']} for item in items],
                        'conflicts': [{'session': item['session'], 'selected_value': item['value'],
                                       'selected_source': item['source'], 'selected_received_at': item['received_at'],
                                       'alternatives': item['alternatives'],
                                       'alternatives_omitted_count': item['alternatives_omitted_count']} for item in items if item['state'] == _CONFLICT]}
    return result


def research_proposal(service, instrument, product, *, now=None):
    """Expose qualified components independently; never fabricate missing inputs.

    A stale completed-session close remains available as historical evidence;
    Zebra's selected conflicting values are retained as conditional candidates.
    Geometry uses only a contiguous suffix of retained high/low/close fields,
    with Wilder ATR initialized on that explicitly disclosed suffix. No open,
    volume, benchmark, live quote, fill or broker mapping is inferred.
    """
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('timezone-aware evaluation time required')
    base = {'contract_version': VERSION, 'instrument': instrument, 'product': product,
            'strategy_id': STRATEGY, 'strategy_version': STRATEGY_VERSION,
            'timeframe': 'daily', 'evaluated_at': when.isoformat(),
            'state': 'UNAVAILABLE', 'research_only': True, 'live_execution': False,
            'basis': 'COMPLETED_SESSION_HISTORICAL_CLOSE_NOT_QUOTE_OR_FILL',
            'costs': None, 'spread_slippage': None, 'quantity': None,
            'entry_reference': None, 'stop_reference': None, 'target_reference': None,
            'risk_per_share': None, 'risk_reward_before_costs': None,
            'broker_input': None, 'broker_input_status': 'UNVERIFIED',
            'limitations': ['Not a trade signal or broker order',
                            'Benchmark is not evaluated by this geometry-only proposal',
                            'Costs, spread, slippage and quantity not provided',
                            'OST order-field units unverified']}
    if not isinstance(instrument, str) or not any(w.get('instrument') == instrument for w in service.store.list_watches()):
        return {**base, 'reason': 'WATCH_IDENTITY_UNAVAILABLE'}
    if product != 'CASH_SHARE':
        return {**base, 'reason': 'PRODUCT_UNSUPPORTED'}
    try:
        daily = json.loads((Path(service.folder) / 'daily-cache' / (instrument + '.json')).read_text(encoding='utf-8'))['daily']
        rows = daily['history']['rows']
        if not isinstance(rows, list):
            raise ValueError('invalid retained rows')
        expected = latest_expected_session(when)
        cutoff = expected or (when.astimezone(timezone.utc).date() - timedelta(days=1)).isoformat()
        declared_latest = daily.get('latest_session')
        invalid_declared_latest = False
        if declared_latest:
            try:
                if date.fromisoformat(declared_latest).isoformat() != declared_latest:
                    raise ValueError('non-canonical date')
                cutoff = min(cutoff, declared_latest)
            except (TypeError, ValueError):
                invalid_declared_latest = True
        by_date = {}
        duplicates = set()
        invalid_rows = 0
        for row in rows:
            try:
                session = row['session']
                if date.fromisoformat(session).isoformat() != session:
                    raise ValueError('non-canonical date')
            except (KeyError, TypeError, ValueError):
                invalid_rows += 1
                continue
            if session <= cutoff:
                if session in by_date or session in duplicates:
                    by_date.pop(session, None)
                    duplicates.add(session)
                else:
                    by_date[session] = row
        sessions = sorted(by_date)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {**base, 'reason': 'DAILY_SOURCE_UNAVAILABLE', 'freshness': 'UNKNOWN'}
    diagnostics = {'invalid_session_rows': invalid_rows, 'duplicate_sessions': sorted(duplicates),
                   'invalid_declared_latest': invalid_declared_latest,
                   'policy': 'QUARANTINE_INVALID_OR_AMBIGUOUS_ROWS_NEVER_PICK_A_DUPLICATE'}
    base = {**base, 'data_quality': diagnostics}
    available = [day for day in sessions if _field(by_date[day], 'close', when)]
    if not available:
        return {**base, 'reason': 'QUALIFIED_CLOSE_UNAVAILABLE', 'freshness': 'UNKNOWN',
                'missing': ['QUALIFIED_CLOSE_UNAVAILABLE']}
    selected = available[-1]
    latest = by_date[selected]
    latest_close = _field(latest, 'close', when)
    freshness = 'CURRENT_COMPLETED_SESSION' if expected == selected else ('STALE' if expected else 'CALENDAR_UNVERIFIED')
    base = {**base, 'state': 'PARTIAL', 'reason': 'HLC_GEOMETRY_UNAVAILABLE',
            'session': selected, 'expected_session': expected, 'freshness': freshness,
            'entry_reference': latest_close['value'], 'currency': 'ZAR',
            'source_symbol': instrument, 'source_fields': {'close': _sources([{'close': latest_close}])['close']},
            'missing': ['CONTIGUOUS_QUALIFIED_HLC_REQUIRED'],
            'limitations': base['limitations'] + ['Reference close is historical, not a current quote or observed fill']}
    if latest_close['state'] == _CONFLICT:
        base['limitations'].append('Selected close has conflicting sources; value is a provisional candidate')
    # Reconstruct a suffix in chronological order and stop at the first gap or
    # missing HLC field; gaps are never compressed into adjacent sessions.
    suffix = []
    for day in reversed(sessions):
        if day > selected:
            continue
        if suffix and next_session(day) != suffix[0]['session']:
            break
        obs = {'session': day}
        for name in ('high', 'low', 'close'):
            obs[name] = _field(by_date[day], name, when)
        if not all(obs.values()) or not (obs['low']['value'] <= obs['close']['value'] <= obs['high']['value']):
            break
        suffix.insert(0, obs)
        if len(suffix) >= 100:
            break
    if len(suffix) < 15:
        return {**base, 'qualified_hlc_sessions': len(suffix)}
    closes = [item['close']['value'] for item in suffix]
    ranges = [max(item['high']['value']-item['low']['value'],
                  abs(item['high']['value']-closes[i-1]),
                  abs(item['low']['value']-closes[i-1]))
              for i, item in enumerate(suffix) if i > 0]
    atr = sum(ranges[:14])/14
    for value in ranges[14:]:
        atr = (13*atr+value)/14
    stop = min(min(item['low']['value'] for item in suffix[-11:-1]), closes[-1]-atr)
    risk = closes[-1]-stop
    if not (isfinite(stop) and isfinite(risk) and 0 < stop < closes[-1]):
        return {**base, 'reason': 'VALID_REFERENCE_GEOMETRY_UNAVAILABLE', 'qualified_hlc_sessions': len(suffix)}
    source_hash = sha256(json.dumps(suffix, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    conflicting = any(item[field]['state'] == _CONFLICT for item in suffix for field in ('high', 'low', 'close'))
    conditional = conflicting or invalid_declared_latest
    limitations = base['limitations'] + (['Geometry uses Zebra-selected conflicting fields and is conditional, not a confirmed value'] if conflicting else [])
    if invalid_declared_latest:
        limitations.append('Cache latest-session metadata is invalid; selected date is conditional')
    return {**base, 'state': 'CONDITIONAL_REFERENCE' if conditional else 'HISTORICAL_REFERENCE', 'reason': None,
            'limitations': limitations,
            'source_bars': len(suffix), 'qualified_hlc_sessions': len(suffix),
            'window_start_session': suffix[0]['session'], 'window_end_session': suffix[-1]['session'],
            'atr_initialization': 'FIRST_14_TRUE_RANGES_THEN_WILDER_ON_CONTIGUOUS_WINDOW',
            'source_sha256': source_hash, 'source_fields': _sources(suffix),
            'stop_reference': stop, 'target_reference': closes[-1]+2*risk,
            'risk_per_share': risk, 'risk_reward_before_costs': 2.0,
            'stop_rule': 'LOWER_OF_PRIOR_10_SESSION_LOW_AND_ONE_ATR_BELOW_CLOSE',
            'assumptions': ['Historical completed close is not an observed fill',
                            'Wilder ATR initialized on the displayed contiguous qualified HLC window',
                            'Stop is lower of prior ten-session low and close minus one Wilder ATR',
                            'Target is two times reference risk before costs'], 'missing': []}
