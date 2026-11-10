"""Explicit, local-evidence-only Strategy Radar monitor. No providers or orders."""
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import json
import sqlite3
from .intraday_store import SAST, _session


def market_status(now):
    if now.tzinfo is None or now.utcoffset() is None: raise ValueError('aware time required')
    local=now.astimezone(SAST); session=_session(local.date())
    if session is None: return 'CALENDAR_UNVERIFIED'
    return 'OPEN' if session and time(9)<=local.time().replace(tzinfo=None)<time(17) else 'CLOSED'


class MonitorStore:
    def __init__(self,path):
        self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db,db:
            db.executescript('''CREATE TABLE IF NOT EXISTS monitor_config(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL DEFAULT 0,interval_seconds INTEGER NOT NULL DEFAULT 300,desktop INTEGER NOT NULL DEFAULT 0,last_check TEXT,last_status TEXT,last_error TEXT,lease_owner TEXT,lease_until TEXT);
            INSERT OR IGNORE INTO monitor_config(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS monitor_state(instrument TEXT PRIMARY KEY,eligible_state TEXT NOT NULL,observed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS monitor_events(id INTEGER PRIMARY KEY AUTOINCREMENT,instrument TEXT NOT NULL,state TEXT NOT NULL,observed_at TEXT NOT NULL,trace TEXT NOT NULL,desktop_status TEXT NOT NULL DEFAULT 'NOT_REQUESTED');''')
            if 'autostart' not in {row['name'] for row in db.execute('PRAGMA table_info(monitor_config)')}:
                db.execute('ALTER TABLE monitor_config ADD COLUMN autostart INTEGER NOT NULL DEFAULT 0')
            if 'profile' not in {row['name'] for row in db.execute('PRAGMA table_info(monitor_config)')}:
                db.execute("ALTER TABLE monitor_config ADD COLUMN profile TEXT NOT NULL DEFAULT 'intraday_5m_research_v1'")
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row;return db
    def config(self):
        with closing(self.connect()) as db: return dict(db.execute('SELECT * FROM monitor_config WHERE id=1').fetchone())
    def configure(self,enabled,interval_seconds,desktop,autostart=False,profile='intraday_5m_research_v1'):
        if profile not in ('intraday_5m_research_v1','intraday_30m_research_v1'): raise ValueError('unsupported profile')
        if type(autostart) is not bool or type(enabled) is not bool or type(desktop) is not bool or type(interval_seconds) is not int or not 60<=interval_seconds<=3600: raise ValueError('enabled/desktop booleans and interval 60–3600 seconds required')
        with closing(self.connect()) as db,db: db.execute('UPDATE monitor_config SET enabled=?,interval_seconds=?,desktop=?,autostart=?,profile=? WHERE id=1',(int(enabled),interval_seconds,int(desktop),int(autostart),profile))
    def claim(self,owner,now):
        ts=now.astimezone(timezone.utc); until=(ts+timedelta(minutes=3)).isoformat(); stamp=ts.isoformat()
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            cur=db.execute("UPDATE monitor_config SET lease_owner=?,lease_until=? WHERE id=1 AND enabled=1 AND (lease_owner IS NULL OR lease_owner=? OR lease_until<?)",(owner,until,owner,stamp))
            return cur.rowcount==1
    def release(self,owner):
        with closing(self.connect()) as db,db: db.execute('UPDATE monitor_config SET lease_owner=NULL,lease_until=NULL WHERE id=1 AND lease_owner=?',(owner,))
    def status(self,now,state,error=None):
        with closing(self.connect()) as db,db: db.execute('UPDATE monitor_config SET last_check=?,last_status=?,last_error=? WHERE id=1',(now.astimezone(timezone.utc).isoformat(),state,error))
    def record(self,instrument,evaluation,now):
        state=evaluation['state']; stamp=now.astimezone(timezone.utc).isoformat()
        if state not in ('WATCHING','DEVELOPING','ENTRY_MET','UNKNOWN'): raise ValueError('invalid state')
        # Unknown/source loss is health information and never rearms an alert.
        if state=='UNKNOWN': return None
        trace=json.dumps(evaluation,sort_keys=True,separators=(',',':'),allow_nan=False)
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            config=db.execute('SELECT enabled,profile FROM monitor_config WHERE id=1').fetchone()
            evaluation_profile=evaluation.get('strategy_id','intraday_5m_research_v1')
            if not config['enabled'] or config['profile']!=evaluation_profile: return None
            state_key=instrument+'|'+evaluation_profile
            old=db.execute('SELECT eligible_state FROM monitor_state WHERE instrument=?',(state_key,)).fetchone()
            previous=old['eligible_state'] if old else None
            db.execute('INSERT INTO monitor_state VALUES(?,?,?) ON CONFLICT(instrument) DO UPDATE SET eligible_state=excluded.eligible_state,observed_at=excluded.observed_at',(state_key,state,stamp))
            if state in ('DEVELOPING','ENTRY_MET') and state!=previous:
                cur=db.execute('INSERT INTO monitor_events(instrument,state,observed_at,trace) VALUES(?,?,?,?)',(instrument,state,stamp,trace)); return cur.lastrowid
        return None
    def mark_desktop(self,event_id,state):
        with closing(self.connect()) as db,db: db.execute('UPDATE monitor_events SET desktop_status=? WHERE id=?',(state,event_id))
    def events(self,limit=100):
        with closing(self.connect()) as db:
            return [dict(row,trace=json.loads(row['trace'])) for row in db.execute('SELECT * FROM monitor_events ORDER BY id DESC LIMIT ?', (limit,))]


