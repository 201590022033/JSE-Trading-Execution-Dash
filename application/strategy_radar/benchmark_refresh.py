"""Resolve benchmark charts from local retained sources without provider calls.

If an on-disk daily cache is absent or stale, prewarm reads the local archive
into memory. This read path does not alter files or enqueue collection jobs.
"""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import math
import json
from datetime import date
from pathlib import Path
import re
from threading import Lock
from time import monotonic

from application.opportunities.session_freshness import latest_expected_session, next_session
from .swing_radar import _chart

_STATES = frozenset({'SINGLE_SOURCE', 'AGREEMENT', 'THREE_PROVIDER_AGREEMENT'})
_RESEARCH_STATES = _STATES | {'CONFLICT_NO_CONSENSUS'}
_FIELDS = ('open', 'high', 'low', 'close', 'volume')
_SUCCESS_TTL = 300.0
_FAILURE_TTL = 60.0
_MAX_ENTRIES = 64
_MAX_PENDING = 4
_lock = Lock()
_pending = set()
_memo = {}
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='radar-benchmark-local')


def _retained_target(key, daily, now, target):
    """Use the exact target's observed close history; never manufacture gaps.

    Only receipts available at evaluation are considered. Conflict candidates
    are the existing Zebra priority selections and are explicitly provisional.
    """
    try:
        if not isinstance(target, str) or date.fromisoformat(target).isoformat() != target: return None
        expected = latest_expected_session(now)
        cutoff = expected or (now.astimezone(timezone.utc).date() - timedelta(days=1)).isoformat()
        if target > cutoff: return None
        rows = daily['history']['rows']
        by_day, duplicates = {}, set()
        for row in rows:
            try:
                day = row['session']
                if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day: continue
                if day > target: continue
                if day in duplicates: continue
                if day in by_day:
                    by_day.pop(day); duplicates.add(day)
                else: by_day[day] = row
            except (TypeError, KeyError, ValueError):
                continue
        bars, evidence = [], []
        for day in sorted(by_day):
            detail = by_day[day].get('fields', {}).get('close', {})
            if not isinstance(detail, dict) or detail.get('state') not in _RESEARCH_STATES or not isinstance(detail.get('source'), str) or not detail['source'].strip():
                continue
            try:
                stamp = datetime.fromisoformat(detail['acquired_at'].replace('Z', '+00:00'))
                earliest = datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(hours=15)
                value = float(detail['value'])
                if stamp.tzinfo is None or stamp.utcoffset() is None or not earliest <= stamp <= now or not math.isfinite(value) or value <= 0:
                    continue
            except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
                continue
            alternatives, omitted = [], 0
            if detail['state'] == 'CONFLICT_NO_CONSENSUS':
                raw_alternatives = detail.get('alternatives', [])
                if not isinstance(raw_alternatives, list): raw_alternatives, omitted = [], 1
                for candidate in raw_alternatives:
                    try:
                        source = candidate['source']
                        amount = float(candidate['value'])
                        if not isinstance(source, str) or not source.strip() or not math.isfinite(amount) or amount <= 0:
                            raise ValueError('unqualified source or value')
                        received = datetime.fromisoformat(candidate['acquired_at'].replace('Z', '+00:00'))
                        if received.tzinfo is None or received.utcoffset() is None or not earliest <= received <= now:
                            raise ValueError('unqualified receipt')
                        alternatives.append(candidate)
                    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                        omitted += 1
            bars.append({'timestamp': day+'T00:00:00+00:00', 'close': value})
            evidence.append({'session': day, 'source': detail['source'], 'received_at': stamp.isoformat(),
                             'state': detail['state'], 'value': value, 'source_sha256': detail.get('source_sha256'),
                             'upstream_independence': detail.get('upstream_independence'),
                             'alternatives': alternatives, 'alternatives_omitted_unqualified': omitted})
        if not bars or bars[-1]['timestamp'][:10] != target: return None
        bars, evidence = bars[-100:], evidence[-100:]
        pairs = [(a['timestamp'][:10], b['timestamp'][:10]) for a,b in zip(bars,bars[1:])]
        gaps = [{'after': a, 'before': b, 'expected_next': next_session(a)} for a,b in pairs if next_session(a) != b]
        provisional = any(item['state'] == 'CONFLICT_NO_CONSENSUS' for item in evidence)
        quality = {'session': target, 'expected_session': expected, 'stale': target != expected if expected else None,
                   'calendar_unverified': expected is None, 'provisional': provisional,
                   'session_gaps_or_unknown_adjacency': gaps, 'ambiguous_sessions': sorted(duplicates),
                   'fields': evidence, 'limitation': 'Retained receipts as of evaluation; not a point-in-time backtest. Missing sessions are not filled.'}
        return {'symbol':key, 'interval':'1d', 'currency':'ZAR', 'bars':bars, 'data_quality':quality}
    except (OSError, KeyError, TypeError, ValueError, OverflowError):
        return None


