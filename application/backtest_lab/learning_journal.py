"""Durable local work queue and holdout ledger for research, never trading."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

class LearningJournal:
    def __init__(self,path):
        self.db=sqlite3.connect(str(path),timeout=30,isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL,
          attempt INTEGER NOT NULL DEFAULT 0, result TEXT, updated TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
          state TEXT NOT NULL, recorded TEXT NOT NULL, detail TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS holdout_looks (
          window_id TEXT PRIMARY KEY, candidate TEXT NOT NULL, recorded TEXT NOT NULL,
          result_hash TEXT, state TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS holdout_windows (
          window_id TEXT PRIMARY KEY, instrument TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL);''')
    def close(self):self.db.close()
    def _time(self):return datetime.now(timezone.utc).isoformat()
    def enqueue(self,spec):
        body=_canonical(spec); identity=sha256(body.encode()).hexdigest(); now=self._time()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            cur=self.db.execute('INSERT OR IGNORE INTO jobs(id,spec,state,updated) VALUES(?,?,?,?)',(identity,body,'QUEUED',now))
            if cur.rowcount:self.db.execute('INSERT INTO events(job_id,state,recorded,detail) VALUES(?,?,?,?)',(identity,'QUEUED',now,'{}'))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
        return identity
    def claim(self,identity,*,recover=False):
        now=self._time();self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT state FROM jobs WHERE id=?',(identity,)).fetchone()
            if row is None:raise KeyError('unknown job')
            allowed=('QUEUED','FAILED','RUNNING') if recover else ('QUEUED','FAILED')
            if row[0] not in allowed:self.db.execute('COMMIT');return False
            self.db.execute('UPDATE jobs SET state=?,attempt=attempt+1,updated=? WHERE id=?',('RUNNING',now,identity))
            self.db.execute('INSERT INTO events(job_id,state,recorded,detail) VALUES(?,?,?,?)',(identity,'RUNNING',now,_canonical({'recovered':row[0]=='RUNNING'})))
            self.db.execute('COMMIT');return True
        except BaseException:self.db.execute('ROLLBACK');raise
    def finish(self,identity,state,result):
        if state not in ('COMPLETED','FAILED'):raise ValueError('invalid completion state')
        body=_canonical(result);now=self._time();self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT state FROM jobs WHERE id=?',(identity,)).fetchone()
            if not row or row[0]!='RUNNING':raise ValueError('job must be running')
            self.db.execute('UPDATE jobs SET state=?,result=?,updated=? WHERE id=?',(state,body,now,identity))
            self.db.execute('INSERT INTO events(job_id,state,recorded,detail) VALUES(?,?,?,?)',(identity,state,now,body))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def get(self,identity):
        row=self.db.execute('SELECT spec,state,attempt,result FROM jobs WHERE id=?',(identity,)).fetchone()
        if row is None:raise KeyError('unknown job')
        return {'spec':json.loads(row[0]),'state':row[1],'attempt':row[2],'result':json.loads(row[3]) if row[3] else None}
    def jobs(self,instrument):
        result=[]
        for identity,spec,state,attempt in self.db.execute('SELECT id,spec,state,attempt FROM jobs ORDER BY updated'):
            value=json.loads(spec)
            if value.get('instrument')==instrument:result.append({'id':identity,'state':state,'attempt':attempt})
        return result
    def reserve_holdout(self,window_id,candidate,*,instrument=None,start=None,end=None):
        """Reserve before reading; an interrupted look still consumes its window."""
        if not window_id or not candidate:raise ValueError('window and frozen candidate required')
        if any(x is not None for x in (instrument,start,end)):
            from datetime import date
            if not all((instrument,start,end)) or date.fromisoformat(start)>date.fromisoformat(end):
                raise ValueError('ordered holdout interval required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if instrument:
                previous=self.db.execute('SELECT MAX(end) FROM holdout_windows WHERE instrument=?',(instrument,)).fetchone()[0]
                if previous and start<=previous:self.db.execute('COMMIT');return False
            cur=self.db.execute('INSERT OR IGNORE INTO holdout_looks(window_id,candidate,recorded,state) VALUES(?,?,?,?)',
                                (window_id,candidate,self._time(),'RESERVED'))
            if cur.rowcount and instrument:self.db.execute('INSERT INTO holdout_windows VALUES(?,?,?,?)',(window_id,instrument,start,end))
            self.db.execute('COMMIT');return bool(cur.rowcount)
        except BaseException:self.db.execute('ROLLBACK');raise
    def complete_holdout(self,window_id,candidate,result_hash):
        if len(result_hash)!=64 or any(x not in '0123456789abcdef' for x in result_hash):raise ValueError('result hash required')
        cur=self.db.execute('UPDATE holdout_looks SET state=?,result_hash=? WHERE window_id=? AND candidate=? AND state=?',
                            ('COMPLETED',result_hash,window_id,candidate,'RESERVED'))
        if cur.rowcount!=1:raise ValueError('matching unused reservation required')
    def holdout_status(self,instrument):
        row=self.db.execute('SELECT h.state,w.start,w.end,h.result_hash FROM holdout_windows w '
            'JOIN holdout_looks h ON h.window_id=w.window_id WHERE w.instrument=? ORDER BY w.end DESC LIMIT 1',
            (instrument,)).fetchone()
        return {'state':row[0],'start':row[1],'end':row[2],'result_hash':row[3]} if row else {'state':'UNOPENED'}
