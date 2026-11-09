"""Local-only watch orchestration; no broker or model calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from contextlib import closing
import json
import sqlite3
import os
from hashlib import sha256
from uuid import uuid4

from .daily import prewarm_daily, refresh_daily
from .watch_store import WatchStore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ('jse_swing_3_5d', '1.0.1')

class RadarService:
    def __init__(self, root=ROOT, *, prewarm=prewarm_daily, refresh=refresh_daily, clock=None, grace_sessions=2):
        if type(grace_sessions) is not int or not 0 <= grace_sessions <= 30:
            raise ValueError('grace_sessions must be between 0 and 30')
        self.grace_sessions = grace_sessions
        self.root = Path(root)
        self.folder = self.root / 'runtime/local-swing-data/strategy-radar'
        self.store = WatchStore(self.folder / 'watches.sqlite3')
        self.prewarm, self.refresh = prewarm, refresh
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='strategy-radar-daily')
        self.lock, self.prewarm_lock, self.reconcile_lock, self.running = Lock(), Lock(), Lock(), False
        with closing(self._db()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS radar_daily_job (id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL, result TEXT)")
            db.execute("UPDATE radar_daily_job SET state='QUEUED' WHERE state='RUNNING'")
            db.execute("CREATE TABLE IF NOT EXISTS radar_ranking_receipt (source_generated_at TEXT NOT NULL, observed_at TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL UNIQUE)")

    def _db(self):
        db = sqlite3.connect(self.folder / 'watches.sqlite3', timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def _queue(self, keys, now):
        with closing(self._db()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            for key in keys:
                pending = db.execute("SELECT 1 FROM radar_daily_job WHERE instrument=? AND state IN ('QUEUED','RUNNING')", (key,)).fetchone()
                if not pending:
                    db.execute("INSERT INTO radar_daily_job(instrument,created_at,state) VALUES(?,?,'QUEUED')", (key, now.isoformat()))

    def reconcile(self, snapshot, *, start_worker=True):
        with self.reconcile_lock:
            return self._reconcile_locked(snapshot, start_worker=start_worker)

    def _reconcile_locked(self, snapshot, *, start_worker):
        if not isinstance(snapshot, dict) or snapshot.get('schema') != 'zebra-research-screen-v1':
            raise ValueError('successful canonical snapshot required')
        rows = snapshot.get('opportunities')
        if not isinstance(rows, list) or not rows:
            raise ValueError('nonempty successful ranking required')
        now = self.clock()
        source_time = datetime.fromisoformat(snapshot['generated_at'].replace('Z', '+00:00'))
        if source_time.tzinfo is None or source_time.utcoffset() is None or source_time > now:
            raise ValueError('actual past source generation time required')
        source_time = source_time.astimezone(timezone.utc)
        fingerprint = sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        with closing(self._db()) as db:
            last = db.execute('SELECT source_generated_at,snapshot_sha256 FROM radar_ranking_receipt ORDER BY source_generated_at DESC LIMIT 1').fetchone()
            if last and (source_time < datetime.fromisoformat(last['source_generated_at']) or
                         (source_time == datetime.fromisoformat(last['source_generated_at']) and fingerprint != last['snapshot_sha256'])):
                raise ValueError('stale or conflicting canonical snapshot')
        previous = {x['instrument']: x for x in self.store.list_watches(include_archived=True)}
        from application.backtest_lab.zebra_field_windows import SECTOR_PROXY
        records = []
        for row in rows[:5]:
            key = row['research_key']
            old = previous.get(key, {})
            records.append({'instrument': key, 'strategy_id': old.get('strategy_id') or DEFAULT_PROFILE[0],
                'strategy_version': old.get('strategy_version') or DEFAULT_PROFILE[1],
                'sector': row.get('sector'), 'benchmark': old.get('benchmark') or SECTOR_PROXY.get(row.get('sector'), 'ETF_STX40')})
        watches = self.store.reconcile(records, now, grace_sessions=self.grace_sessions)
        self.prune_intraday()
        with closing(self._db()) as db, db:
            db.execute('INSERT OR IGNORE INTO radar_ranking_receipt VALUES(?,?,?)',
                       (source_time.isoformat(), now.isoformat(), fingerprint))
        try:
            self._save_prewarm([watch['instrument'] for watch in watches])
        except Exception:
            pass  # A damaged source must not prevent watch lifecycle or public refresh.
        entered = [r['instrument'] for r in records if not previous.get(r['instrument'], {}).get('in_top5')]
        with closing(self._db()) as db:
            missing = [r['instrument'] for r in records if not db.execute('SELECT 1 FROM radar_daily_job WHERE instrument=? LIMIT 1', (r['instrument'],)).fetchone()]
        self._queue(list(dict.fromkeys(entered + missing)), now)
        if start_worker and (entered or missing):
            self.start()
        return watches

    def prune_intraday(self, *, retention_sessions=10):
        from .intraday_store import IntradayCache
        watches = self.store.list_watches()
        active = [item['instrument'] for item in watches]
        pinned = [item['instrument'] for item in watches if item['pinned']]
        return IntradayCache(self.folder / 'intraday.sqlite3').prune(
            self.clock(), active, retention_sessions=retention_sessions, protected_instruments=pinned)

    def select(self, item, *, start_worker=True):
        from application.opportunities.zebra_instruments import mappings
        key = str(item.get('instrument', '')).strip().upper()
        mapping = mappings(self.root / 'runtime/local-swing-data/radar-public-prices')
        if key not in mapping:
            raise ValueError('select a registered instrument with an identity-checked mapping')
        from application.opportunities.research_classification import classifications
        sector = classifications([key])['instruments'][key]['sector']
        previous = self.store.get(key)
        now = self.clock()
        from application.backtest_lab.zebra_field_windows import SECTOR_PROXY
        record = {'instrument': key, 'sector': sector, 'benchmark': (previous or {}).get('benchmark') or SECTOR_PROXY.get(sector, 'ETF_STX40'),
                  'strategy_id': (previous or {}).get('strategy_id') or DEFAULT_PROFILE[0],
                  'strategy_version': (previous or {}).get('strategy_version') or DEFAULT_PROFILE[1]}
        watch = self.store.select(record, now)
        if not previous or previous['state'] == 'ARCHIVED':
            self._queue([key], now)
            if start_worker: self.start()
        return watch

    def set_pin(self, key, value):
        return self.store.set_flag(key, 'pinned', value, self.clock())

    def catalog(self):
        from application.opportunities.zebra_instruments import mappings
        return sorted(mappings(self.root / 'runtime/local-swing-data/radar-public-prices'))

    def _save_prewarm(self, keys):
        with self.prewarm_lock:
            return self._save_prewarm_locked(keys)

    def _save_prewarm_locked(self, keys):
        data = self.prewarm(keys, root=self.root, now=self.clock())
        folder = self.folder / 'daily-cache'
        folder.mkdir(parents=True, exist_ok=True)
        for key, value in data.get('watches', {}).items():
            raw = json.dumps({'as_of': data.get('as_of'), 'daily': value}, allow_nan=False).encode('utf-8')
            target = folder / (key + '.json')
            temp = folder / (key + '-' + uuid4().hex + '.tmp')
            try:
                temp.write_bytes(raw)
                os.replace(temp, target)
            finally:
                if temp.exists(): temp.unlink()
        return data

    def status(self, include_history=False):
        watches = self.store.list_watches()
        keys = [w['instrument'] for w in watches]
        cached, missing = {}, []
        for key in keys:
            try:
                item = json.loads((self.folder / 'daily-cache' / (key + '.json')).read_text(encoding='utf-8'))
                cached[key] = {**item['daily'], 'prewarmed_at': item.get('as_of')}
            except (OSError, ValueError, KeyError, TypeError):
                missing.append(key)
        data = self.prewarm(missing, root=self.root, now=self.clock())
        cached.update(data.get('watches', {}))
        with closing(self._db()) as db:
            ranking = db.execute('SELECT source_generated_at,observed_at,snapshot_sha256 FROM radar_ranking_receipt ORDER BY source_generated_at DESC LIMIT 1').fetchone()
            jobs = {}
            for key in keys:
                row = db.execute('SELECT state,created_at,result FROM radar_daily_job WHERE instrument=? ORDER BY id DESC LIMIT 1',(key,)).fetchone()
                if row:
                    jobs[key] = {'state': row['state'], 'requested_at': row['created_at'],
                                 'receipt': json.loads(row['result']) if row['result'] else None}
        for watch in watches:
            info = cached.get(watch['instrument'], {})
            watch['daily'] = info if include_history else {k:v for k,v in info.items() if k != 'history'}
            watch['refresh'] = jobs.get(watch['instrument'], {'state':'NOT_REQUESTED'})
        return {'watches': watches, 'ranking_receipt': dict(ranking) if ranking else None, 'prewarm_as_of': self.clock().isoformat(),
                'historical_not_quote': True, 'profile_basis':'DEFAULT_DAILY_RESEARCH_PROFILE',
                'live_execution':False}

    def start(self):
        with self.lock:
            if not self.running:
                self.running = True
                self.pool.submit(self._drain)

    def _drain(self):
        try:
            while True:
                with closing(self._db()) as db, db:
                    db.execute('BEGIN IMMEDIATE')
                    jobs = db.execute("SELECT id,instrument FROM radar_daily_job WHERE state='QUEUED' ORDER BY id LIMIT 5").fetchall()
                    if not jobs: break
                    db.executemany("UPDATE radar_daily_job SET state='RUNNING' WHERE id=?", [(r['id'],) for r in jobs])
                keys = [r['instrument'] for r in jobs]
                try:
                    try:
                        self._save_prewarm(keys)
                    except Exception:
                        pass  # Local read failure cannot suppress independent provider attempts.
                    result = self.refresh(keys, root=self.root)
                    try:
                        self._save_prewarm(keys)
                    except Exception:
                        pass  # Retain the previous cache and actual refresh receipt.
                    for job in jobs:
                        item = {'started_at': result['started_at'], 'finished_at': result['finished_at'],
                                'sources': result['results'].get(job['instrument'], {}), 'receipt': result['receipt']}
                        with closing(self._db()) as db, db:
                            db.execute("UPDATE radar_daily_job SET state='ATTEMPTED',result=? WHERE id=?", (json.dumps(item),job['id']))
                except Exception as exc:
                    with closing(self._db()) as db, db:
                        db.executemany("UPDATE radar_daily_job SET state='FAILED',result=? WHERE id=?", [(json.dumps({'error_type': type(exc).__name__}),r['id']) for r in jobs])
        finally:
            with self.lock:
                self.running = False
                with closing(self._db()) as db:
                    pending = db.execute("SELECT 1 FROM radar_daily_job WHERE state='QUEUED' LIMIT 1").fetchone()
                if pending:
                    self.running = True
                    self.pool.submit(self._drain)
