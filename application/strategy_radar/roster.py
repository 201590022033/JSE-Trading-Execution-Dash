"""Durable work receipts for the existing explicitly enabled Radar worker."""
from datetime import timezone
from application.backtest_lab.learning_journal import LearningJournal
from .monitor import market_status


def enqueue(service, lane, *, instrument=None, request_id=None):
    import re
    if lane not in ('sens', 'backtester'):
        raise ValueError('unsupported submission lane')
    spec = {'lane': lane}
    if lane == 'backtester':
        if not isinstance(instrument, str) or not re.fullmatch(r'[A-Z0-9_]{2,16}', instrument):
            raise ValueError('canonical instrument required')
        if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', request_id):
            raise ValueError('explicit request identity required')
        spec.update(instrument=instrument, request_id=request_id)
    else:
        from datetime import datetime
        spec['slot'] = int(datetime.now(timezone.utc).timestamp()) // 300
    journal = LearningJournal(service.folder / 'work-roster.sqlite3')
    try: return journal.enqueue(spec)
    finally: journal.close()


def enqueue_exact(service, request):
    from application.backtest_lab.exact_run_job import EXACT_REQUEST, validate_request

    spec = validate_request(request, service)
    journal = LearningJournal(service.folder / 'work-roster.sqlite3')
    try:
        return journal.enqueue({**spec, 'lane': 'backtester', 'request_kind': EXACT_REQUEST})
    finally:
        journal.close()


def exact_status(service, identity):
    from contextlib import closing
    import json
    import sqlite3
    from application.backtest_lab.exact_run_job import EXACT_REQUEST

    path = (service.folder / 'work-roster.sqlite3').resolve()
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('SELECT spec,state,result FROM jobs WHERE id=?', (identity,)).fetchone()
    if row is None or json.loads(row[0]).get('request_kind') != EXACT_REQUEST:
        return None
    spec, state, result = row
    return {'job_id': identity, 'instrument': json.loads(spec)['instrument'],
            'state': state, **(json.loads(result) if result else {})}


def run_lane(service, lane, *, invoke=None):
    """Execute one retained-source or explicitly submitted deterministic job."""
    import subprocess
    import sys
    from pathlib import Path
    from scripts.local_runtime import process_lock
    root = Path(__file__).resolve().parents[2]
    if lane not in ('sens', 'backtester'): raise ValueError('unsupported lane')
    with process_lock(service.folder / (lane + '-roster.lock')):
        journal = LearningJournal(service.folder / 'work-roster.sqlite3')
        try:
            job = journal.claim_next(lane, max_attempts=1 if lane == 'backtester' else 3)
            if job is None: return {'state': 'IDLE'}
            if lane == 'backtester' and job['spec'].get('request_kind'):
                from application.backtest_lab.exact_run_job import RunUnavailable, run_job

                try:
                    result = {'run_id': run_job(service, job['spec']), 'model_calls_requested': 0}
                    state = 'COMPLETED'
                except RunUnavailable as exc:
                    state, result = 'FAILED', {'error': str(exc)}
                except Exception as exc:
                    state, result = 'FAILED', {'error': f'Saved-replay worker failed ({type(exc).__name__}).'}
                journal.finish(job['id'], state, result)
                return {'state': state, 'job_id': job['id'], **result}
            command = ([sys.executable, str(root/'scripts/sens_runtime_bridge.py'), 'tick'] if lane == 'sens' else
                       [sys.executable, str(root/'scripts/run_component_learning.py'),
                        '--instrument', job['spec']['instrument'], '--cycles', '1'])
            try:
                runner = invoke or subprocess.run
                completed = runner(command, cwd=root, capture_output=True, timeout=1800,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                result = {'returncode': completed.returncode, 'model_calls_requested': None if lane == 'sens' else 0}
                if lane == 'sens': result['model_call_accounting'] = 'SEE_MACRO_EXPECTATION_RECEIPTS'
                state = 'COMPLETED' if completed.returncode == 0 else 'FAILED'
            except Exception as exc:
                state, result = 'FAILED', {'error_type': type(exc).__name__}
            journal.finish(job['id'], state, result)
            return {'state': state, 'job_id': job['id'], **result}
        finally: journal.close()


def start_lane(service, lane):
    import subprocess
    import sys
    from pathlib import Path
    if lane not in ('sens', 'backtester'): raise ValueError('unsupported lane')
    root = Path(__file__).resolve().parents[2]
    subprocess.Popen([sys.executable, str(root/'scripts/work_roster_worker.py'), lane],
        cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), close_fds=True)


