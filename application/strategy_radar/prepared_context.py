"""Bounded local evidence packets for the current Strategy Radar choices."""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
import re

MAX_CHOICES = 6
MAX_BARS_PER_CHOICE = 150
MAX_NEWS_ITEMS = 20
MAX_SENS_ITEMS = 20
MAX_PACKETS = 100


def _bounded_text(value, limit):
    return value[:limit] if isinstance(value, str) else None


def _compact_candidate(candidate):
    if not isinstance(candidate, dict):
        return None
    limits = {'source': 120, 'value': 80, 'source_timestamp': 80, 'received_at': 80,
              'availability': 40, 'source_timestamp_basis': 120,
              'normalization_basis': 160, 'selection_policy': 40, 'source_raw_sha256': 64,
              'derived_inputs_sha256': 64}
    result = {key: _bounded_text(candidate.get(key), limit)
              for key, limit in limits.items()}
    result['provisional'] = bool(candidate.get('provisional'))
    return result


def _compact_bar(bar):
    fields = {}
    for name, field in bar.get('fields', {}).items():
        candidates = [_compact_candidate(candidate) for candidate in
                      ([field.get('selected')] + (field.get('alternatives') or [])[:3])]
        revisions = (field.get('revisions') or [])[:3]
        fields[name] = {
            'state': field.get('state'),
            'unit': field.get('unit'),
            'selected': candidates[0],
            'alternatives': candidates[1:],
            'revisions': revisions,
        }
    return {'instrument': bar.get('instrument'), 'interval_minutes': bar.get('interval_minutes'),
            'bar_start': bar.get('bar_start'), 'bar_end': bar.get('bar_end'),
            'provisional': bar.get('provisional'), 'research_only': True, 'fields': fields}


def _news_items(report):
    rows = (report or {}).get('items') or []
    return [{
        'headline': _bounded_text(row.get('headline') or row.get('title'), 500),
        'summary': _bounded_text(row.get('summary') or row.get('description'), 1200),
        'source': _bounded_text(row.get('source') or row.get('publisher'), 120),
        'url': _bounded_text(row.get('url'), 2000),
        'published_at': _bounded_text(row.get('published_at') or row.get('publishedAt'), 100),
        'available_at': _bounded_text(row.get('available_at') or row.get('received_at'), 100),
        'instrument_ids': (row.get('instrument_ids') or [])[:MAX_CHOICES]
        if isinstance(row.get('instrument_ids') or [], list) else [],
    } for row in rows[:MAX_NEWS_ITEMS] if isinstance(row, dict)]


def _sens_items(event_status):
    rows = ((event_status or {}).get('sens_discovery') or {}).get('sources') or []
    return [{
        'source_id': _bounded_text(row.get('source_id'), 200),
        'headline': _bounded_text(row.get('headline'), 500),
        'url': _bounded_text(row.get('source_url') or row.get('url'), 2000),
        'published_at': _bounded_text(row.get('published_at'), 100),
        'available_at': _bounded_text(row.get('available_at'), 100),
        'current': row.get('current'),
        'provenance': {
            key: _bounded_text((row.get('provenance') or {}).get(key), 2000)
            for key in ('source', 'source_id', 'source_kind', 'source_url', 'published_at',
                        'available_at', 'raw_sha256', 'article_sha256')
            if isinstance(row.get('provenance'), dict) and (row['provenance'].get(key) is None
                or isinstance(row['provenance'].get(key), str))
        },
    } for row in rows[:MAX_SENS_ITEMS] if isinstance(row, dict)]


def _calendar_items(event_status):
    rows = (event_status or {}).get('calendar_upcoming') or (event_status or {}).get('events') or []
    return [{
        'record_id': _bounded_text(row.get('record_id'), 200),
        'title': _bounded_text(row.get('title'), 500),
        'state': _bounded_text(row.get('state'), 100),
        'event_date': _bounded_text(row.get('event_date'), 100),
        'anchor_at': _bounded_text(row.get('anchor_at'), 100),
        'source_url': _bounded_text(row.get('source_url'), 2000),
        'source_quote': _bounded_text(row.get('source_quote'), 1200),
        'instrument_ids': (row.get('instrument_ids') or [])[:MAX_CHOICES]
        if isinstance(row.get('instrument_ids') or [], list) else [],
    } for row in rows[:20] if isinstance(row, dict)]


