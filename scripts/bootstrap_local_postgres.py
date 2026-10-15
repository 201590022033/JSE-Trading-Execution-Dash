"""Create the owner's explicitly authorized isolated fresh PG18 research cluster.

Does not restore Railway, modify existing PostgreSQL services, start workers,
issue acceptance, or change dashboard configuration. Private files stay ignored.
"""
from pathlib import Path
import hashlib
import getpass
import json
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'runtime/local-migration/fresh-20261015'
BIN = Path('C:/Program Files/PostgreSQL/18/bin')
PORT = 55432
DATABASE = 'trading_local_20261015'
USER = 'trading_local'


def require_cluster(row, data):
    directory, version, address, port, user, listeners = row
    if (Path(directory).resolve() != data.resolve() or not 180000 <= int(version) < 190000
            or address != '127.0.0.1' or port != PORT or user != USER
            or listeners != '127.0.0.1'):
        raise ValueError('Connected server is not the isolated approved local cluster')


def main():
    import psycopg
    from psycopg import sql
    FOLDER.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        subprocess.run(['icacls', str(FOLDER), '/inheritance:r', '/grant:r',
                        getpass.getuser()+':(OI)(CI)F'], capture_output=True, check=True)
    private = FOLDER / 'private.json'
    data = FOLDER / 'pgdata'
    if private.exists():
        settings = json.loads(private.read_text())
        if (settings['port'] != PORT or settings['database'] != DATABASE
                or settings['user'] != USER or not settings.get('password')):
            raise ValueError('Existing private initialization identity differs')
    else:
        if data.exists():
            raise ValueError('Unrecorded existing cluster; inspect before continuing')
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(('127.0.0.1', PORT)) == 0:
                raise ValueError('Dedicated port already occupied')
        settings = {'port': PORT, 'database': DATABASE, 'user': USER,
                    'password': secrets.token_urlsafe(36)}
        with private.open('x') as stream:
            json.dump(settings, stream)
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    if not (data / 'PG_VERSION').exists():
        password_file = FOLDER / 'initialization-password.txt'
        password_file.write_text(settings['password'])
        try:
            result = subprocess.run([str(BIN/'initdb.exe'), '-D', str(data), '-U', USER,
                                     '--pwfile', str(password_file), '-A', 'scram-sha-256',
                                     '--encoding=UTF8', '--no-locale'],
                                    capture_output=True, creationflags=flags)
            (FOLDER/'initdb.log').write_bytes(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError('Cluster initialization failed; inspect private log')
        finally:
            password_file.unlink(missing_ok=True)
        with (data/'postgresql.conf').open('a') as stream:
            stream.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\n"
                         "shared_buffers = '128MB'\nwork_mem = '4MB'\nmax_connections = 30\n")
    status = subprocess.run([str(BIN/'pg_ctl.exe'), '-D', str(data), 'status'],
                            capture_output=True, creationflags=flags)
    if status.returncode:
        result = subprocess.run([str(BIN/'pg_ctl.exe'), '-D', str(data), '-l',
                                 str(FOLDER/'postgres.log'), '-w', 'start'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=flags)
        if result.returncode:
            raise RuntimeError('Cluster start failed; inspect private PostgreSQL log')
    params = dict(host='127.0.0.1', port=PORT, user=USER,
                  password=settings['password'], connect_timeout=5)
    with psycopg.connect(dbname='postgres', autocommit=True, **params) as connection:
        row = connection.execute("SELECT current_setting('data_directory'), "
                                 "current_setting('server_version_num'), host(inet_server_addr()), "
                                 "inet_server_port(), current_user, current_setting('listen_addresses')").fetchone()
        require_cluster(row, data)
        exists = connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (DATABASE,)).fetchone()
        if not exists:
            connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
    sys.path.insert(0, str(ROOT))
    from persistence.postgres_repository import PostgresRepository
    url = f"postgresql://{USER}:{settings['password']}@127.0.0.1:{PORT}/{DATABASE}"
    repository = PostgresRepository(url)
    try:
        repository.initialize()
    finally:
        repository.close()
    manifest = {'schema': 'local-fresh-initialization-v1', 'operation': 'FRESH_START',
                'database_identity': {'host': '127.0.0.1', 'port': PORT, 'database': DATABASE},
                'server_major_version': 18, 'hosted_history_restored': False,
                'account_id': 'local-paper-zar-20261015'}
    manifest_path = FOLDER/'initialization-manifest.json'
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if any(existing.get(key) != value for key, value in manifest.items()):
            raise ValueError('Existing initialization manifest identity differs')
    else:
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2))
    print(json.dumps({'state': 'ISOLATED_LOCAL_DATABASE_INITIALIZED',
                      'hosted_history_restored': False, 'worker_started': False,
                      'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'state': 'LOCAL_BOOTSTRAP_FAILED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
