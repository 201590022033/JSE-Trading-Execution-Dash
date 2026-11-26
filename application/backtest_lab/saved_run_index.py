"""An in-memory, verified index of existing Backtest Lab run files."""
from datetime import date, datetime, timezone
from functools import lru_cache
from threading import Lock


def _title(summary, instrument=None):
    """Describe the selected share's slice of a run when it is known."""
    span = summary['instruments'].get(instrument, summary)
    scope = instrument if instrument in summary['instruments'] else ', '.join(list(summary['instruments'])[:2])
    others = len(summary['instruments']) - 2
    if instrument not in summary['instruments'] and others > 0:
        scope += f' and {others} more'
    strategies = summary['strategies']
    profile = strategies[0]
    strategy = f"{profile['label']} ({profile['id']} v{profile['version']})"
    if len(strategies) > 1:
        strategy = f'{len(strategies)} strategies, including {strategy}'
    period = f"{span['first_session']} to {span['last_session']}" if span['first_session'] else 'dates unavailable'
    clock = 'replay cutoff (simulated)' if 'NOT_WALL_CLOCK' in summary['created_at_basis'] else 'saved'
    return f"{scope or 'Unspecified instruments'} · {strategy} · {period} · {clock} {summary['created_at'][:10]}"


def _summarize(run, run_id):
    meta = run['meta']
    observed = set()
    instruments = {}
    for instrument, bars in sorted(run['bars'].items()):
        dates = {date.fromisoformat(row[0][:10]).isoformat() for row in bars}
        observed.update(dates)
        instruments[instrument] = {
            'first_session': min(dates, default=None), 'last_session': max(dates, default=None),
            'session_count': len(dates),
        }
    created = datetime.fromisoformat(meta['created_at'])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    strategies = [
        {'id': item['strategy_profile_id'], 'version': item['strategy_profile_version'],
         'label': item.get('name') or item['strategy_profile_id'],
         'timeframe_minutes': None if item.get('timeframe') == '1d' else item.get('timeframe_minutes'),
         'timeframe_recorded': item.get('timeframe') == '1d' or (
             type(item.get('timeframe_minutes')) is int and item['timeframe_minutes'] > 0)}
        for item in run['strategies']
    ]
    if not strategies:
        raise ValueError('missing strategy')
    return {
        'run_id': run_id, 'created_at': created.isoformat(), 'created_at_basis': meta.get('created_at_basis') or '',
        'data_basis': meta['data_basis'], 'grade': meta['grade'], 'cost_basis': meta['cost_basis'],
        'strategies': strategies, 'instruments': instruments,
        'first_session': min(observed, default=None), 'last_session': max(observed, default=None),
        'session_count': len(observed),
        'cash_equity_instruments': sorted(
            instrument for instrument in instruments
            if (receipts := [receipt for receipt in meta.get('source_receipts', []) if receipt.get('instrument') == instrument])
            and all(receipt.get('product') == 'cash_equity' for receipt in receipts)),
    }


def _fingerprint(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _exact(summary, selection):
    if not selection or summary['grade'] == 'SYNTHETIC' or selection['product'] != 'CASH_SHARE':
        return False
    if selection['instrument'] not in summary['cash_equity_instruments']:
        return False
    return any(
        strategy['timeframe_recorded'] and
        (strategy['id'], strategy['version'], strategy['timeframe_minutes']) ==
        (selection['strategy_id'], selection['strategy_version'], selection['timeframe_minutes'])
        for strategy in summary['strategies']
    )


class SavedRunIndex:
    def __init__(self, read):
        @lru_cache(maxsize=1024)
        def verified(path, fingerprint):
            summary = _summarize(read(path.parent, path.stem), path.stem)
            if _fingerprint(path) != fingerprint:
                raise ValueError('run changed while being indexed')
            return summary
        self._lock = Lock()

        @lru_cache(maxsize=4)
        def summaries(entries):
            runs, failures = [], []
            for path, fingerprint in entries:
                try:
                    if fingerprint is None:
                        raise OSError('Could not stat the file.')
                    summary = verified(path, fingerprint)
                except OSError:
                    failures.append({'run_file': path.name, 'reason': 'Could not read the file.'})
                except (ValueError, KeyError, TypeError, AttributeError, IndexError, OverflowError):
                    failures.append({'run_file': path.name, 'reason': 'File identity, contents or metadata failed verification.'})
                else:
                    runs.append({
                        **summary, 'title': _title(summary),
                        'titles_by_instrument': {key: _title(summary, key) for key in summary['instruments']},
                    })
            runs.sort(key=lambda run: (datetime.fromisoformat(run['created_at']), run['run_id']), reverse=True)
            return runs, failures

        self._summaries = summaries

    def _snapshot(self, folder):
        with self._lock:
            entries = []
            for path in sorted(folder.glob('*.json')):
                try:
                    fingerprint = _fingerprint(path)
                except OSError:
                    fingerprint = None
                entries.append((path, fingerprint))
            snapshot = self._summaries(tuple(entries))
            if snapshot[1]:
                # Retry unverifiable files while still reusing verified per-file summaries.
                self._summaries.cache_clear()
            return snapshot

    def warm(self, folder):
        self._snapshot(folder)

    def list(self, folder, selection=None):
        runs, failures = self._snapshot(folder)
        return {'runs': [
            {**run, 'matches_exact_identity': _exact(run, selection) if selection else None}
            for run in runs
        ], 'could_not_verify': failures}
