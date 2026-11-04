"""Independent window-scoped descriptive indicators; not policy evidence."""
from datetime import date, datetime, timezone
from math import isfinite

from domain.features.technical import _ema, candidate_rsi_wilder
from .swing_data_quality import real_ohlc


def _num(value, positive=False):
    try:
        x = float(value)
        return x if isfinite(x) and (x > 0 if positive else x >= 0) else None
    except (TypeError, ValueError, OverflowError):
        return None


def calculate(instrument, data, benchmark, now):
    """Use observed bars only; a broken range resets ATR rather than bridging it."""
    rows = data['rows']
    if not rows or data['instrument'] != instrument or data.get('live_execution') is not False:
        raise ValueError('identified research history required')
    acquired = datetime.fromisoformat(data['acquired_at'].replace('Z', '+00:00'))
    if acquired.tzinfo is None or acquired > now:
        raise ValueError('actual past acquisition required')
    sessions = [date.fromisoformat(r['session']) for r in rows]
    if any(a >= b for a, b in zip(sessions, sessions[1:])):
        raise ValueError('ordered distinct observations required')
    from .radar_price_capture import usable_close
    for row in rows:
        observed = datetime.fromisoformat(row.get('acquired_at', data['acquired_at']).replace('Z', '+00:00'))
        if observed.tzinfo is None or observed > now or not usable_close(row['session'], observed):
            raise ValueError('rows must have been completed at their actual acquisition')
    closes = [_num(r.get('close'), positive=True) for r in rows]
    suffix = 0
    for value in reversed(closes):
        if value is None: break
        suffix += 1
    close_values = closes[-suffix:] if suffix else []
    values = {'ema20': None, 'ema50': None, 'rsi14_wilder': None,
              'atr14_wilder': None, 'relative_volume20': None,
              'prior_high10': None, 'prior_low10': None,
              'prior_high20': None, 'prior_low20': None, 'relative_return20': None}
    reasons = {}
    if len(close_values) >= 50:
        values['ema20'], values['ema50'] = _ema(close_values, 20), _ema(close_values, 50)
    else: reasons['ema'] = 'NEEDS_50_CONSECUTIVE_VALID_OBSERVED_CLOSES'
    rsi = candidate_rsi_wilder(close_values)
    if rsi.available: values['rsi14_wilder'] = rsi.value
    else: reasons['rsi'] = 'NEEDS_15_CONSECUTIVE_VALID_OBSERVED_CLOSES'
    # Do not join an ATR seed across an invalid bar or provider transition.
    tail = []
    provider = rows[-1].get('source', data.get('provider'))
    for row in reversed(rows):
        if row.get('source', data.get('provider')) != provider or not real_ohlc(row): break
        tail.append(row)
    tail.reverse()
    if len(tail) >= 15:
        ranges = [max(float(r['high'])-float(r['low']),
                      abs(float(r['high'])-float(tail[i-1]['close'])),
                      abs(float(r['low'])-float(tail[i-1]['close'])))
                  for i, r in enumerate(tail) if i]
        atr = sum(ranges[:14])/14
        for value in ranges[14:]: atr = (13*atr+value)/14
        values['atr14_wilder'] = atr
    else: reasons['atr'] = 'NEEDS_15_CONSECUTIVE_VALID_SAME_SOURCE_OHLC_ROWS'
    for n in (10, 20):
        prior = rows[-n-1:-1]
        if len(prior) == n and all(real_ohlc(r) for r in prior):
            values[f'prior_high{n}'] = max(float(r['high']) for r in prior)
            values[f'prior_low{n}'] = min(float(r['low']) for r in prior)
        else: reasons[f'prior_range{n}'] = 'INVALID_OR_MISSING_OHLC_IN_REQUIRED_WINDOW'
    vols = [_num(r.get('volume')) for r in rows[-21:]]
    if len(vols) == 21 and all(v is not None for v in vols) and sum(vols[:-1]) > 0:
        values['relative_volume20'] = vols[-1] / (sum(vols[:-1])/20)
    else: reasons['volume'] = 'NEEDS_21_VALID_VOLUME_OBSERVATIONS'
    if benchmark and len(close_values) >= 21:
        bdays = [date.fromisoformat(r['session']) for r in benchmark['rows']]
        if any(a >= b for a, b in zip(bdays, bdays[1:])):
            raise ValueError('ordered unique benchmark observations required')
        for row in benchmark['rows']:
            observed = datetime.fromisoformat(row.get('acquired_at', benchmark['acquired_at']).replace('Z', '+00:00'))
            if observed.tzinfo is None or observed > now or not usable_close(row['session'], observed):
                raise ValueError('benchmark row not completed at acquisition')
        b = {r['session']: _num(r.get('close'), positive=True) for r in benchmark['rows']}
        start, end = rows[-21]['session'], rows[-1]['session']
        if b.get(start) and b.get(end) and benchmark['rows'][-1]['session'] == end:
            values['relative_return20'] = close_values[-1]/close_values[-21]-b[end]/b[start]
        else: reasons['benchmark'] = 'ALIGNED_BENCHMARK_ENDPOINTS_UNAVAILABLE'
    else: reasons['benchmark'] = 'ALIGNED_BENCHMARK_ENDPOINTS_UNAVAILABLE'
    bad = [r['session'] for r in rows if not real_ohlc(r)]
    return {'state': 'PARTIAL' if reasons else 'AVAILABLE', 'instrument': instrument,
            'as_of_session': rows[-1]['session'], 'acquired_at': data['acquired_at'],
            'source_policy': data.get('source_policy', 'YAHOO_ONLY'),
            'source_hash': data['source_sha256'], 'benchmark_session': benchmark['rows'][-1]['session'] if benchmark and benchmark['rows'] else None,
            'values': values, 'unavailable_reasons': reasons,
            'quality': {'invalid_ohlc_count': len(bad), 'recent_invalid_sessions': bad[-10:],
                        'atr_valid_same_source_rows': len(tail),
                        'atr_seed_session': tail[0]['session'] if tail else None,
                        'calendar': 'OBSERVED_DATES_ONLY_NOT_VERIFIED_COMPLETE'},
            'scope': 'DESCRIPTIVE_RESEARCH_NOT_POLICY_OR_EXECUTION', 'live_execution': False}
