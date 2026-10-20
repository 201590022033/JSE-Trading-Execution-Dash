"""Explicit local outbox/receiver. Observations never dispatch trading or training."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3
import uuid

from application.release_inbox.protocol import plain_path
from jse_intelligence_core import ArtifactReference, ExecutionFeedback, StrategyRelease
from jse_intelligence_core.contracts import _instant
from jse_intelligence_core.feedback import PROVENANCES, identifier
from jse_intelligence_core.json_boundary import canonical, digest, exact, parse_json

APP_ID = 0x4A535235
TABLES = {'meta', 'profiles', 'releases', 'events', 'positions', 'batches', 'delivery_acks', 'delivery_positions'}


class FeedbackError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise FeedbackError(code)


def instant(value):
    return datetime.fromisoformat(_instant(value))


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def bounded(value):
    return parse_json(value if type(value) is bytes else canonical(value).encode())


class FeedbackJournal:
    def __init__(self, directory, *, producer_profiles, allow_test_feedback=False):
        need(type(allow_test_feedback) is bool, 'BOOLEAN_TEST_POLICY_REQUIRED')
        self.root = plain_path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root/'execution-feedback.sqlite3'
        self.allow_test = allow_test_feedback
        profiles = bounded(producer_profiles)
        need(type(profiles) is dict and 1 <= len(profiles) <= 32, 'PROFILES_REQUIRED')
        for producer, profile in profiles.items():
            identifier(producer)
            exact(profile, ('provenances', 'test_only'))
            need(type(profile['test_only']) is bool and type(profile['provenances']) is list
                 and 1 <= len(profile['provenances']) <= 3 and all(p in PROVENANCES for p in profile['provenances'])
                 and len(set(profile['provenances'])) == len(profile['provenances']), 'INVALID_PROFILE')
        self.profiles = profiles
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            app = con.execute('PRAGMA application_id').fetchone()[0]
            version = con.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if app == 0 and version == 0 and not tables:
                con.execute(f'PRAGMA application_id={APP_ID}')
                con.execute('PRAGMA user_version=1')
                con.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                con.execute('INSERT INTO meta VALUES (?,?)', ('stream_id', str(uuid.uuid4())))
                con.execute('CREATE TABLE profiles(producer TEXT PRIMARY KEY,body TEXT NOT NULL)')
                con.executemany('INSERT INTO profiles VALUES (?,?)', [(p, canonical(v)) for p,v in profiles.items()])
                con.execute('CREATE TABLE releases(release_id TEXT,package_id TEXT,body TEXT NOT NULL,test_only INTEGER NOT NULL,PRIMARY KEY(release_id,package_id))')
                con.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE NOT NULL,producer TEXT NOT NULL,producer_sequence INTEGER NOT NULL,event_hash TEXT NOT NULL,received_at TEXT NOT NULL,test_only INTEGER NOT NULL,body TEXT NOT NULL,correction_id TEXT UNIQUE,decision_root TEXT UNIQUE,UNIQUE(producer,producer_sequence))')
                con.execute('CREATE TABLE positions(stream TEXT,position INTEGER,event_id TEXT NOT NULL,event_hash TEXT NOT NULL,test_only INTEGER NOT NULL,PRIMARY KEY(stream,position))')
                con.execute('CREATE TABLE batches(batch_id TEXT PRIMARY KEY,body TEXT NOT NULL)')
                con.execute('CREATE TABLE delivery_acks(destination TEXT,batch_id TEXT,committed INTEGER NOT NULL,received_at TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(destination,batch_id))')
                con.execute('CREATE TABLE delivery_positions(destination TEXT,position INTEGER,event_hash TEXT NOT NULL,PRIMARY KEY(destination,position))')
                for table in TABLES:
                    for action in ('UPDATE', 'DELETE'):
                        con.execute(f"CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable feedback'); END")
            else:
                need(app == APP_ID and version == 1 and tables == TABLES, 'UNRECOGNIZED_FEEDBACK_STORE')
            persisted = {p: parse_json(b.encode()) for p,b in con.execute('SELECT producer,body FROM profiles')}
            need(persisted == profiles, 'PRODUCER_PROFILE_CHANGED')
            self.stream_id = con.execute("SELECT value FROM meta WHERE key='stream_id'").fetchone()[0]

    @contextmanager
    def _db(self):
        plain_path(self.root)
        for suffix in ('', '-journal', '-wal', '-shm'):
            path = plain_path(str(self.path)+suffix)
            need(not path.exists() or (path.is_file() and path.stat().st_nlink == 1), 'UNSAFE_FEEDBACK_STORE')
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            con.execute('PRAGMA synchronous=FULL')
            if hasattr(self, 'stream_id'):
                need(con.execute('PRAGMA application_id').fetchone()[0] == APP_ID
                     and con.execute('PRAGMA user_version').fetchone()[0] == 1, 'UNRECOGNIZED_FEEDBACK_STORE')
            with con:
                yield con
        finally:
            con.close()

    def register_release(self, manifest, *, package_id, test_only=False):
        manifest = StrategyRelease.from_dict(bounded(manifest))
        ArtifactReference(reference_id='package', content_hash=package_id)
        need(type(test_only) is bool, 'BOOLEAN_TEST_POLICY_REQUIRED')
        label = manifest.test_only or test_only
        need(not label or self.allow_test, 'TEST_FEEDBACK_DISABLED')
        body = manifest.canonical_json()
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT body,test_only FROM releases WHERE release_id=? AND package_id=?', (manifest.canonical_id,package_id)).fetchone()
            if old:
                need(old[0] == body and (old[1] or not label), 'RELEASE_LABEL_CONFLICT')
                need(not old[1] or self.allow_test, 'TEST_FEEDBACK_DISABLED')
            else:
                con.execute('INSERT INTO releases VALUES (?,?,?,?)', (manifest.canonical_id,package_id,body,int(label)))
        return dict(release_id=manifest.canonical_id, package_id=package_id, test_only=bool(old[1]) if old else label)

    def _append(self, con, value, now, forwarded_test=False):
        event = ExecutionFeedback.from_dict(value)
        need(instant(event.recorded_at) <= instant(now), 'FUTURE_FEEDBACK')
        need(event.producer_id in self.profiles, 'UNSUPPORTED_PRODUCER')
        profile = self.profiles[event.producer_id]
        need(event.provenance in profile['provenances'], 'UNSUPPORTED_PROVENANCE')
        row = con.execute('SELECT body,test_only FROM releases WHERE release_id=? AND package_id=?', (event.release_id,event.package_id)).fetchone()
        need(row is not None, 'UNKNOWN_RELEASE')
        manifest = StrategyRelease.from_json(row[0], expected_id=event.release_id)
        need(event.mapping in manifest.mappings and event.horizon == manifest.horizon, 'RELEASE_SCOPE_MISMATCH')
        need(instant(manifest.created_at) <= instant(event.observed_at), 'FEEDBACK_PRECEDES_RELEASE')
        need(all(r.as_of <= instant(event.observed_at).date().isoformat() for r in
                 (manifest.scope.universe,manifest.scope.exposures)), 'FEEDBACK_PRECEDES_SCOPE')
        if event.kind == 'DECISION' and event.occurrence.precision == 'exact':
            need(instant(manifest.created_at) <= instant(event.occurrence.value), 'FEEDBACK_PRECEDES_RELEASE')
        label = bool(row[1]) or profile['test_only'] or event.test_only or forwarded_test
        old = con.execute('SELECT event_hash,received_at,test_only FROM events WHERE event_id=?', (event.event_id,)).fetchone()
        if old:
            need(old[0] == event.canonical_id, 'EVENT_ID_COLLISION')
            need(old[2] or not label, 'TEST_LABEL_CONFLICT')
            label = label or bool(old[2])
        need(not label or self.allow_test, 'TEST_FEEDBACK_DISABLED')
        if not old:
            correction = event.correction_of.reference_id if event.correction_of else None
            root = event.producer_id+'|'+event.decision_id if event.kind == 'DECISION' and correction is None else None
            try:
                con.execute('INSERT INTO events(event_id,producer,producer_sequence,event_hash,received_at,test_only,body,correction_id,decision_root) VALUES (?,?,?,?,?,?,?,?,?)',
                    (event.event_id,event.producer_id,event.producer_sequence,event.canonical_id,now,int(label),event.canonical_json(),correction,root))
            except sqlite3.IntegrityError as exc:
                raise FeedbackError('SEQUENCE_ROOT_OR_CORRECTION_COLLISION') from exc
        return dict(schema_version='feedback-receipt/1', event_id=event.event_id, canonical_id=event.canonical_id,
                    received_at=old[1] if old else now, test_only=bool(label), state='STORED_NOT_AUTHORITY')

    def append(self, event):
        value = bounded(event.to_dict() if type(event) is ExecutionFeedback else event)
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            return self._append(con, value, utc_now())

    def export_batch(self, *, after_cursor=0, limit=100):
        need(type(after_cursor) is int and 0 <= after_cursor <= 2**53-1
             and type(limit) is int and 1 <= limit <= 100, 'BOUNDED_CURSOR_REQUIRED')
        with self._db() as con:
            maximum = con.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            need(after_cursor <= maximum, 'CURSOR_AHEAD')
            rows = con.execute('SELECT seq,body,event_hash,test_only FROM events WHERE seq>? ORDER BY seq LIMIT ?', (after_cursor,limit)).fetchall()
        body = dict(schema_version='execution-feedback-batch/1', stream_id=self.stream_id,
                    after_cursor=after_cursor, next_cursor=after_cursor, items=[])
        for seq,raw,event_hash,label in rows:
            need(not label or self.allow_test, 'TEST_FEEDBACK_DISABLED')
            event = ExecutionFeedback.from_json(raw, expected_id=event_hash)
            item = dict(cursor=seq, event=event.to_dict(), test_only=bool(label))
            proposed = {**body, 'items':body['items']+[item], 'next_cursor':seq}
            if len(canonical({**proposed,'batch_id':'sha256:'+'0'*64}).encode()) > 256*1024:
                break
            body = proposed
        need(not rows or body['items'], 'EVENT_TOO_LARGE_FOR_BATCH')
        return {**body, 'batch_id':digest(canonical(body).encode())}

    @staticmethod
    def _checkpoint(con, stream):
        cursor = 0
        for (position,) in con.execute('SELECT position FROM positions WHERE stream=? ORDER BY position', (stream,)):
            if position != cursor+1:
                break
            cursor = position
        return cursor

    def checkpoint(self, stream_id):
        with self._db() as con:
            return self._checkpoint(con, stream_id)

    def import_batch(self, batch):
        batch = bounded(batch)
        exact(batch, ('schema_version','stream_id','after_cursor','next_cursor','items','batch_id'))
        need(batch['schema_version'] == 'execution-feedback-batch/1', 'UNSUPPORTED_BATCH')
        try:
            need(str(uuid.UUID(batch['stream_id'])) == batch['stream_id'], 'INVALID_STREAM')
        except (ValueError, TypeError, AttributeError) as exc:
            raise FeedbackError('INVALID_STREAM') from exc
        body = {k:v for k,v in batch.items() if k != 'batch_id'}
        need(digest(canonical(body).encode()) == batch['batch_id'], 'BATCH_INTEGRITY')
        after, end, items = batch['after_cursor'], batch['next_cursor'], batch['items']
        need(type(after) is int and 0 <= after <= 2**53-1 and type(end) is int and 0 <= end <= 2**53-1
             and type(items) is list and len(items) <= 100 and end == after+len(items), 'INVALID_CURSOR_RANGE')
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute('SELECT body FROM batches WHERE batch_id=?', (batch['batch_id'],)).fetchone()
            if existing:
                ack = parse_json(existing[0].encode())
                need(self.allow_test or not any(r['test_only'] for r in ack['receipts']), 'TEST_FEEDBACK_DISABLED')
                return ack
            now, receipts = utc_now(), []
            for position,item in enumerate(items, after+1):
                exact(item, ('cursor','event','test_only'))
                need(type(item['cursor']) is int and item['cursor'] == position and type(item['test_only']) is bool, 'INVALID_ITEM')
                receipt = self._append(con, item['event'], now, item['test_only'])
                old = con.execute('SELECT event_id,event_hash,test_only FROM positions WHERE stream=? AND position=?', (batch['stream_id'],position)).fetchone()
                expected = (receipt['event_id'],receipt['canonical_id'],int(item['test_only']))
                if old:
                    need(old == expected, 'STREAM_POSITION_CONFLICT')
                else:
                    con.execute('INSERT INTO positions VALUES (?,?,?,?,?)', (batch['stream_id'],position,*expected))
                receipts.append(receipt)
            ack = dict(schema_version='feedback-batch-ack/1', batch_id=batch['batch_id'],stream_id=batch['stream_id'],
                       next_cursor=end, committed_through=self._checkpoint(con,batch['stream_id']), receipts=receipts,
                       received_at=now, state='STORED_NOT_SEMANTIC_APPROVAL')
            con.execute('INSERT INTO batches VALUES (?,?)', (batch['batch_id'],canonical(ack)))
            return ack

    def audit(self):
        with self._db() as con:
            rows = con.execute('SELECT event_hash,received_at,test_only,body FROM events ORDER BY seq LIMIT 10001').fetchall()
        need(len(rows) <= 10000, 'AUDIT_WINDOW_LIMIT')
        result = []
        for expected,received,label,raw in rows:
            need(not label or self.allow_test, 'TEST_FEEDBACK_DISABLED')
            event = ExecutionFeedback.from_json(raw, expected_id=expected)
            result.append(dict(event=event.to_dict(),canonical_id=expected,received_at=received,test_only=bool(label)))
        return result

    def acknowledge(self, destination_id, batch, ack):
        """Persist an explicitly supplied receiver acknowledgement; no sending."""
        identifier(destination_id)
        batch,ack = bounded(batch),bounded(ack)
        exact(batch, ('schema_version','stream_id','after_cursor','next_cursor','items','batch_id'))
        exact(ack, ('schema_version','batch_id','stream_id','next_cursor','committed_through','receipts','received_at','state'))
        need(batch['schema_version'] == 'execution-feedback-batch/1' and batch['stream_id'] == self.stream_id
             and batch['batch_id'] == digest(canonical({k:v for k,v in batch.items() if k != 'batch_id'}).encode()), 'ACK_BATCH_MISMATCH')
        need(ack['schema_version'] == 'feedback-batch-ack/1' and ack['state'] == 'STORED_NOT_SEMANTIC_APPROVAL'
             and all(ack[k] == batch[k] for k in ('batch_id','stream_id','next_cursor')), 'ACK_BATCH_MISMATCH')
        need(type(batch['after_cursor']) is int and batch['after_cursor'] >= 0
             and type(batch['items']) is list and len(batch['items']) <= 100
             and batch['next_cursor'] == batch['after_cursor']+len(batch['items'])
             and type(ack['receipts']) is list and len(ack['receipts']) == len(batch['items']), 'INVALID_ACK')
        now = utc_now()
        need(instant(ack['received_at']) <= instant(now), 'FUTURE_ACK')
        with self._db() as con:
            con.execute('BEGIN IMMEDIATE')
            maximum = con.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            need(type(ack['committed_through']) is int and 0 <= ack['committed_through'] <= maximum, 'INVALID_ACK_CHECKPOINT')
            for position,(item,receipt) in enumerate(zip(batch['items'],ack['receipts']),batch['after_cursor']+1):
                exact(item, ('cursor','event','test_only'))
                exact(receipt, ('schema_version','event_id','canonical_id','received_at','test_only','state'))
                local = con.execute('SELECT body,event_hash,test_only FROM events WHERE seq=?', (position,)).fetchone()
                need(local is not None and type(item['cursor']) is int and item['cursor'] == position
                     and canonical(item['event']) == local[0] and type(item['test_only']) is bool
                     and item['test_only'] == bool(local[2]), 'ACK_BATCH_MISMATCH')
                need(receipt['schema_version'] == 'feedback-receipt/1' and receipt['state'] == 'STORED_NOT_AUTHORITY'
                     and receipt['event_id'] == item['event']['event_id'] and receipt['canonical_id'] == local[1]
                     and type(receipt['test_only']) is bool and (receipt['test_only'] or not local[2]), 'INVALID_ACK_RECEIPT')
                need(not (receipt['test_only'] or local[2]) or self.allow_test, 'TEST_FEEDBACK_DISABLED')
                need(instant(receipt['received_at']) <= instant(ack['received_at']), 'INVALID_ACK_CLOCK')
                # Only exact verified receipts establish delivery. A receiver's
                # claimed checkpoint cannot attest to other unsent positions.
                con.execute('INSERT OR IGNORE INTO delivery_positions VALUES (?,?,?)',(destination_id,position,local[1]))
            raw = canonical(ack)
            old = con.execute('SELECT body,received_at FROM delivery_acks WHERE destination=? AND batch_id=?', (destination_id,batch['batch_id'])).fetchone()
            if old:
                need(old[0] == raw, 'ACK_COLLISION')
            else:
                con.execute('INSERT INTO delivery_acks VALUES (?,?,?,?,?)', (destination_id,batch['batch_id'],ack['committed_through'],now,raw))
            return dict(destination_id=destination_id,batch_id=batch['batch_id'],received_at=old[1] if old else now,
                        committed_through=ack['committed_through'],delivery_checkpoint=self._delivered(con,destination_id))

    @staticmethod
    def _delivered(con, destination_id):
        cursor = 0
        for (position,) in con.execute('SELECT position FROM delivery_positions WHERE destination=? ORDER BY position',(destination_id,)):
            if position != cursor+1:
                break
            cursor = position
        return cursor

    def delivery_checkpoint(self, destination_id):
        identifier(destination_id)
        with self._db() as con:
            return self._delivered(con,destination_id)

    def read_as_of(self, as_of, *, purpose='outcome'):
        need(purpose in ('decision','outcome'), 'EXPLICIT_READ_PURPOSE_REQUIRED')
        cutoff = instant(as_of)
        visible = {r['event']['event_id']:r for r in self.audit() if max(instant(r['received_at']),
                   instant(r['event']['recorded_at']),instant(r['event']['observed_at'])) <= cutoff}
        cache = {}
        def resolve(eid, stack=()):
            if eid in cache:
                return cache[eid]
            if eid not in visible:
                return ('PENDING_REFERENCE','MISSING_OR_NOT_YET_AVAILABLE')
            if eid in stack or len(stack) >= 64:
                return ('INVALID_REFERENCE','REFERENCE_CYCLE_OR_DEPTH')
            event = ExecutionFeedback.from_dict(visible[eid]['event'])
            try:
                for name in ('parent','correction_of'):
                    ref = getattr(event,name)
                    if ref is None:
                        continue
                    status,reason = resolve(ref.reference_id,(*stack,eid))
                    if status != 'AVAILABLE':
                        cache[eid]=(status,reason);return cache[eid]
                    target = ExecutionFeedback.from_dict(visible[ref.reference_id]['event'])
                    need(ref.content_hash == target.canonical_id, 'REFERENCE_HASH_MISMATCH')
                    need(all(getattr(event,k) == getattr(target,k) for k in
                         ('producer_id','release_id','package_id','mapping','horizon','decision_id','provenance')), 'REFERENCE_LINEAGE_MISMATCH')
                    need(target.producer_sequence < event.producer_sequence
                         and instant(target.observed_at) <= instant(event.observed_at), 'REFERENCE_CHRONOLOGY')
                    if name == 'correction_of':
                        need(event.kind == target.kind and event.parent == target.parent
                             and instant(target.recorded_at) <= instant(event.recorded_at), 'CORRECTION_LINEAGE_MISMATCH')
                    else:
                        allowed = {'RISK':('DECISION',),'ORDER':('RISK',),'FILL':('ORDER',),'COST':('FILL','EXIT'),'EXIT':('FILL',)}
                        need(target.kind in allowed[event.kind], 'PARENT_KIND_MISMATCH')
                        if target.kind == 'DECISION':need(target.data['status'] == 'INTENT', 'NO_SETUP_CANNOT_EXECUTE')
                        if target.kind == 'RISK':need(target.data['status'] in ('APPROVED','REDUCED'), 'REJECTED_RISK_CANNOT_EXECUTE')
                        if target.kind == 'ORDER':
                            need(target.data['status'] in ('PENDING','FILLED') and event.data['order_id'] == target.data['order_id'], 'ORDER_FILL_MISMATCH')
                        if target.kind in ('FILL','EXIT'):
                            need(event.data['currency'] == target.data['currency'], 'CURRENCY_MISMATCH')
                            if event.kind == 'EXIT':need(Decimal(event.data['quantity']) <= Decimal(target.data['quantity']), 'EXIT_QUANTITY_EXCEEDS_FILL')
                        if event.occurrence.precision == target.occurrence.precision == 'exact':
                            need(instant(target.occurrence.value) <= instant(event.occurrence.value), 'OCCURRENCE_BEFORE_PARENT')
                cache[eid]=('AVAILABLE',None)
            except FeedbackError as exc:
                cache[eid]=('INVALID_REFERENCE',str(exc))
            return cache[eid]
        for eid in visible:resolve(eid)
        superseded = {r['event']['correction_of']['reference_id'] for eid,r in visible.items()
                      if cache[eid][0] == 'AVAILABLE' and r['event']['correction_of'] is not None}
        records,unresolved = [],[]
        for eid,row in visible.items():
            state,reason = cache[eid]
            if state != 'AVAILABLE':
                if purpose == 'outcome' or row['event']['kind'] == 'DECISION':
                    unresolved.append(dict(event_id=eid,state=state,reason_code=reason))
            elif eid not in superseded and (purpose == 'outcome' or row['event']['kind'] == 'DECISION'):
                records.append(row)
        return dict(schema_version='feedback-as-of/1',as_of=_instant(as_of),purpose=purpose,
                    records=records,unresolved=unresolved,retraining=False,activation=False)
