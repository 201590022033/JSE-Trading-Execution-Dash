"""Read-only view of local model activity in the legacy research database."""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit, urlencode, urlunsplit, parse_qsl, quote

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_RADAR = 'anticipatory-radar-v1'
ACCOUNT_CALENDAR = 'calendar-ollama-runner-v1'


def _summary(item, fields):
    return {k: item[k] for k in fields if k in item} if item else None


def snapshot(repo, now, *, idle=None, memory=None):
    from scripts import calendar_ollama as runner
    as_of = now.isoformat()
    attempts = repo.paper_records(ACCOUNT_RADAR, 'radar-model-attempt', as_of=as_of, limit=1)
    results = repo.paper_records(ACCOUNT_RADAR, 'radar-model-result', as_of=as_of, limit=1)
    cal_attempts = repo.paper_records(ACCOUNT_CALENDAR, 'calendar-ollama-attempt', as_of=as_of, limit=1)
    cal_results = repo.paper_records(ACCOUNT_CALENDAR, 'calendar-ollama-result', as_of=as_of, limit=1)
    try:
        free = (memory or runner.available_memory_bytes)()
        idle_secs = (idle or runner.windows_idle_seconds)()
        calendar_gate = runner.CALENDAR_START_MEMORY
        checks = {'free_gib': round(free / runner.GIB, 2), 'idle_seconds': round(idle_secs, 1),
                  'qwen_minimum_gib': 3.5, 'calendar_minimum_gib': calendar_gate / runner.GIB,
                  'idle_required_seconds': runner.IDLE_SECONDS,
                  'qwen_memory_ready': free >= 7 * runner.GIB // 2,
                  'calendar_memory_ready': free >= calendar_gate,
                  'idle_ready': idle_secs >= runner.IDLE_SECONDS}
    except Exception:
        checks = {'state': 'RESOURCE_TELEMETRY_UNAVAILABLE'}
    fields = ('record_id', 'received_at', 'reserved_at', 'state', 'mode', 'model', 'model_digest',
              'model_calls', 'model_calls_upper_bound', 'error_type', 'request_started_at', 'request_completed_at')
    last_cal_attempt = cal_attempts[0] if cal_attempts else None
    pending = bool(last_cal_attempt and not repo.paper_record(last_cal_attempt['record_id'] + '-result'))
    return {'state': 'AVAILABLE', 'source_database': 'legacy research (localhost:55432)',
            'qwen': {'last_attempt': _summary(attempts[0] if attempts else None, fields),
                     'last_result': _summary(results[0] if results else None, fields)},
            'calendar': {'last_attempt': _summary(last_cal_attempt, fields),
                         'last_result': _summary(cal_results[0] if cal_results else None, fields),
                         'latest_attempt_unresolved': pending},
            'resources': checks, 'model_calls_on_read': 0,
            'interpretation': 'Recorded responses are not evidence of prediction accuracy.'}


def status(now=None):
    from runtime_persistence import runtime_repository
    now = now or datetime.now(timezone.utc)
    repo = None
    try:
        file = ROOT / 'runtime/local-migration/fresh-20261015/environment.json'
        url = json.loads(file.read_text(encoding='utf-8'))['DATABASE_URL']
        parsed = urlsplit(url)
        if parsed.scheme not in ('postgres', 'postgresql') or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.port != 55432 or parsed.path != '/trading_local_20261015':
            raise ValueError('Unexpected legacy database')
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params.update(options='-c default_transaction_read_only=on', connect_timeout='3')
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params, quote_via=quote), parsed.fragment))
        repo = runtime_repository(database_url=url)
        return snapshot(repo, now)
    except Exception:
        return {'state': 'LEGACY_ACTIVITY_UNAVAILABLE', 'source_database': 'legacy research (localhost:55432)',
                'model_calls_on_read': 0}
    finally:
        if repo is not None:
            repo.close()
