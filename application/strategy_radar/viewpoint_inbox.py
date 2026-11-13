"""Import native five-minute ViewPoint exports from Radar's local inbox."""
from datetime import datetime, timezone
from hashlib import sha256
import csv
import io
import re
from pathlib import Path

from application.opportunities.zebra_instruments import mappings
from .intraday_adapters import viewpoint_table_csv
from .intraday_store import IntradayCache

_MAX_BYTES = 2_500_000
_EXPORT = re.compile(r'([A-Z][A-Z0-9]{1,7})\.JSE \(\d{17} _ \d{17}\)(?: \(\d+\))?\.csv', re.I)


class ViewPointInbox:
    def __init__(self, service):
        self.service = service
        self.folder = service.folder / 'viewpoint-inbox' / '5m'

    def load(self, watches, now, *, include_downloads=True):
        registered = mappings(self.service.folder.parent / 'radar-public-prices')
        instruments = dict.fromkeys(watch['instrument'] for watch in watches)
        instruments.update(dict.fromkeys(watch.get('benchmark') for watch in watches))
        selected = {registered[instrument]: instrument for instrument in instruments
                    if instrument in registered}
        pending = {symbol: [] for symbol in selected}
        folders = [self.folder]
        if include_downloads:
            folders.append(Path.home() / 'Downloads')
        for folder in folders:
            if not folder.is_dir():
                continue
            for path in folder.iterdir():
                match = _EXPORT.fullmatch(path.name)
                if match and match[1].upper() in pending and not path.is_symlink() and path.is_file():
                    pending[match[1].upper()].append(path)

        cache = IntradayCache(self.service.folder / 'intraday.sqlite3')
        errors = 0
        for symbol, paths in pending.items():
            if not paths:
                continue
            instrument = selected[symbol]
            retained = {row.get('source_raw_sha256') for row in cache.read(instrument)
                        if row['source'] == 'IRESS_VIEWPOINT_TABLE_CSV' and row['interval_minutes'] == 5}
            for path in sorted(paths, key=lambda path: path.name, reverse=True)[:8]:
                try:
                    modified = path.stat()
                    with path.open('rb') as stream:
                        raw = stream.read(_MAX_BYTES + 1)
                    if len(raw) > _MAX_BYTES or path.stat().st_mtime_ns != modified.st_mtime_ns:
                        continue
                    digest = sha256(raw).hexdigest()
                    if digest in retained:
                        continue
                    if path.parent != self.folder:
                        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
                        starts = sorted({datetime.fromisoformat(row['Date']) for row in reader})
                        if not any((end - start).total_seconds() == 300
                                   for start, end in zip(starts, starts[1:])):
                            continue
                    records = viewpoint_table_csv(
                        raw, instrument, f'{symbol}.JSE', now, file_name=path.name,
                        file_modified_at=datetime.fromtimestamp(modified.st_mtime, timezone.utc),
                        interval_minutes=5, accept_operator_conventions=True,
                    )
                    cache.put_batch(records, raw, evidence=True)
                    retained.add(digest)
                except (OSError, ValueError, TypeError, KeyError, csv.Error):
                    errors += 1
        return errors
