"""Acceptance-gated local PostgreSQL ingress and one existing worker cycle.

Stage configuration first; never creates a database or Windows task. After an
independently verified restore OR owner-authorized isolated fresh initialization,
supply the corresponding private acceptance receipt. Fresh start never claims
hosted ledger continuity or resets an existing account. Commands:
  python scripts/local_runtime.py ingest --dataset runtime/local-swing-data/latest.json
  python scripts/local_runtime.py worker
Both require loopback PostgreSQL 18, LOCAL learning and LOCAL_UPLOAD source.
Worker additionally requires the existing PAPER configuration and fresh aligned
whole-source IRESS/OST inputs. No network provider fallback or model activation
is introduced. Existing research/AI admission and daily attempt budgets apply.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def loopback(host):
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def configuration(env, receipt, now):
    from shadow_learning import timestamp
    url = env.get('DATABASE_URL', '')
    parsed = urlparse(url)
    if (parsed.scheme not in ('postgres', 'postgresql') or not loopback(parsed.hostname)
            or parsed.query or parsed.fragment or not parsed.path.strip('/')):
        raise ValueError('Explicit loopback PostgreSQL URL required')
    identity = {'host': parsed.hostname, 'port': parsed.port or 5432,
                'database': parsed.path.removeprefix('/')}
    if (receipt.get('state') != 'ACCEPTED'
            or receipt.get('database_identity') != identity
            or timestamp(receipt['verified_at']) > now):
        raise ValueError('Matching completed runtime acceptance required')
    if receipt.get('schema') == 'local-restore-acceptance-v1':
        hashes = ('source_backup_sha256', 'reconciliation_sha256')
    elif receipt.get('schema') == 'local-bootstrap-acceptance-v1':
        if (receipt.get('operation') != 'FRESH_START'
                or receipt.get('owner_reset_authorized') is not True
                or not isinstance(receipt.get('account_id'), str)
                or not re.fullmatch(r'local-[A-Za-z0-9_-]{1,100}', receipt['account_id'])
                or not isinstance(receipt.get('baseline_commit'), str)
                or not re.fullmatch('[0-9a-f]{7,40}', receipt['baseline_commit'])
                or 'source_backup_sha256' in receipt or 'reconciliation_sha256' in receipt):
            raise ValueError('Explicit isolated fresh-start acceptance required')
        hashes = ('initialization_manifest_sha256',)
        # The initial local lane is deterministic. Do not inherit any hosted
        # cloud/model/provider activation while establishing its new ledger.
        for key in ('SWING_RESEARCH_ENABLED', 'PAPER_NEWS_ENABLED',
                    'ALPHA_VANTAGE_ENABLED', 'PAPER_IG_SWING_DIAGNOSTICS', 'IG_STREAM_ENABLED'):
            if str(env.get(key, '')).strip() != '0':
                raise ValueError('Fresh runtime external research/provider switches must explicitly be off')
    else:
        raise ValueError('Known restore or fresh bootstrap acceptance required')
    for key in hashes:
        if not isinstance(receipt.get(key), str) or not re.fullmatch('[0-9a-f]{64}', receipt[key]):
            raise ValueError('Acceptance evidence hashes required')
    if env.get('SWING_LEARNING_SOURCE') != 'LOCAL' or env.get('SWING_DATA_SOURCE') != 'LOCAL_UPLOAD':
        raise ValueError('Explicit local learning and uploaded source required')
    return url, identity


def verify_database(url, identity):
    """Read-only identity check before repository composition can write anything."""
    import psycopg
    with psycopg.connect(url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SELECT current_database(), host(inet_server_addr()), inet_server_port(), current_setting('server_version_num')::int")
            name, address, port, version = cursor.fetchone()
    if name != identity['database'] or port != identity['port'] or not loopback(address) or not 180000 <= version < 190000:
        raise ValueError('Actual local PostgreSQL identity/version mismatch')


@contextmanager
def process_lock(path):
    """OS-owned lock releases on crash; the receipt file is not a stale PID lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            if path.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def validated_input(payload, now):
    from application.opportunities.ost_data import SCHEMA, POLICY
    from application.opportunities.swing_research import validate_dataset
    if payload.get('schema') != SCHEMA or payload.get('source_policy') != POLICY:
        raise ValueError('Whole-source OST v3 input required; no Yahoo fallback')
    return validate_dataset(payload, now)


def worker_ready(dataset, now):
    from shadow_learning import timestamp
    from application.opportunities.public_research import _available_at
    from application.opportunities.supplemental_data import current_research_charts
    validated_input(dataset, now)
    charts = current_research_charts(dataset, now)
    research = charts.get('SASOL')
    benchmark = charts.get('ETF_STX40')
    if not research or not benchmark or research['provenance']['provider'] != 'IRESS':
        raise ValueError('Fresh whole-source IRESS Sasol and OST benchmark required')
    latest = research['bars'][-1]
    if (latest['timestamp'] != benchmark['bars'][-1]['timestamp']
            or _available_at(latest['timestamp']) > now
            or latest.get('open') is None or latest['open'] <= 0
            or timestamp(dataset['observed_at']) > now):
        raise ValueError('Completed aligned sessions and actual Open required')


def execute(command, env, receipt, *, payload=None, now=None, factory=None, runner=None):
    now = now or datetime.now(timezone.utc)
    url, identity = configuration(env, receipt, now)
    verify_database(url, identity)
    from runtime_persistence import runtime_repository
    from application.opportunities.swing_research import accept_dataset, latest_dataset
    repository = (factory or runtime_repository)(database_url=url)
    try:
        if command == 'ingest':
            return accept_dataset(repository, validated_input(payload, now), now)
        if command != 'worker':
            raise ValueError('Unknown local operation')
        from application.opportunities.paper_host import configured_paper
        config = configured_paper()
        if not config or config.mode != 'PAPER':
            raise ValueError('Existing PAPER configuration required')
        if (receipt['schema'] == 'local-bootstrap-acceptance-v1'
                and config.account_id != receipt['account_id']):
            raise ValueError('Fresh account configuration must match accepted isolated identity')
        if repository.paper_account(config.account_id) is None:
            raise ValueError('Accepted existing PAPER account required; no second starting balance')
        worker_ready(latest_dataset(repository), now)
        from workers.heartbeat import run
        (runner or run)(repository=repository, scheduled=True)
        return {'state': 'LOCAL_BOUNDED_WORKER_FINISHED', 'live_execution': False}
    finally:
        repository.close()


def main():
    import argparse
    from ai_config import project_environment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('ingest', 'worker'))
    parser.add_argument('--receipt', type=Path, default=ROOT/'runtime/local-migration/restore-acceptance.json')
    parser.add_argument('--dataset', type=Path)
    args = parser.parse_args()
    env = project_environment()
    # Existing configuration readers use process environment. Never print values.
    os.environ.update(env)
    try:
        receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
        payload = json.loads(args.dataset.read_text(encoding='utf-8')) if args.dataset else None
        with process_lock(ROOT/'runtime/local-migration/runtime.lock'):
            result = execute(args.command, env, receipt, payload=payload)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({'state': 'LOCAL_RUNTIME_BLOCKED', 'failure_type': type(exc).__name__, 'live_execution': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