def check_once(store,service,now,*,evaluator=None,notifier=None):
    configuration=store.config()
    if not configuration['enabled']:
        store.status(now,'PAUSED'); return 'PAUSED'
    profile=configuration['profile']
    session=market_status(now)
    if session!='OPEN': store.status(now,session); return session
    if evaluator is None:
        from .shadow_service import evaluate_watch
        evaluator=lambda instrument: evaluate_watch(service,instrument,profile,now=now)
    try:
        watches=service.store.list_watches()
        if not watches: store.status(now,'EMPTY_WATCHLIST'); return 'EMPTY_WATCHLIST'
        unknown=0; errors=0
        for watch in watches:
            if not store.config()['enabled']:
                store.status(now,'PAUSED'); return 'PAUSED'
            try: evaluation=evaluator(watch['instrument'])
            except Exception:
                errors+=1; continue
            current=store.config()
            if not current['enabled']:
                store.status(now,'PAUSED'); return 'PAUSED'
            if current['profile']!=profile:
                store.status(now,'CONFIG_CHANGED'); return 'CONFIG_CHANGED'
            if evaluation['state']=='UNKNOWN': unknown+=1
            event_id=store.record(watch['instrument'],evaluation,now)
            if event_id:
                current=store.config()
                if not current['enabled'] or current['profile']!=profile:
                    store.mark_desktop(event_id,'SUPPRESSED_CONFIG_CHANGED')
                    state='PAUSED' if not current['enabled'] else 'CONFIG_CHANGED'
                    store.status(now,state)
                    return state
                elif current['desktop']:
                    try: result='UNAVAILABLE' if notifier is None else notifier(watch['instrument'],evaluation['state'])
                    except Exception: result='WINDOWS_NOTIFICATION_FAILED'
                    store.mark_desktop(event_id,result)
        state='ERROR' if errors==len(watches) else 'SOURCE_UNAVAILABLE' if unknown==len(watches) else 'PARTIAL_SOURCE' if unknown or errors else 'CHECKED'
        store.status(now,state,'WATCH_EVALUATION_FAILED' if errors else None); return state
    except Exception as exc:
        store.status(now,'ERROR',type(exc).__name__); return 'ERROR'