def collect_due(service, collector, now):
    """Run at most one current-slot export; preserve the existing market gate."""
    if market_status(now) != 'OPEN':
        return {'state': market_status(now), 'instruments': {}}
    watches = sorted(({'instrument': w['instrument'], **(
        {'benchmark': w['benchmark']} if w.get('benchmark') else {})}
        for w in service.store.radar_choices()), key=lambda w: w['instrument'])
    if not watches:
        return {'state': 'EMPTY_WATCHLIST', 'instruments': {}}
    slot = int(now.astimezone(timezone.utc).timestamp()) // 300
    journal = LearningJournal(service.folder / 'work-roster.sqlite3')
    try:
        identity = journal.enqueue({'lane': 'viewpoint', 'slot': slot, 'watches': watches})
        previous = journal.get(identity)
        if previous['state'] == 'COMPLETED':
            return previous['result']
        # Claim only this slot: obsolete five-minute jobs must not be exported.
        if previous['attempt'] >= 3 or previous['state'] == 'RUNNING':
            return {'state': previous['state'], 'instruments': {}, 'job_id': identity}
        if not journal.claim(identity):
            return {'state': 'ALREADY_CLAIMED', 'instruments': {}, 'job_id': identity}
        try:
            result = {**collector.collect(watches), 'job_id': identity}
            states = result.get('instruments', {})
            expected = {w['instrument'] for w in watches}
            expected.update(w['benchmark'] for w in watches if w.get('benchmark'))
            success = (result.get('state') == 'CHECKED' and all(
                states.get(key) in ('IMPORTED', 'ALREADY_RETAINED') for key in expected))
            journal.finish(identity, 'COMPLETED' if success else 'FAILED', result)
            # Collection has already been recorded: a context failure must not
            # discard successful imports or turn a healthy feed into a failure.
            imported = sorted(key for key, state in states.items() if state == 'IMPORTED')
            if imported:
                try:
                    prepared = service.prepare_context('VIEWPOINT_CSV_IMPORT')
                    result['prepared_context'] = {'state': prepared.get('state', 'UNKNOWN'),
                                                  'imported_instruments': imported}
                except Exception as exc:
                    result['prepared_context'] = {'state': 'UNAVAILABLE',
                                                  'error_type': type(exc).__name__,
                                                  'imported_instruments': imported}
            return result
        except Exception as exc:
            journal.finish(identity, 'FAILED', {'state': 'WORKER_FAILED', 'error_type': type(exc).__name__})
            raise
    finally:
        journal.close()


def status(service):
    path = service.folder / 'work-roster.sqlite3'
    if not path.exists():
        return {'jobs': [], 'state': 'NOT_STARTED'}
    import sqlite3
    import json
    from contextlib import closing
    with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT id,state,attempt,updated,spec,result FROM jobs ORDER BY updated DESC,id DESC LIMIT 50').fetchall()
    jobs = []
    for identity, state, attempt, updated, spec_json, result_json in rows:
        try:
            spec = json.loads(spec_json)
            result = json.loads(result_json) if result_json else {}
            if not isinstance(spec, dict) or not isinstance(result, dict):
                raise ValueError('invalid job')
        except (ValueError, TypeError):
            spec, result = {}, {}
        lane = spec.get('lane') if spec.get('lane') in ('viewpoint', 'sens', 'backtester') else 'legacy'
        limit = 1 if lane == 'backtester' else 3 if lane in ('sens', 'viewpoint') else None
        job = {'id': identity, 'state': state, 'attempt': attempt, 'updated': updated,
               'lane': lane, 'max_attempts': limit,
               'retry_available': state == 'FAILED' and limit is not None and attempt < limit}
        if lane == 'backtester':
            job['instrument'] = spec.get('instrument')
        if state == 'FAILED':
            job['error_type'] = result.get('error_type') or result.get('state')
            job['returncode'] = result.get('returncode')
        jobs.append(job)
    return {'state': 'AVAILABLE', 'jobs': jobs}
