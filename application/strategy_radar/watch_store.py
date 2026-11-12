"""Durable Strategy Radar watch lifecycle. No network or scheduling side effects.

Callers supply a successful canonical ranking snapshot; a failed read must never be
represented by an empty ranking. History is append-only. Dates outside the reviewed
JSE calendar conservatively retain grace watches.
"""
import json
import re
from contextlib import contextmanager
import sqlite3
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from application.opportunities.session_freshness import HOLIDAYS_2026


def _stamp(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('an aware observation time is required')
    return now.astimezone(timezone.utc).isoformat()


def _session_count(after, through):
    """Sessions strictly after departure through current date, or None if unknown."""
    from datetime import timedelta
    start, end = date.fromisoformat(after), date.fromisoformat(through)
    if start.year != 2026 or end.year != 2026:
        return None
    count = 0
    while start < end:
        start += timedelta(days=1)
        count += start.weekday() < 5 and start.isoformat() not in HOLIDAYS_2026
    return count


def _record(item):
    if not isinstance(item, dict):
        raise ValueError('watch item must be an object')
    instrument = str(item.get('instrument') or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,79}', instrument):
        raise ValueError('instrument required')
    def optional(key):
        value = item.get(key)
        return str(value).strip() if value is not None and str(value).strip() else None
    strategy_id, strategy_version = optional('strategy_id'), optional('strategy_version')
    if (strategy_id is None) != (strategy_version is None):
        raise ValueError('strategy id and version must be provided together')
    return {'instrument': instrument, 'strategy_id': strategy_id,
            'strategy_version': strategy_version, 'sector': optional('sector'),
            'benchmark': optional('benchmark')}


class WatchStore:
    """SQLite-backed watch state and immutable transition/decision history."""
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS radar_watch (
                  instrument TEXT PRIMARY KEY, strategy_id TEXT, strategy_version TEXT,
                  sector TEXT, benchmark TEXT, pinned INTEGER NOT NULL DEFAULT 0,
                  active INTEGER NOT NULL DEFAULT 0, in_top5 INTEGER NOT NULL DEFAULT 0,
                  rank INTEGER, departed_on TEXT, state TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS radar_watch_event (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, instrument TEXT NOT NULL,
                  occurred_at TEXT NOT NULL, kind TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS radar_watch_meta (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _event(db, instrument, timestamp, kind):
        row = dict(db.execute('SELECT * FROM radar_watch WHERE instrument=?', (instrument,)).fetchone())
        db.execute('INSERT INTO radar_watch_event(instrument,occurred_at,kind,snapshot) VALUES(?,?,?,?)',
                   (instrument, timestamp, kind, json.dumps(row, sort_keys=True)))

    def reconcile(self, items, now, grace_sessions=2):
        """Reconcile one successful ranking snapshot, up to five unique instruments.

        `now` is the actual aware snapshot time; no inferred source time is written.
        Empty is valid only if the caller has positively confirmed an empty ranking.
        """
        ts = _stamp(now)
        local_day = now.astimezone(timezone(timedelta(hours=2))).date().isoformat()
        if type(grace_sessions) is not int or grace_sessions < 0:
            raise ValueError('grace_sessions must be a nonnegative integer')
        records = [_record(item) for item in items]
        if len(records) > 5 or len({x['instrument'] for x in records}) != len(records):
            raise ValueError('ranking must contain at most five unique instruments')
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute("SELECT value FROM radar_watch_meta WHERE key='ranking_time'").fetchone()
            digest = json.dumps(records, sort_keys=True, separators=(',', ':'))
            if previous and datetime.fromisoformat(ts) < datetime.fromisoformat(previous['value']):
                raise ValueError('out-of-order ranking snapshot')
            if previous and ts == previous['value']:
                prior_digest = db.execute("SELECT value FROM radar_watch_meta WHERE key='ranking_snapshot'").fetchone()
                if prior_digest and prior_digest['value'] != digest:
                    raise ValueError('conflicting ranking at the same timestamp')
            selected = {r['instrument']: (rank, r) for rank, r in enumerate(records, 1)}
            for instrument, (rank, record) in selected.items():
                old = db.execute('SELECT * FROM radar_watch WHERE instrument=?', (instrument,)).fetchone()
                if old is None:
                    db.execute('''INSERT INTO radar_watch(instrument,strategy_id,strategy_version,sector,benchmark,
                        in_top5,rank,state,created_at,updated_at) VALUES(?,?,?,?,?,1,?,'WATCHING',?,?)''',
                        (instrument, record['strategy_id'], record['strategy_version'], record['sector'], record['benchmark'],rank,ts,ts))
                    self._event(db,instrument,ts,'ADDED_TOP5')
                else:
                    # A listing may omit metadata; never erase retained explicit choices.
                    values = [old[k] if k in ('strategy_id', 'strategy_version') and old[k] is not None else (record[k] if record[k] is not None else old[k]) for k in ('strategy_id','strategy_version','sector','benchmark')]
                    new = tuple(values) + (1, rank, None, 'WATCHING')
                    prior = tuple(old[k] for k in ('strategy_id','strategy_version','sector','benchmark','in_top5','rank','departed_on','state'))
                    if new != prior:
                        db.execute('''UPDATE radar_watch SET strategy_id=?,strategy_version=?,sector=?,benchmark=?,
                            in_top5=?,rank=?,departed_on=?,state=?,updated_at=? WHERE instrument=?''',(*new,ts,instrument))
                        self._event(db,instrument,ts,'TOP5_UPDATED')
            for old in db.execute('SELECT * FROM radar_watch WHERE in_top5=1').fetchall():
                instrument = old['instrument']
                if instrument not in selected:
                    state = 'WATCHING' if old['pinned'] or old['active'] else 'GRACE'
                    db.execute('UPDATE radar_watch SET in_top5=0,rank=NULL,departed_on=?,state=?,updated_at=? WHERE instrument=?',
                               (local_day,state,ts,instrument))
                    self._event(db,instrument,ts,'LEFT_TOP5')
            for old in db.execute("SELECT * FROM radar_watch WHERE in_top5=0 AND departed_on IS NOT NULL").fetchall():
                sessions = _session_count(old['departed_on'],local_day)
                state = ('WATCHING' if old['pinned'] or old['active'] else
                         'ARCHIVED' if sessions is not None and (grace_sessions == 0 or sessions > grace_sessions) else 'GRACE')
                if state != old['state']:
                    db.execute('UPDATE radar_watch SET state=?,updated_at=? WHERE instrument=?',(state,ts,old['instrument']))
                    self._event(db,old['instrument'],ts,'STATE_CHANGED')
            db.execute("INSERT INTO radar_watch_meta(key,value) VALUES('ranking_time',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (ts,))
            db.execute("INSERT INTO radar_watch_meta(key,value) VALUES('ranking_snapshot',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (digest,))
        return self.list_watches()

    def select(self, item, now, pinned=True):
        """Explicitly select a research contender; pin keeps it without ranking."""
        ts, record = _stamp(now), _record(item)
        if type(pinned) is not bool:
            raise ValueError('pinned must be boolean')
        if not pinned:
            raise ValueError('a newly selected contender must be pinned')
        instrument = record['instrument']
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM radar_watch WHERE instrument=?',(instrument,)).fetchone()
            if not (old and old['pinned']):
                other = db.execute('SELECT instrument FROM radar_watch WHERE pinned=1 AND instrument!=? LIMIT 1',
                                   (instrument,)).fetchone()
                if other:
                    raise ValueError(f"{other['instrument']} is already pinned; unpin it before selecting another contender")
            if old is None:
                db.execute('''INSERT INTO radar_watch(instrument,strategy_id,strategy_version,sector,benchmark,pinned,state,created_at,updated_at)
                    VALUES(?,?,?,?,?,1,'WATCHING',?,?)''', (instrument, record['strategy_id'], record['strategy_version'], record['sector'], record['benchmark'],ts,ts))
                self._event(db,instrument,ts,'SELECTED')
            else:
                values = [record[k] if record[k] is not None else old[k] for k in ('strategy_id','strategy_version','sector','benchmark')]
                if tuple(values)+(1,'WATCHING') != tuple(old[k] for k in ('strategy_id','strategy_version','sector','benchmark','pinned','state')):
                    db.execute('UPDATE radar_watch SET strategy_id=?,strategy_version=?,sector=?,benchmark=?,pinned=1,state=?,updated_at=? WHERE instrument=?',(*values,'WATCHING',ts,instrument))
                    self._event(db,instrument,ts,'SELECTED')
        return self.get(instrument)

    def set_flag(self, instrument, flag, value, now):
        if flag not in ('pinned','active') or type(value) is not bool:
            raise ValueError('invalid flag or value')
        ts = _stamp(now)
        instrument = str(instrument).strip().upper()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM radar_watch WHERE instrument=?',(instrument,)).fetchone()
            if old is None:
                raise KeyError(instrument)
            if flag == 'pinned' and value and not old['pinned']:
                other = db.execute('SELECT instrument FROM radar_watch WHERE pinned=1 AND instrument!=? LIMIT 1',
                                   (instrument,)).fetchone()
                if other:
                    raise ValueError(f"{other['instrument']} is already pinned; unpin it before pinning another watch")
            if old[flag] != value:
                # On release, keep a grace state until a ranking reconciliation evaluates expiry.
                pinned = value if flag == 'pinned' else old['pinned']
                active = value if flag == 'active' else old['active']
                state = 'WATCHING' if pinned or active or old['in_top5'] else 'GRACE'
                departed = old['departed_on']
                if state == 'GRACE' and departed is None:
                    departed = now.astimezone(timezone(timedelta(hours=2))).date().isoformat()
                db.execute(f'UPDATE radar_watch SET {flag}=?,state=?,departed_on=?,updated_at=? WHERE instrument=?',(int(value),state,departed,ts,instrument))
                self._event(db,instrument,ts,flag.upper() + '_CHANGED')
        return self.get(instrument)

    def get(self, instrument):
        with self._connect() as db:
            row = db.execute('SELECT * FROM radar_watch WHERE instrument=?',(instrument,)).fetchone()
            return dict(row) if row else None

    def list_watches(self, include_archived=False):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM radar_watch" + ('' if include_archived else " WHERE state!='ARCHIVED'") + ' ORDER BY in_top5 DESC,rank,instrument').fetchall()
            return [dict(row) for row in rows]

    def history(self, instrument=None):
        with self._connect() as db:
            rows = db.execute('SELECT * FROM radar_watch_event' + (' WHERE instrument=?' if instrument else '') + ' ORDER BY id', (instrument,) if instrument else ()).fetchall()
            return [dict(row, snapshot=json.loads(row['snapshot'])) for row in rows]