def _target_status(chart, prefix):
    quality = chart['data_quality']
    parts = [prefix]
    if quality['calendar_unverified']: parts.append('CALENDAR_UNVERIFIED')
    elif quality['stale']: parts.append('STALE')
    if quality['provisional']: parts.append('PROVISIONAL')
    return '_'.join(parts)


def _from_daily(key, daily, now, target_session=None):
    if target_session is not None:
        return _retained_target(key, daily, now, target_session)
    try:
        expected = latest_expected_session(now)
        if not expected or daily['latest_session'] != expected:
            return None
        rows = daily['history']['rows'][-100:]
        if not rows or rows[-1]['session'] != expected or any(next_session(a['session']) != b['session'] for a,b in zip(rows,rows[1:])):
            return None
        bars = []
        for row in rows:
            day = row['session']
            bar = {'timestamp': day + 'T00:00:00+00:00'}
            for field in _FIELDS:
                # Benchmarks need closes; absent OHLCV fields must not become
                # invented bars or suppress otherwise qualified close history.
                detail = row.get('fields', {}).get(field, {})
                stamp = datetime.fromisoformat(detail['acquired_at'].replace('Z','+00:00')) if detail.get('acquired_at') else None
                if detail.get('state') in _STATES and stamp and stamp.tzinfo and datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(hours=15) <= stamp <= now and detail.get('value') is not None:
                    value = float(detail['value'])
                    if math.isfinite(value): bar[field] = value
            if 'close' not in bar or bar['close'] <= 0:
                return None
            bars.append(bar)
        return {'symbol': key, 'interval': '1d', 'currency': 'ZAR', 'bars': bars}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def resolve_benchmark_chart(service, instrument, *, now=None, target_session=None):
    """Resolve an exact-session research benchmark from retained data only.

    With a target session, preserve stale or conflicting Zebra selections as
    labelled historical/provisional research with source quality; never fill
    missing sessions or silently substitute a later session. The legacy path
    without a target retains its stricter current-cache behavior. Return a
    chart and a status that distinguishes cache, local reread and unavailability.
    """
    now = now or service.clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware time required')
    if not isinstance(instrument,str) or not re.fullmatch(r'ETF_[A-Z0-9]{2,12}', instrument):
        return None, 'INVALID_BENCHMARK'
    session = latest_expected_session(now)
    if not session and target_session is None:
        return None, 'CALENDAR_UNAVAILABLE'
    if target_session is not None:
        try:
            if not isinstance(target_session, str) or date.fromisoformat(target_session).isoformat() != target_session:
                return None, 'INVALID_TARGET_SESSION'
            cutoff = session or (now.astimezone(timezone.utc).date() - timedelta(days=1)).isoformat()
            if target_session > cutoff:
                return None, 'INVALID_TARGET_SESSION'
            daily = json.loads((Path(service.folder)/'daily-cache'/(instrument+'.json')).read_text(encoding='utf-8'))['daily']
            chart = _retained_target(instrument, daily, now, target_session)
            if chart: return chart, _target_status(chart, 'CACHE')
        except (OSError, TypeError, ValueError, KeyError):
            pass
    chart = _chart(service.folder, instrument, now) if target_session is None else None
    if chart and all(isinstance(b.get('close'), (float, int)) and math.isfinite(b['close']) and b['close'] > 0 for b in chart['bars']):
        return chart, 'CURRENT_CACHE'
    try:
        prewarm = service.prewarm
        root = Path(service.root).resolve()
    except (AttributeError, TypeError, OSError):
        return None, 'LOCAL_REFRESH_UNAVAILABLE'
    key = (str(root), instrument, session, target_session)
    tick = monotonic()
    with _lock:
        cached = _memo.get(key)
        if cached and cached[0] > tick and now >= cached[3]:
            return cached[1], cached[2]
        if cached:
            _memo.pop(key, None)
        if key in _pending:
            return None, 'LOCAL_REFRESH_PENDING'
        if len(_pending) >= _MAX_PENDING:
            return None, 'LOCAL_REFRESH_UNAVAILABLE'
        _pending.add(key)

    def refresh():
        try:
            data = prewarm([instrument], root=root, now=now)
            chart = _from_daily(instrument, data.get('watches', {}).get(instrument, {}), now, target_session)
            status = (_target_status(chart, 'LOCAL_REFRESH') if target_session is not None else 'LOCAL_REFRESH') if chart else 'LOCAL_REFRESH_UNAVAILABLE'
        except Exception:
            # A local source failure must not strand the pending slot or turn
            # an unavailable benchmark into an application error.
            chart, status = None, 'LOCAL_REFRESH_UNAVAILABLE'
        with _lock:
            _pending.discard(key)
            if len(_memo) >= _MAX_ENTRIES:
                _memo.pop(min(_memo, key=lambda item: _memo[item][0]), None)
            _memo[key] = (monotonic() + (_SUCCESS_TTL if chart else _FAILURE_TTL), chart, status, now)

    try:
        _executor.submit(refresh)
    except RuntimeError:
        with _lock:
            _pending.discard(key)
        return None, 'LOCAL_REFRESH_UNAVAILABLE'
    return None, 'LOCAL_REFRESH_PENDING'
