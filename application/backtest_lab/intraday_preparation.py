"""Explicit single-session preparation via the installed ViewPoint request queue."""
from contextlib import closing
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import sqlite3
from time import monotonic

from application.opportunities.ost_data import atomic_json
from application.opportunities.session_freshness import latest_expected_session, SAST
from application.strategy_radar.intraday_store import normalize_bar, VIEWPOINT_SOURCE, _session, _time
from scripts.local_runtime import process_lock

from .exact_run_job import RunUnavailable, replay_instruments


def target(service, instrument, session):
    symbol = next((row['symbol'] for row in replay_instruments(service.root) if row['instrument'] == instrument), None)
    latest = latest_expected_session(service.clock())
    try:
        day = date.fromisoformat(session)
        if day.isoformat() != session or _session(day) is not True or latest is None or session > latest:
            raise ValueError
    except (TypeError, ValueError):
        raise RunUnavailable('Choose a completed session in the reviewed JSE calendar.') from None
    if not symbol:
        raise RunUnavailable('Select a recognized ViewPoint cash-share symbol.')
    return dict(instrument=instrument, session=session, symbol=f'{symbol}.JSE',
                interval_minutes=5, expected_bars=96, latest_completed=latest)


def coverage(records, request, now):
    starts = set()
    for record in records:
        try:
            bar = normalize_bar(record)
            if (bar['instrument'] != request['instrument'] or bar['source'] != VIEWPOINT_SOURCE
                    or bar['interval_minutes'] != 5 or not bar['interval_verified'] or bar['provisional']
                    or _time(bar['received_at']) > now or any(value is None for value in bar['fields'].values())):
                continue
            start = _time(bar['bar_start']).astimezone(SAST)
            if start.date().isoformat() == request['session']:
                starts.add(start)
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return len(starts)


def _retained(service, request):
    path = (service.folder / 'intraday.sqlite3').resolve()
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT payload FROM bars WHERE instrument=? AND session=?',
                          (request['instrument'], request['session'])).fetchall()
    return [json.loads(row[0]) for row in rows]


def _paths(service, request):
    identity = sha256(f"lab-5m-v1:{request['instrument']}:{request['session']}".encode()).hexdigest()[:32]
    pending = service.folder / 'viewpoint-requests' / f'{identity}.json'
    return pending, pending.with_suffix('.result'), pending.with_name(f'{pending.stem}-lab.progress')


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _heartbeat(pending):
    try:
        return 0 <= monotonic() - float((pending.parent / 'heartbeat').read_text()) <= 120
    except (OSError, ValueError):
        return False


def status(service, request, *, read_records=_retained):
    pending, receipt, progress = _paths(service, request)
    count = coverage(read_records(service, request), request, service.clock())
    result = _read(receipt)
    stage = _read(progress).get('state')
    command = _read(pending)
    if count == request['expected_bars']:
        state = 'READY'
    elif result:
        evidence = result.get('instruments', {}).get(request['instrument'])
        if evidence in ('IMPORTED', 'ALREADY_RETAINED'):
            state = 'PARTIAL_EXPORT'
        elif result.get('state') == 'OST_SIGN_IN_OR_CHART_SETUP_REQUIRED':
            state = 'SIGN_IN_REQUIRED'
        else:
            state = 'EXPORT_UNAVAILABLE'
    elif command and 'requested_at' in command:
        age = (service.clock() - _time(command['requested_at'])).total_seconds()
        state = (stage if stage in ('DOWNLOADING', 'IMPORTING') else 'PENDING_DOWNLOAD') if age < 150 else 'REQUEST_TIMED_OUT'
    elif request['session'] != request['latest_completed']:
        state = 'UNSUPPORTED_HISTORICAL_WINDOW'
    else:
        state = 'MISSING'
    return dict(request, state=state, imported_bars=count, collector_receipt=result)


def submit(service, request, *, retry=False, read_records=_retained):
    current = status(service, request, read_records=read_records)
    retryable = {'PARTIAL_EXPORT', 'SIGN_IN_REQUIRED', 'EXPORT_UNAVAILABLE'}
    if current['state'] not in ({'MISSING'} | (retryable if retry else set())):
        return current
    if request['session'] != request['latest_completed']:
        return {**current, 'state': 'UNSUPPORTED_HISTORICAL_WINDOW'}
    pending, receipt, progress = _paths(service, request)
    if not _heartbeat(pending):
        return {**current, 'state': 'COLLECTOR_NOT_CONNECTED'}
    with process_lock(pending.with_suffix('.lab-lock')):
        current = status(service, request, read_records=read_records)
        if current['state'] not in ({'MISSING'} | (retryable if retry else set())):
            return current
        # Remove the command before its receipt so the collector cannot replay it.
        pending.unlink(missing_ok=True)
        receipt.unlink(missing_ok=True)
        progress.unlink(missing_ok=True)
        atomic_json(pending, {'watches': [{'instrument': request['instrument']}],
                              'lab_session': request['session'], 'requested_at': service.clock().isoformat()})
    return status(service, request, read_records=read_records)


def manual(service, request, raw, name, *, save):
    from application.strategy_radar.intraday_adapters import viewpoint_table_csv
    from application.strategy_radar.intraday_store import IntradayCache
    from application.strategy_radar.viewpoint_inbox import _EXPORT

    match = _EXPORT.fullmatch(name)
    if not match or f'{match[1].upper()}.JSE' != request['symbol']:
        raise RunUnavailable(f"Keep the native ViewPoint export filename for {request['symbol']}.")
    now = service.clock()
    rows = viewpoint_table_csv(raw, request['instrument'], request['symbol'], now, file_name=name,
                               interval_minutes=5, accept_operator_conventions=True)
    selected = [row for row in rows if _time(row['bar_start']).astimezone(SAST).date().isoformat()
                == request['session']]
    if not selected:
        raise RunUnavailable('The file has no five-minute rows for the requested session.')
    starts = sorted(_time(row['bar_start']) for row in selected)
    if not any(b - a == timedelta(minutes=5) for a, b in zip(starts, starts[1:])):
        raise RunUnavailable('The requested session must contain at least two consecutive five-minute timestamps.')
    count = coverage(selected, request, now)
    if save:
        if not count:
            raise RunUnavailable('The file contains no complete OHLCV bars for the requested session.')
        IntradayCache(service.folder / 'intraday.sqlite3').put_batch(selected, raw, evidence=True)
        report = status(service, request)
        return report if report['state'] == 'READY' else {**report, 'state': 'PARTIAL_EXPORT'}
    return dict(request, state='VALIDATED_FILE', file_rows=len(rows), validated_bars=count,
                missing_bars=request['expected_bars'] - count, source_sha256=sha256(raw).hexdigest())
