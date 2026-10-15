"""Private fresh-PC launcher; no secrets in process arguments or command output.

dashboard: start the existing loopback app. cycle: ingest and one guarded PAPER
cycle (Windows task should require 10 minutes idle). start-db: only start the
already initialized isolated cluster, never initialize/migrate on startup.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import hashlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'runtime/local-migration/fresh-20261015'
sys.path.insert(0, str(ROOT))


def start_database():
    from scripts.bootstrap_local_postgres import BIN, require_cluster
    import psycopg
    settings = json.loads((FOLDER/'private.json').read_text())
    data = FOLDER/'pgdata'
    if not (data/'PG_VERSION').exists():
        raise ValueError('Explicit isolated initialization required before startup')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    result = subprocess.run([str(BIN/'pg_ctl.exe'), '-D', str(data), 'status'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags, timeout=15)
    if result.returncode:
        subprocess.run([str(BIN/'pg_ctl.exe'), '-D', str(data), '-l',
                        str(FOLDER/'postgres.log'), '-w', 'start'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=flags, timeout=45, check=True)
    with psycopg.connect(host='127.0.0.1', port=settings['port'], dbname='postgres',
                         user=settings['user'], password=settings['password'], connect_timeout=5) as conn:
        row = conn.execute("SELECT current_setting('data_directory'), current_setting('server_version_num'), "
                           "host(inet_server_addr()), inet_server_port(), current_user, "
                           "current_setting('listen_addresses')").fetchone()
        require_cluster(row, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['dashboard', 'cycle', 'start-db', 'backup'])
    args = parser.parse_args()
    from ai_config import project_environment
    env = project_environment()
    env.update(json.loads((FOLDER/'environment.json').read_text()))
    start_database()
    if args.command == 'start-db':
        return 0
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if args.command == 'backup':
        from scripts.bootstrap_local_postgres import BIN
        from scripts.local_runtime import process_lock
        with process_lock(FOLDER/'backup.lock'):
            settings = json.loads((FOLDER/'private.json').read_text())
            backup_env = env.copy()
            backup_env['PGPASSWORD'] = settings['password']
            backup_env['PGCONNECT_TIMEOUT'] = '5'
            backup = FOLDER/('local-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump')
            staged = backup.with_suffix('.partial')
            subprocess.run([str(BIN/'pg_dump.exe'), '-h', '127.0.0.1', '-p', str(settings['port']),
                            '-U', settings['user'], '-d', settings['database'], '-Fc', '-f', str(staged)],
                           env=backup_env, creationflags=flags,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=600)
            staged.replace(backup)
            receipt = {'scope': 'FRESH_LOCAL_LEDGER_ONLY', 'hosted_history_restored': False,
                       'bytes': backup.stat().st_size, 'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()}
            backup.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2))
        return 0
    if args.command == 'dashboard':
        import socket
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(('127.0.0.1', 5000)) == 0:
                raise ValueError('Occupied dashboard port requires runtime identity verification')
        with (FOLDER/'dashboard.stdout.log').open('ab') as out, (FOLDER/'dashboard.stderr.log').open('ab') as err:
            process = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT, env=env,
                                       stdout=out, stderr=err, creationflags=flags)
        print(json.dumps({'state': 'LOCAL_DASHBOARD_STARTED', 'process_id': process.pid}))
        return 0
    from scripts.local_runtime import process_lock
    with process_lock(FOLDER/'cycle.lock'):
        common = [sys.executable, 'scripts/local_runtime.py']
        receipt = str(FOLDER/'bootstrap-acceptance.json')
        flags |= getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
        with (FOLDER/'cycle.log').open('ab') as log:
            for arguments in [('ingest', '--dataset', 'runtime/local-swing-data/latest.json'), ('worker',)]:
                result = subprocess.run(common+list(arguments)+['--receipt', receipt],
                                        cwd=ROOT, env=env, creationflags=flags,
                                        stdout=log, stderr=log)
                if result.returncode:
                    return result.returncode
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'state': 'LOCAL_PC_OPERATION_BLOCKED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
