"""Daily radar built from retained Zebra observations; no provider requests."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from .intraday_evaluation import _trace
from application.opportunities.session_freshness import latest_expected_session, next_session
from application.opportunities.swing_technical import snapshot

_FIELDS = ('open', 'high', 'low', 'close', 'volume')
_STATES = {'SINGLE_SOURCE', 'AGREEMENT', 'THREE_PROVIDER_AGREEMENT'}
_NAMES = (('ema_uptrend', 'Close above EMA20 above EMA50'),
          ('breakout20', 'Close above prior 20-session high'),
          ('ema20_reclaim', 'Price reclaims EMA20 in an uptrend'),
          ('rsi_50_70', 'RSI between 50 and 70'),
          ('volume_above_prior20', 'Volume above its prior 20-session mean'),
          ('outperforming_benchmark20', '20-session return exceeds aligned benchmark'))


def _chart(folder, instrument, now):
    if not instrument or not instrument.replace('_', '').isalnum():
        return None
    try:
        item = json.loads((Path(folder) / 'daily-cache' / (instrument + '.json')).read_text(encoding='utf-8'))['daily']
        expected = latest_expected_session(now)
        if not expected or item.get('latest_session') != expected:
            return None
        rows = item['history']['rows'][-100:]
        if not rows or rows[-1]['session'] != expected:
            return None
        if any(next_session(a['session']) != b['session'] for a, b in zip(rows, rows[1:])):
            return None
        bars = []
        for row in rows:
            bar = {'timestamp': row['session'] + 'T00:00:00+00:00'}
            for field in _FIELDS:
                detail = row['fields'][field]
                stamp = datetime.fromisoformat(detail['acquired_at'].replace('Z', '+00:00')) if detail.get('acquired_at') else None
                if detail.get('state') in _STATES and stamp and stamp.tzinfo and datetime.fromisoformat(row['session']).replace(tzinfo=timezone.utc) + timedelta(hours=15) <= stamp <= now and detail.get('value') is not None:
                    bar[field] = detail['value']
            if 'close' not in bar:
                return None
            bars.append(bar)
        return {'symbol': instrument, 'interval': '1d', 'currency': 'ZAR', 'bars': bars}
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        return None


def evaluate_watches(service, *, now=None):
    now = now or datetime.now(timezone.utc)
    watches = service.store.list_watches()
    charts = {key: _chart(service.folder, key, now) for key in
              {w['instrument'] for w in watches} | {w.get('benchmark') for w in watches}}
    results = {}
    for watch in watches:
        key = watch['instrument']
        data = snapshot(charts.get(key), evaluated_at=now, benchmark_chart=charts.get(watch.get('benchmark')))
        conditions = data.get('conditions', {})
        rules = []
        values = data.get('values', {})
        details = {
            'ema_uptrend': (data.get('last_close'), 'EMA20 %s; EMA50 %s' % (values.get('ema20'), values.get('ema50'))),
            'breakout20': (data.get('last_close'), values.get('prior_high20')),
            'ema20_reclaim': (data.get('last_close'), values.get('ema20')),
            'rsi_50_70': (values.get('rsi14_wilder'), '50 to 70'),
            'volume_above_prior20': (values.get('relative_volume20'), '1.0 times prior mean'),
            'outperforming_benchmark20': (values.get('relative_return20'), '0 excess return'),
        }
        for name, description in _NAMES:
            passed_rule = conditions.get(name)
            value, threshold = details[name] if passed_rule is not None else (None, None)
            rules.append(_trace(name, False, passed_rule, value, threshold, [], description if passed_rule is not None else description + ' - missing or disputed source fields'))
        passed = sum(r['state'] == 'PASS' for r in rules)
        unknown = sum(r['state'] == 'UNKNOWN' for r in rules)
        results[key] = {'instrument': key, 'strategy_id': 'jse_swing_3_5d', 'strategy_version': '1.1.0',
                        'timeframe_minutes': None, 'evaluated_at': now.isoformat(),
                        'state': 'UNKNOWN' if unknown == len(rules) else 'WATCHING', 'rules': rules,
                        'passed': passed, 'unknown': unknown, 'applicable': len(rules),
                        'session': data.get('session'), 'missing': data.get('missing', []),
                        'source_bars': data.get('source_bars', 0), 'source_sha256': data.get('source_sha256'), 'values': data.get('values', {}), 'benchmark_instrument': watch.get('benchmark'),
                        'research_only': True, 'live_signal': False}
    return results
