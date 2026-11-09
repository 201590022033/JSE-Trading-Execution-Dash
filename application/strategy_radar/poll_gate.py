"""Persisted reservations for future, explicitly enabled provider polling."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

class PollGate:
    def __init__(self, path, *, minimum_seconds=300):
        if type(minimum_seconds) is not int or minimum_seconds < 300:
            raise ValueError('minimum interval is five minutes')
        self.path=str(path); self.minimum_seconds=minimum_seconds
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS poll_reservation (provider TEXT, instrument TEXT, reserved_at TEXT, PRIMARY KEY(provider,instrument))')
            db.execute('CREATE TABLE IF NOT EXISTS poll_budget (provider TEXT, utc_day TEXT, credits INTEGER NOT NULL, cap INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(provider,utc_day))')
            if 'cap' not in {row[1] for row in db.execute('PRAGMA table_info(poll_budget)')}:
                db.execute('ALTER TABLE poll_budget ADD COLUMN cap INTEGER NOT NULL DEFAULT 0')

    def reserve(self, provider, instrument, now, *, enabled=False, credit_cost=0, daily_limit=0):
        if enabled is not True: return {'allowed':False,'reason':'DISABLED'}
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,30}',provider or '') or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}',instrument or ''):
            raise ValueError('valid provider and instrument required')
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('aware clock required')
        if type(credit_cost) is not int or credit_cost < 0 or type(daily_limit) is not int or daily_limit < 0:
            raise ValueError('nonnegative credit budget required')
        now=now.astimezone(timezone.utc)
        with closing(sqlite3.connect(self.path,timeout=15)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT reserved_at FROM poll_reservation WHERE provider=? AND instrument=?',(provider,instrument)).fetchone()
            if row and (now-datetime.fromisoformat(row[0])).total_seconds() < self.minimum_seconds:
                return {'allowed':False,'reason':'RATE_LIMITED'}
            if credit_cost:
                budget=db.execute('SELECT credits,cap FROM poll_budget WHERE provider=? AND utc_day=?',(provider,now.date().isoformat())).fetchone()
                spent=budget[0] if budget else 0
                cap=min(daily_limit,budget[1]) if budget else daily_limit
                if spent+credit_cost>cap: return {'allowed':False,'reason':'BUDGET_EXHAUSTED'}
                db.execute('INSERT INTO poll_budget(provider,utc_day,credits,cap) VALUES(?,?,?,?) ON CONFLICT(provider,utc_day) DO UPDATE SET credits=credits+excluded.credits,cap=min(cap,excluded.cap)',(provider,now.date().isoformat(),credit_cost,cap))
            db.execute('INSERT INTO poll_reservation VALUES(?,?,?) ON CONFLICT(provider,instrument) DO UPDATE SET reserved_at=excluded.reserved_at',(provider,instrument,now.isoformat()))
        return {'allowed':True,'reserved_at':now.isoformat()}
