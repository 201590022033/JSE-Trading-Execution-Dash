"""Refresh Radar display caches after a successful retained Zebra receipt."""
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import Event, Thread
from uuid import uuid4

logger = logging.getLogger(__name__)
MAX_RECEIPT_BYTES = 4_000_000


def refresh_from_receipt(root, receipt_path, *, loader=None, now=None):
    from .daily import prewarm_daily
    root = Path(root)
    path = Path(receipt_path)
    raw = path.read_bytes()
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ValueError('Receipt too large')
    receipt = json.loads(raw)
    if (receipt.get('schema') != 'zebra-source-refresh-v1'
            or receipt.get('research_only') is not True
            or receipt.get('live_execution') is not False):
        raise ValueError('Invalid receipt')
    finished = datetime.fromisoformat(receipt['finished_at'].replace('Z', '+00:00'))
    clock = now or datetime.now(timezone.utc)
    if finished.tzinfo is None or finished > clock:
        raise ValueError('Invalid receipt time')
    successful = {row['instrument'] for row in receipt['results']
                  if row.get('capture', {}).get('state') == 'CAPTURED'}
    successful.update(row['instrument'] for row in receipt.get('yahoo', {}).get('results', [])
                      if row.get('state') == 'CAPTURED')
    if not successful:
        return []
    folder = root / 'runtime/local-swing-data/strategy-radar'
    db_path = folder / 'watches.sqlite3'
    with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        watches = db.execute("SELECT instrument, benchmark FROM radar_watch WHERE state!='ARCHIVED'").fetchall()
    keys = set()
    for instrument, benchmark in watches:
        if instrument in successful:
            keys.add(instrument)
        if benchmark in successful:
            keys.add(benchmark)
    if not keys:
        return []
    result = (loader or prewarm_daily)(sorted(keys), root=root, now=clock)
    cache = folder / 'daily-cache'
    cache.mkdir(parents=True, exist_ok=True)
    written = []
    for key, item in result.get('watches', {}).items():
        if key not in keys or item.get('state') != 'AVAILABLE' or not item.get('latest_session'):
            continue
        target = cache / (key + '.json')
        try:
            previous = json.loads(target.read_bytes())['daily']['latest_session']
            if previous and previous > item['latest_session']:
                continue
        except (OSError, ValueError, KeyError, TypeError):
            pass
        payload = json.dumps({'as_of': result['as_of'], 'daily': item}, allow_nan=False).encode()
        temporary = cache / (key + '-' + uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        written.append(key)
    return written


def start_receipt_prewarm(root, *, interval=60):
    """Poll completed local receipts in a single background thread."""
    root = Path(root)
    receipts = root / 'runtime/local-swing-data/zebra-refresh-receipts'
    stop = Event()

    def watch():
        last = None
        while not stop.is_set():
            try:
                paths = sorted(receipts.glob('*.json'))
                if paths:
                    path = paths[-1]
                    stat = path.stat()
                    identity = (path.name, stat.st_size, stat.st_mtime_ns)
                    if identity != last:
                        refresh_from_receipt(root, path)
                        last = identity
            except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                logger.warning('Radar capture receipt prewarm unavailable')
            stop.wait(interval)

    thread = Thread(target=watch, name='radar-receipt-prewarm', daemon=True)
    thread.start()
    return stop
