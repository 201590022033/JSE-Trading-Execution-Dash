"""Read retained daily inputs and comparison evidence for the W07 display."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from application.opportunities.session_freshness import latest_expected_session
from .breakout_pullback import REFERENCE, evaluate
from .intraday_store import _time

COMPARISON = Path(__file__).resolve().parents[2] / 'artifacts/research/radar-exact-daily/w06-comparison.json'
MAX_ARTIFACT_BYTES = 8_000_000
MAX_DAILY_CACHE_BYTES = 24_000_000
DISPLAY_BAR_LIMIT = 300
DISPLAY_FIELDS = (
    'session', 'state', 'breakout_date', 'breakout_level', 'breakout_bar_high',
    'pullback_low', 'sessions_left', 'window_ends', 'window_end_basis', 'rules',
    'rules_evaluable', 'score', 'components_evaluable', 'score_components',
    'data_quality', 'low_confidence', 'stop_reference', 'target_reference',
)


def _read_object(path, maximum):
    # Bound the read even if the file is replaced after stat.
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('retained record exceeds display bound')
    return json.loads(raw)


@lru_cache(maxsize=4)
def _comparison(path, modified, size):
    payload = _read_object(path, MAX_ARTIFACT_BYTES)
    supplied = payload.pop('content_sha256')
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode()
    if (sha256(raw).hexdigest() != supplied or payload['schema'] != 'w06-exact-comparison-v1'
            or payload['retrospective'] is not True or payload['live_execution'] is not False
            or payload['profile'] != {'id': REFERENCE.strategy_profile_id,
                                      'version': REFERENCE.strategy_profile_version}):
        raise ValueError('comparison identity or integrity mismatch')
    return payload


def retained_validation(instrument, benchmark, path=None):
    path = COMPARISON if path is None else path
    fallback = {'state': 'NOT_YET_VALIDATED', 'label': 'not yet validated (artifact unavailable)'}
    try:
        stat = path.stat()
        payload = _comparison(path, stat.st_mtime_ns, stat.st_size)
        if payload['benchmark'] != benchmark:
            return fallback
        variants = payload['instruments'][instrument]['variants']
        count = variants['C']['summary']['closed_trades']
        original = variants['A']['summary']['closed_trades']
        floor = payload['minimum_closed_trades']
        if (any(type(value) is not int or value < 0 for value in (count, original))
                or type(floor) is not int or floor < 30):
            return fallback
        noun = 'trade' if count == 1 else 'trades'
        return {'state': 'RETROSPECTIVE_COMPARISON', 'closed_trades': count,
                'minimum_closed_trades': floor, 'window': payload['window'],
                'label': f'W06 comparison: {count} closed {instrument} breakout/pullback {noun} '
                         f'({original} original-rule trades), '
                         + (f'below the {floor}-trade floor.' if count < floor else f'{floor}-trade count floor reached.')
                         + ' Not validated.'}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return fallback


def _rows(folder, key):
    if folder is None or not key or not key.replace('_', '').isalnum():
        return []
    try:
        return _read_object(Path(folder) / 'daily-cache' / (key + '.json'),
                            MAX_DAILY_CACHE_BYTES)['daily']['history']['rows'][-DISPLAY_BAR_LIMIT:]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def breakout_pullback_display(folder, instrument, benchmark, now):
    """Keep this panel independent of the operational checklist and monitor."""
    base = {'validation': retained_validation(instrument, benchmark),
            'components_total': 5, 'research_only': True, 'live_execution': False}
    try:
        now = _time(now)
        result = evaluate(instrument, _rows(folder, instrument), _rows(folder, benchmark),
                          as_of=now, benchmark=benchmark, retrospective=True)
        if result['observations']:
            observation = result['observations'][-1]
            expected = latest_expected_session(now)
            return {**base, **{key: observation[key] for key in DISPLAY_FIELDS},
                    'stale': expected is not None and observation['session'] < expected,
                    'calendar_unverified': expected is None,
                    'availability_basis': result['availability_basis']}
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError):
        pass
    return {**base, 'state': 'NO_DATA', 'session': None, 'score': None,
            'components_evaluable': 0, 'rules': {}, 'data_quality': 'NO_DATA'}
