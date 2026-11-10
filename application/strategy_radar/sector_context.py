"""Read-only, coverage-qualified sector research from retained daily caches.

This is a current research grouping, not a JSE index or historical membership.
No network access or cache writes are performed by this module.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from application.opportunities.research_classification import VERSION, classifications
from application.opportunities.session_freshness import latest_expected_session, next_session
from application.opportunities.zebra_instruments import mappings

UNIVERSE_VERSION = 'registered-research-cash-universe-v1'
QUALIFIED_STATES = frozenset({'SINGLE_SOURCE', 'AGREEMENT', 'THREE_PROVIDER_AGREEMENT'})
USABLE_STATES = QUALIFIED_STATES | {'CONFLICT_NO_CONSENSUS'}


def _previous_session(session):
    d = date.fromisoformat(session) - timedelta(days=1)
    while d.year == 2026:
        if next_session(d.isoformat()) == session:
            return d.isoformat()
        d -= timedelta(days=1)
    return None


def _alternatives(detail, day, now):
    """Show only alternatives actually received by this evaluation time."""
    accepted, omitted = [], 0
    values = detail.get('alternatives', [])
    if not isinstance(values, list):
        return [], 1
    for candidate in values:
        try:
            source = candidate['source']
            value = Decimal(str(candidate['value']))
            if not isinstance(source, str) or not source.strip() or not value.is_finite() or value <= 0:
                raise ValueError('unqualified source or value')
            acquired = datetime.fromisoformat(candidate['acquired_at'].replace('Z', '+00:00'))
            earliest = datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(hours=15)
            if acquired.tzinfo is None or acquired.utcoffset() is None or not earliest <= acquired <= now:
                raise ValueError('unqualified receipt')
            accepted.append(candidate)
        except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation, OverflowError):
            omitted += 1
    return accepted, omitted


def _closes(folder, key, sessions, now):
    try:
        data = json.loads((Path(folder) / 'daily-cache' / (key + '.json')).read_text(encoding='utf-8'))
        daily = data['daily']
        rows = daily['history']['rows']
        # Duplicate sessions are ambiguous: never silently pick a revision.
        by_date = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            day = row.get('session')
            if day in sessions:
                if day in by_date:
                    return None
                by_date[day] = row
        output = []
        for day in sessions:
            detail = by_date[day]['fields']['close']
            if detail.get('state') not in USABLE_STATES or not isinstance(detail.get('source'), str) or not detail['source'].strip():
                return None
            acquired = datetime.fromisoformat(detail['acquired_at'].replace('Z', '+00:00'))
            if acquired.tzinfo is None or not datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(hours=15) <= acquired <= now:
                return None
            value = Decimal(str(detail['value']))
            if not value.is_finite() or value <= 0:
                return None
            alternatives, omitted = _alternatives(detail, day, now) if detail['state'] == 'CONFLICT_NO_CONSENSUS' else ([], 0)
            output.append({'session': day, 'value': float(value), 'raw_value': str(value), 'source': detail['source'],
                           'acquired_at': detail['acquired_at'], 'source_sha256': detail.get('source_sha256'),
                           'state': detail['state'], 'provisional': detail['state'] == 'CONFLICT_NO_CONSENSUS',
                           'alternatives': alternatives, 'alternatives_omitted_unqualified': omitted})
        return output
    except (OSError, ValueError, TypeError, KeyError, InvalidOperation, OverflowError):
        return None


def _latest_retained_pair(folder, members, now, cutoff):
    """Choose the latest usable pair from one member, then align everyone.

    Unknown exchange calendars keep observed dates but are explicitly marked
    unverified; no absent session or quote is manufactured.
    """
    candidates = []
    for key in members:
        try:
            rows = json.loads((Path(folder)/'daily-cache'/(key+'.json')).read_text(encoding='utf-8'))['daily']['history']['rows']
        except (OSError, ValueError, TypeError, KeyError):
            continue
        days = set()
        for row in rows:
            try:
                day = row['session']
                if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day: continue
                if day <= cutoff: days.add(day)
            except (ValueError, TypeError, KeyError):
                continue
        days = sorted(days)
        for i in range(len(days)-1, 0, -1):
            first, last = days[i-1], days[i]
            next_known = next_session(first)
            if next_known and next_known != last:
                continue
            if _closes(folder, key, [first, last], now):
                candidates.append((last, first, next_known == last))
                break
    if not candidates:
        return None
    last, first, calendar_verified = max(candidates)
    return [first, last], calendar_verified


def sector_context(service, instrument, *, now=None):
    """Return one-sector breadth over an explicitly disclosed registered universe.

    Each member requires unambiguous qualified closes on both aligned JSE
    sessions. The ETF proxy and broad ETF reference are separate observations.
    Partial membership coverage is never described as a full-sector count.
    """
    now = now or service.clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware clock required')
    watch = service.store.get(instrument)
    expected = latest_expected_session(now)
    prior = _previous_session(expected) if expected else None
    result = {'state': 'UNAVAILABLE', 'instrument': instrument, 'as_of': now.isoformat(),
              'universe_version': UNIVERSE_VERSION, 'classification_version': VERSION,
              'universe_basis': 'CURRENT_REGISTERED_RESEARCH_CASH_GROUP_NOT_HISTORICAL_JSE_SECTOR',
              'sector': watch.get('sector') if watch else None, 'session': expected,
              'reference_session': prior, 'universe': [], 'qualified_members': [], 'provisional_members': [],
              'coverage': {'qualified': 0, 'total': 0}, 'breadth': None, 'provisional_breadth': None,
              'expected_session': expected, 'stale': None, 'calendar_verified': False,
              'sector_proxy': None, 'broad_benchmark': None, 'relative_percentage_points': None, 'relative_provisional': None,
              'limitations': ['HISTORICAL_CLOSES_NOT_LIVE', 'CURRENT_GROUPING_NOT_HISTORICAL_MEMBERSHIP']}
    if not watch or not result['sector']:
        return result
    mapping = mappings(service.root / 'runtime/local-swing-data/radar-public-prices')
    labels = classifications(mapping)['instruments']
    if instrument not in mapping or labels.get(instrument, {}).get('sector') != result['sector']:
        result['limitations'].append('INSTRUMENT_MAPPING_OR_SECTOR_MISMATCH')
        return result
    # Funds are not stock constituents; exact registered mapping is required.
    members = sorted(key for key in mapping if not key.startswith('ETF_') and
                     labels.get(key, {}).get('sector') == result['sector'] and result['sector'] != 'Funds')
    result['universe'] = members
    result['coverage']['total'] = len(members)
    cutoff = expected or (now.astimezone(timezone.utc).date() - timedelta(days=1)).isoformat()
    pair = _latest_retained_pair(service.folder, members, now, cutoff)
    if not pair:
        result['limitations'].append('ALIGNED_RETAINED_CLOSE_PAIR_UNAVAILABLE')
        return result
    sessions, calendar_verified = pair
    prior, session = sessions
    result.update(reference_session=prior, session=session, stale=(session != expected) if expected else None,
                  calendar_verified=calendar_verified and bool(expected))
    if not expected: result['limitations'].append('EXCHANGE_CALENDAR_UNVERIFIED')
    if not calendar_verified: result['limitations'].append('OBSERVED_SESSION_ADJACENCY_UNVERIFIED')
    if expected and session != expected: result['limitations'].append('STALE_HISTORICAL_SESSIONS')
    up = down = unchanged = 0
    usable_up = usable_down = usable_unchanged = 0
    for key in members:
        obs = _closes(service.folder, key, sessions, now)
        if not obs:
            continue
        delta = Decimal(obs[1]['raw_value']) - Decimal(obs[0]['raw_value'])
        usable_up += delta > 0
        usable_down += delta < 0
        usable_unchanged += delta == 0
        member = {'instrument': key, 'observations': obs}
        if any(item['provisional'] for item in obs):
            result['provisional_members'].append(member)
        else:
            up += delta > 0
            down += delta < 0
            unchanged += delta == 0
            result['qualified_members'].append(member)
    n = len(result['qualified_members'])
    result['coverage']['qualified'] = n
    p = len(result['provisional_members'])
    if p:
        result['coverage']['provisional'] = p
        result['provisional_breadth'] = {'advancers': usable_up, 'decliners': usable_down, 'unchanged': usable_unchanged,
                                          'basis': 'INCLUDES_ZEBRA_PRIORITY_CONFLICT_SELECTIONS_NOT_CONSENSUS'}
        result['limitations'].append('CONFLICTING_CLOSES_SELECTED_PROVISIONALLY')
    if n:
        result['breadth'] = {'advancers': up, 'decliners': down, 'unchanged': unchanged}
    if n or p:
        result['state'] = 'PROVISIONAL' if p else 'STALE' if result['stale'] else 'PARTIAL' if not result['calendar_verified'] or n != len(members) else 'COMPLETE'
    # ETF_STX40 is a generic fallback for sectors without a defined proxy;
    # presenting it as both sector performance and broad benchmark is false.
    proxy = watch.get('benchmark')
    for field, key in [('sector_proxy', proxy if proxy != 'ETF_STX40' else None), ('broad_benchmark', 'ETF_STX40')]:
        if not key:
            continue
        obs = _closes(service.folder, key, sessions, now)
        if obs:
            ret = (obs[1]['value'] / obs[0]['value'] - 1) * 100
            result[field] = {'instrument': key, 'return_percent': ret, 'observations': obs,
                             'provisional': any(item['provisional'] for item in obs),
                             'basis': 'ALIGNED_HISTORICAL_ETF_CLOSES_NOT_INDEX'}
    if result['sector_proxy'] and result['broad_benchmark']:
        result['relative_percentage_points'] = result['sector_proxy']['return_percent'] - result['broad_benchmark']['return_percent']
        result['relative_provisional'] = result['sector_proxy']['provisional'] or result['broad_benchmark']['provisional']
    return result