def build_packet(service, *, reason, now, news_report=None, news_status=None, event_status=None,
                 source_errors=None, imported_instrument=None):
    """Build from retained local evidence only; never refresh a provider or run analysis."""
    if reason not in {'INITIAL_SNAPSHOT', 'TOP5_CHANGED', 'MANUAL_SELECTION', 'PIN_CHANGED',
                      'VIEWPOINT_CSV_IMPORT', 'NEWS_CAPTURE', 'SENS_RADAR_TICK'}:
        raise ValueError('known prepared-context trigger required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware preparation time required')
    if imported_instrument is not None and (not isinstance(imported_instrument, str)
            or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}', imported_instrument)):
        raise ValueError('registered imported instrument required')

    from .intraday_store import IntradayCache, merge_bars

    watches = [item for item in service.store.list_watches()
               if item.get('in_top5') or item.get('pinned')][:MAX_CHOICES]
    cache = IntradayCache(service.folder / 'intraday.sqlite3')
    choices = []
    for watch in watches:
        instrument = watch['instrument']
        daily = {}
        daily_as_of = None
        daily_error = None
        try:
            saved = json.loads((service.folder / 'daily-cache' / (instrument + '.json')).read_text(encoding='utf-8'))
            daily = saved.get('daily') or {}
            daily_as_of = saved.get('as_of')
        except (OSError, ValueError, TypeError) as exc:
            daily_error = type(exc).__name__
        merged = merge_bars(cache.read(instrument))
        bars = merged.get('bars') or []
        choices.append({
            'instrument': instrument,
            'rank': watch.get('rank'),
            'in_top5': bool(watch.get('in_top5')),
            'pinned': bool(watch.get('pinned')),
            'strategy_id': watch.get('strategy_id'),
            'strategy_version': watch.get('strategy_version'),
            'sector': watch.get('sector'),
            'daily_as_of': daily_as_of,
            'daily_latest_session': daily.get('latest_session') or daily.get('as_of_session'),
            'daily_cache_error': daily_error,
            'intraday': {
                'available_bars': len(bars),
                'bars': [_compact_bar(bar) for bar in bars[-MAX_BARS_PER_CHOICE:]],
                'unknown_clock_count': len(merged.get('unknown_clock_records') or []),
            },
        })

    imported_evidence = None
    if imported_instrument:
        imported = merge_bars(cache.read(imported_instrument))
        imported_bars = imported.get('bars') or []
        imported_evidence = {
            'instrument': imported_instrument,
            'available_bars': len(imported_bars),
            'bars': [_compact_bar(bar) for bar in imported_bars[-MAX_BARS_PER_CHOICE:]],
            'unknown_clock_count': len(imported.get('unknown_clock_records') or []),
            'raw_hashes': sorted({
                candidate.get('source_raw_sha256')
                for bar in imported_bars
                for field in bar.get('fields', {}).values()
                for candidate in ([field.get('selected')] + field.get('alternatives', []))
                if candidate and candidate.get('source_raw_sha256')
            }),
        }

    report = news_report or ((news_status or {}).get('data') or {})
    latest_capture = (event_status or {}).get('latest_capture') or {}
    return {
        'schema': 'strategy-radar-prepared-context-v1',
        'state': 'PREPARED',
        'prepared_at': now.astimezone(timezone.utc).isoformat(),
        'trigger': reason,
        'scope': 'CURRENT_TOP5_PLUS_ONE_PIN',
        'choices': choices,
        'imported_evidence': imported_evidence,
        'news': {
            'state': _bounded_text((news_status or {}).get('state', 'UNKNOWN'), 40),
            'last_success': _bounded_text((news_status or {}).get('last_success'), 100),
            'items': _news_items(report),
        },
        'sens': {
            'state': (event_status or {}).get('source_freshness', 'UNAVAILABLE'),
            'latest_capture': {
                'state': _bounded_text(latest_capture.get('state'), 80),
                'received_at': _bounded_text(latest_capture.get('received_at'), 100),
                'capture_id': _bounded_text(latest_capture.get('capture_id'), 200),
                'raw_sha256': _bounded_text(latest_capture.get('raw_sha256'), 64),
                'retained': latest_capture.get('retained'),
            },
            'items': _sens_items(event_status),
        },
        'calendar_events': _calendar_items(event_status),
        'source_errors': source_errors or [],
        'limits': {'max_choices': MAX_CHOICES, 'max_bars_per_choice': MAX_BARS_PER_CHOICE,
                   'max_news_items': MAX_NEWS_ITEMS, 'max_sens_items': MAX_SENS_ITEMS},
        'execution': {'provider_calls': 0, 'model_calls': 0, 'backtest_runs': 0,
                      'live_execution': False},
    }


class PreparedContextStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS prepared_context (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, trigger TEXT NOT NULL,
                payload TEXT NOT NULL)''')

    def save(self, packet):
        payload = json.dumps(packet, sort_keys=True, separators=(',', ':'), allow_nan=False)
        identity = sha256(payload.encode('utf-8')).hexdigest()
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.execute('INSERT OR IGNORE INTO prepared_context VALUES(?,?,?,?)',
                       (identity, packet['prepared_at'], packet['trigger'], payload))
            db.execute('''DELETE FROM prepared_context WHERE id NOT IN
                          (SELECT id FROM prepared_context ORDER BY created_at DESC, id DESC LIMIT ?)''',
                       (MAX_PACKETS,))
        return {'id': identity, 'created_at': packet['prepared_at'], 'trigger': packet['trigger'],
                'state': packet.get('state', 'PREPARED'),
                'error_type': packet.get('error_type'),
                'choice_count': len(packet.get('choices') or [])}

    def latest(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT id,created_at,trigger,payload FROM prepared_context '
                             'ORDER BY created_at DESC,id DESC LIMIT 1').fetchone()
        if not row:
            return {'state': 'NOT_PREPARED', 'packet': None, 'live_execution': False}
        packet = json.loads(row['payload'])
        return {'state': packet.get('state', 'PREPARED'), 'id': row['id'], 'created_at': row['created_at'],
                'trigger': row['trigger'], 'packet': packet,
                'live_execution': False}
