"""Intraday research records, provenance-preserving merge and bounded local cache.

No provider access. Canonical interval boundaries require an established source
clock convention. The reviewed JSE holiday calendar currently covers 2026 only.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from application.opportunities.session_freshness import HOLIDAYS_2026

SAST = timezone(timedelta(hours=2))
FIELDS = ('open', 'high', 'low', 'close', 'volume')
AVAILABILITY = {'LIVE', 'DELAYED', 'MANUAL', 'STALE', 'HISTORICAL', 'UNKNOWN'}
VIEWPOINT_SOURCE = 'IRESS_VIEWPOINT_TABLE_CSV'


def _time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def _session(day):
    if day.year != 2026:
        return None
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS_2026


def _value(value, field, unit):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = Decimal(str(value))
        if not n.is_finite() or (n < 0 if field == 'volume' else n <= 0):
            return None
        if field != 'volume' and unit == 'ZAR_CENTS':
            n /= 100
        return str(n)
    except (InvalidOperation, ValueError):
        return None


def _is_viewpoint_source(source):
    return source == VIEWPOINT_SOURCE or source == f'DERIVED_5M:{VIEWPOINT_SOURCE}'


def normalize_bar(record):
    """Validate a source record; unknown bar clocks remain unmergeable.

    A field with an invalid number is explicitly missing, while other fields
    remain usable. `raw_payload` is retained verbatim in the cached record.
    """
    key, source = record['instrument'], record['source']
    if not isinstance(key, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}', key):
        raise ValueError('invalid instrument')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('source required')
    interval = record['interval_minutes']
    if type(interval) is not int or interval not in (5, 30):
        raise ValueError('five or thirty minute interval required')
    semantics = record['clock_semantics']
    if semantics not in ('START', 'END', 'UNKNOWN'):
        raise ValueError('source clock semantics required')
    availability, unit = record['availability'], record['unit']
    if availability not in AVAILABILITY or unit not in ('ZAR', 'ZAR_CENTS', 'UNVERIFIED'):
        raise ValueError('explicit availability and price unit required')
    source_at = _time(record['source_timestamp']) if record.get('source_timestamp') is not None else None
    received = _time(record['received_at'])
    if source_at and source_at > received:
        raise ValueError('source time after receipt')
    start = _time(record['bar_start']) if record.get('bar_start') is not None else None
    end = _time(record['bar_end']) if record.get('bar_end') is not None else None
    verified = semantics != 'UNKNOWN' and source_at is not None and start is not None and end is not None
    if semantics != 'UNKNOWN' and not verified:
        raise ValueError('verified clock requires source and interval clocks')
    if type(record.get('provisional', False)) is not bool:
        raise ValueError('provisional must be boolean')
    if verified:
        if end-start != timedelta(minutes=interval) or source_at != (start if semantics == 'START' else end):
            raise ValueError('source timestamp does not establish interval')
        local_start, local_end = start.astimezone(SAST), end.astimezone(SAST)
        market_ok = (_session(local_start.date()) is True and local_start.date() == local_end.date()
                     and local_start.hour >= 9 and local_end <= local_start.replace(hour=17, minute=0, second=0, microsecond=0)
                     and local_start.second == 0 and local_start.microsecond == 0
                     and (local_start.hour*60 + local_start.minute - 9*60) % interval == 0)
        if not market_ok:
            raise ValueError('bar outside verified JSE session/alignment')
    data = record.get('fields')
    if not isinstance(data, dict):
        raise ValueError('field map required')
    if unit == 'UNVERIFIED' and any(data.get(field) is not None for field in FIELDS):
        raise ValueError('unverified units cannot have normalized field values')
    fields = {f: None if unit == 'UNVERIFIED' else _value(data.get(f), f, unit) for f in FIELDS}
    invalid = [f for f in FIELDS if data.get(f) is not None and fields[f] is None]
    # A defective high or low must not make an otherwise observed close vanish.
    values = {k: Decimal(fields[k]) if fields[k] is not None else None for k in ('open','high','low','close')}
    if values['high'] is not None and any(v is not None and values['high'] < v for v in (values['open'],values['close'],values['low'])):
        fields['high'] = None; invalid.append('high')
    if values['low'] is not None and any(v is not None and values['low'] > v for v in (values['open'],values['close'],values['high'])):
        fields['low'] = None; invalid.append('low')
    return {'instrument': key, 'source': source, 'interval_minutes': interval,
            'bar_start': start.isoformat() if start else None, 'bar_end': end.isoformat() if end else None,
            'source_timestamp': source_at.isoformat() if source_at else None, 'received_at': received.isoformat(),
            'clock_semantics': semantics, 'interval_verified': verified, 'availability': availability,
            'unit': 'UNVERIFIED' if unit == 'UNVERIFIED' else 'ZAR',
            'original_unit': unit, 'volume_unit': 'unverified' if unit == 'UNVERIFIED' else 'shares', 'fields': fields,
            'invalid_fields': invalid, 'provisional': bool(record.get('provisional', False) or (end and end > received)),
            'raw_payload': record.get('raw_payload'),
            'source_raw_sha256':record.get('source_raw_sha256'),
            'source_timestamp_basis':record.get('source_timestamp_basis'),
            'normalization_basis':record.get('normalization_basis'),
            'derived_inputs_sha256':record.get('derived_inputs_sha256'),
            'derived_inputs':record.get('derived_inputs')}


def merge_bars(records):
    """Merge valid canonical bars by field; source revisions remain visible."""
    groups, unknown = {}, []
    normalized = [normalize_bar(record) for record in records]
    accepted_csv_hashes = {
        item['source_raw_sha256'] for item in normalized
        if item['source'] == 'IRESS_VIEWPOINT_TABLE_CSV'
        and item.get('normalization_basis') == 'OPERATOR_ACCEPTED_VIEWPOINT_CSV_CONVENTION_V1'
        and item.get('source_raw_sha256')
    }
    for item in normalized:
        if not item['interval_verified']:
            if (item['source'] == 'IRESS_VIEWPOINT_TABLE_CSV'
                    and item.get('source_raw_sha256') in accepted_csv_hashes):
                continue
            unknown.append(item)
            continue
        identity = (item['instrument'], item['interval_minutes'], item['bar_start'], item['bar_end'])
        groups.setdefault(identity, []).append(item)
    output = []
    for (instrument, interval, start, end), items in sorted(groups.items()):
        fields = {}
        for field in FIELDS:
            per_source = {}
            for item in items:
                if item['fields'][field] is not None:
                    per_source.setdefault(item['source'], []).append(item)
            latest, revisions = [], []
            for source, entries in sorted(per_source.items()):
                entries.sort(key=lambda x: (x['received_at'], json.dumps(x, sort_keys=True)))
                latest.append(entries[-1])
                revisions.extend({'source': source, 'value': x['fields'][field],
                                  'received_at': x['received_at'], 'source_timestamp': x['source_timestamp']}
                                 for x in entries[:-1] if x['fields'][field] != entries[-1]['fields'][field])
            # Prefer usable ViewPoint imports on overlapping bars; retain every
            # alternative so a source disagreement remains inspectable.
            quality = {'LIVE':0,'DELAYED':1,'MANUAL':2,'HISTORICAL':3,'UNKNOWN':4,'STALE':5}
            latest.sort(key=lambda x:(
                x['provisional'],
                x['availability'] in ('STALE', 'UNKNOWN', 'HISTORICAL'),
                not _is_viewpoint_source(x['source']),
                quality[x['availability']],
                -_time(x['received_at']).timestamp(),
                x['source'],
            ))
            candidates = [{'source': x['source'], 'value': x['fields'][field],
                           'source_timestamp': x['source_timestamp'], 'received_at': x['received_at'],
                           'availability': x['availability'], 'provisional': x['provisional'],
                           'selection_policy': 'VIEWPOINT_PREFERRED' if _is_viewpoint_source(x['source']) else 'FALLBACK_SOURCE',
                           'source_timestamp_basis': x.get('source_timestamp_basis'),
                           'normalization_basis': x.get('normalization_basis'),
                           'source_raw_sha256': x.get('source_raw_sha256'),
                           'derived_inputs_sha256': x.get('derived_inputs_sha256'),
                           'derived_inputs': x.get('derived_inputs')} for x in latest]
            selected = candidates[0] if candidates else None
            distinct = {Decimal(c['value']) for c in candidates}
            fields[field] = {'state': 'MISSING' if not candidates else 'CONFLICT' if len(distinct)>1 else 'AVAILABLE',
                             'selected': selected, 'alternatives': candidates[1:], 'revisions': revisions,
                             'unit': 'shares' if field == 'volume' else 'ZAR'}
        output.append({'instrument': instrument, 'interval_minutes': interval, 'bar_start': start,
                       'bar_end': end, 'fields': fields, 'provisional': any(v['selected'] and v['selected']['provisional'] for v in fields.values()),
                       'research_only': True})
    unknown.sort(key=lambda item: (
        item['source_timestamp'] or '', item['received_at'], item['source'],
    ))
    return {'bars': output, 'unknown_clock_records': unknown, 'research_only': True}


def aggregate_30m(records):
    """Produce 30m same-source bars only from six completed aligned 5m bars."""
    groups = {}
    for raw in records:
        item = normalize_bar(raw)
        if not item['interval_verified'] or item['interval_minutes'] != 5 or item['provisional']:
            continue
        start = _time(item['bar_start'])
        local = start.astimezone(SAST)
        bucket = start - timedelta(minutes=(local.minute % 30))
        groups.setdefault((item['instrument'], item['source'], bucket), {}).setdefault(start, []).append(item)
    result = []
    for (instrument, source, start), members in sorted(groups.items()):
        expected = [start + timedelta(minutes=5*i) for i in range(6)]
        if set(members) != set(expected):
            continue
        bars = [max(members[t], key=lambda x: x['received_at']) for t in expected]
        def value(i, f):
            x = bars[i]['fields'][f]
            return Decimal(x) if x is not None else None
        vals = {f: [value(i, f) for i in range(6)] for f in FIELDS}
        fields = {'open': vals['open'][0], 'close': vals['close'][-1],
                  'high': max(vals['high']) if all(x is not None for x in vals['high']) else None,
                  'low': min(vals['low']) if all(x is not None for x in vals['low']) else None,
                  'volume': sum(vals['volume']) if all(x is not None for x in vals['volume']) else None}
        # The output carries every input receipt; it is derived, never a quote.
        result.append({'instrument': instrument, 'source': source, 'interval_minutes': 30,
                       'bar_start': start.isoformat(), 'bar_end': (start+timedelta(minutes=30)).isoformat(),
                       'fields': {k: str(v) if v is not None else None for k,v in fields.items()},
                       'input_receipts': [x['received_at'] for x in bars],
                       'input_source_timestamps': [x['source_timestamp'] for x in bars],
                       'input_availability': [x['availability'] for x in bars],
                       'derived': True, 'unit': 'ZAR', 'volume_unit': 'shares'})
    return result


class IntradayCache:
    """SQLite append-only raw observations; prune only unprotected temporary rows."""
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS bars (digest TEXT PRIMARY KEY, instrument TEXT NOT NULL, session TEXT, payload TEXT NOT NULL, pinned INTEGER NOT NULL, evidence INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS raw_responses (digest TEXT PRIMARY KEY, data BLOB NOT NULL)')

    def put(self, record, *, pinned=False, evidence=False):
        item = normalize_bar(record)
        # Store the original record, retaining source-specific raw payload/units.
        raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = sha256(raw.encode('utf-8')).hexdigest()
        # Unknown-clock observations age by receipt date, never by a guessed bar boundary.
        retention_clock = item['bar_start'] if item['interval_verified'] else item['received_at']
        session = _time(retention_clock).astimezone(SAST).date().isoformat()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(digest) DO UPDATE SET pinned = max(pinned,excluded.pinned), evidence = max(evidence,excluded.evidence)',
                       (digest, item['instrument'], session, raw, int(bool(pinned)), int(bool(evidence))))
        return digest

    def put_batch(self, records, raw, *, evidence=False):
        """Atomically retain raw provider bytes and normalized-record inputs."""
        if not isinstance(raw,bytes) or type(evidence) is not bool: raise ValueError('raw bytes and evidence flag required')
        digest = sha256(raw).hexdigest()
        prepared=[]
        for original in records:
            record={**original,'source_raw_sha256':digest}
            item=normalize_bar(record)
            payload=json.dumps(record,sort_keys=True,separators=(',', ':'),allow_nan=False)
            identity=sha256(payload.encode('utf-8')).hexdigest()
            retention_clock=item['bar_start'] if item['interval_verified'] else item['received_at']
            session=_time(retention_clock).astimezone(SAST).date().isoformat()
            prepared.append((identity,item['instrument'],session,payload,0,int(evidence)))
        if not prepared: return []
        with closing(sqlite3.connect(self.path,timeout=15)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT data FROM raw_responses WHERE digest=?',(digest,)).fetchone()
            if previous and previous[0] != raw: raise ValueError('raw hash collision')
            db.execute('INSERT OR IGNORE INTO raw_responses VALUES(?,?)',(digest,raw))
            db.executemany('INSERT OR IGNORE INTO bars VALUES(?,?,?,?,?,?)',prepared)
        return [row[0] for row in prepared]

    def read(self, instrument):
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute('SELECT payload FROM bars WHERE instrument = ? ORDER BY session, digest', (instrument,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def prune(self, now, active_instruments, *, retention_sessions=10, protected_instruments=()):
        now = _time(now).astimezone(SAST)
        if type(retention_sessions) is not int or retention_sessions < 1:
            raise ValueError('positive retention required')
        day, sessions = now.date(), []
        while len(sessions) < retention_sessions:
            state = _session(day)
            if state is None:
                return {'state': 'CALENDAR_UNAVAILABLE', 'deleted': 0}
            if state:
                sessions.append(day.isoformat())
            day -= timedelta(days=1)
        cutoff = sessions[-1]
        active = set(active_instruments)
        protected = set(protected_instruments)
        with closing(sqlite3.connect(self.path)) as db, db:
            candidates = db.execute('SELECT digest, instrument, session, payload FROM bars WHERE pinned=0 AND evidence=0').fetchall()
            remove = [(digest, payload) for digest, key, session, payload in candidates if key not in protected and (key not in active or (session is not None and session < cutoff))]
            db.executemany('DELETE FROM bars WHERE digest=?', [(digest,) for digest, _ in remove])
            remaining = {json.loads(row[0]).get('source_raw_sha256') for row in db.execute('SELECT payload FROM bars')}
            removed_raw = {json.loads(payload).get('source_raw_sha256') for _,payload in remove} - remaining
            deleted_raw=0
            for digest in removed_raw:
                if isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest):
                    deleted_raw += db.execute('DELETE FROM raw_responses WHERE digest=?',(digest,)).rowcount
        return {'state': 'PRUNED', 'deleted': len(remove), 'raw_deleted': deleted_raw, 'cutoff_session': cutoff}
