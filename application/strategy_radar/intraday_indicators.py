"""Indicator snapshots from retained, point-in-time five-minute bars."""
from datetime import timedelta

from .intraday_store import SAST, _session, _time, five_minute_updates


def _adjacent(first, second):
    end, start = _time(first['bar_end']).astimezone(SAST), _time(second['bar_start']).astimezone(SAST)
    if end == start:
        return True
    if end.date() == start.date() or (end.hour, end.minute) != (17, 0) or (start.hour, start.minute) != (9, 0):
        return False
    day = end.date() + timedelta(days=1)
    while day < start.date():
        state = _session(day)
        if state is not False:
            return False
        day += timedelta(days=1)
    return _session(start.date()) is True


def _snapshot(updates, cutoff, *, timeframe, adjacent):
    from research_indicators import DataCapabilities, MarketBar
    from technical_feature_registry import build_intraday_registry

    result = {'timeframe': timeframe, 'as_of': cutoff.isoformat(), 'research_only': True,
              'latest_bar_end': updates[-1]['bar_end'] if updates else None,
              'latest_inputs': updates[-1]['fields'] if updates else {}, 'indicators': {}}
    registry = build_intraday_registry()
    for name, required, warmup in (
        ('rsi', ('close',), 15), ('ema', ('close',), 26),
        ('stochastic', ('high', 'low', 'close'), 16),
        ('stochastic_14_3_3', ('high', 'low', 'close'), 18),
        ('ichimoku', ('high', 'low', 'close'), 78),
    ):
        suffix = []
        for update in reversed(updates):
            if suffix and not adjacent(update, suffix[0]):
                break
            if any(update['fields'][field]['selected'] is None for field in required):
                break
            suffix.insert(0, update)
            if len(suffix) == 300:
                break
        item = {'available': False, 'bars_used': len(suffix), 'required_bars': warmup,
                'values': {}, 'input_updates': [{'id': u['id'], 'version': u['version']} for u in suffix]}
        if len(suffix) < warmup:
            item['reason'] = 'INSUFFICIENT_CONTIGUOUS_COMPLETED_BARS_OR_REQUIRED_FIELD'
            result['indicators'][name] = item
            continue
        def value(update, field):
            selected = update['fields'][field]['selected']
            return float(selected['value']) if selected is not None else None
        bars = [MarketBar(close=value(u, 'close'), high=value(u, 'high'), low=value(u, 'low'),
                          open=value(u, 'open'), volume=value(u, 'volume')) for u in suffix]
        caps = DataCapabilities(has_ohlc=all(b.high is not None and b.low is not None for b in bars),
                                has_volume=all(b.volume is not None for b in bars), intraday=timeframe == '5m', frequency=timeframe)
        try:
            if name == 'stochastic_14_3_3':
                fast = []
                for index in range(len(bars)-5, len(bars)):
                    window = bars[index-13:index+1]
                    high, low = max(b.high for b in window), min(b.low for b in window)
                    if high <= low:
                        raise ValueError('flat stochastic range')
                    fast.append(100 * (bars[index].close-low)/(high-low))
                slow = [sum(fast[i:i+3])/3 for i in range(3)]
                item.update(available=True, values={'slow_k': slow[-1], 'slow_d': sum(slow)/3},
                            version='stochastic-ohlc-14-3-3-v1', reason='')
                result['indicators'][name] = item
                continue
            computed = registry.compute('ichimoku' if name == 'ichimoku' else 'intraday_continuous',
                                        bars, caps, len(bars)-1)
            fields = {'rsi': ('rsi',), 'ema': ('ema_fast', 'ema_slow', 'ema_spread'),
                      'stochastic': ('stochastic_k', 'stochastic_d')}.get(name)
            item['values'] = computed.values if fields is None else {k: computed.values[k] for k in fields if k in computed.values}
            item['available'] = bool(item['values'])
            item['version'] = computed.version
            item['reason'] = '' if item['available'] else (computed.reason or 'CALCULATION_UNAVAILABLE')
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            item['reason'] = 'CALCULATION_ERROR_' + type(exc).__name__
        result['indicators'][name] = item
    return result


def indicator_snapshot(records, *, as_of):
    """Compute separate field-dependent windows without filling gaps or bars."""
    cutoff = _time(as_of)
    updates = [u for u in five_minute_updates(records, as_of=cutoff)['updates']
               if not u['provisional'] and _time(u['bar_end']) <= cutoff]
    return _snapshot(updates, cutoff, timeframe='5m', adjacent=_adjacent)


def daily_indicator_snapshot(history, *, as_of):
    """Calculate from Zebra's retained field selections and acquisition clocks."""
    import hashlib
    import json
    from datetime import date, datetime, time
    cutoff = _time(as_of)
    updates = []
    for row in history.get('rows', []):
        day = date.fromisoformat(row['session'])
        end = datetime.combine(day, time(17), SAST)
        if end > cutoff:
            continue
        fields = {}
        for field in ('open', 'high', 'low', 'close', 'volume'):
            detail = row.get('fields', {}).get(field) or {}
            acquired = detail.get('acquired_at')
            selected = None
            if detail.get('value') is not None and acquired and _time(acquired) <= cutoff:
                selected = {'value': detail['value'], 'source': detail.get('source'),
                            'received_at': acquired, 'source_raw_sha256': detail.get('source_sha256'),
                            'state': detail.get('state'), 'alternatives': detail.get('alternatives', [])}
            fields[field] = {'selected': selected}
        payload = json.dumps({'session': row['session'], 'fields': fields}, sort_keys=True, default=str)
        updates.append({'id': row['session'], 'version': hashlib.sha256(payload.encode()).hexdigest(),
                        'bar_start': datetime.combine(day, time(9), SAST).isoformat(),
                        'bar_end': end.isoformat(), 'fields': fields})
    updates.sort(key=lambda u: u['bar_end'])
    def adjacent(first, second):
        day = _time(first['bar_end']).astimezone(SAST).date() + timedelta(days=1)
        target = _time(second['bar_start']).astimezone(SAST).date()
        while day < target:
            if _session(day) is not False:
                return False
            day += timedelta(days=1)
        return day == target and _session(day) is True
    return _snapshot(updates, cutoff, timeframe='1d', adjacent=adjacent)


def research_wilder_rsi(closes, period):
    """Reuse the frozen RSI14 and its Wilder smoothing convention for other periods."""
    from domain.features.technical import _ema, candidate_rsi_wilder

    if type(period) is not int or period < 1:
        raise ValueError('Positive RSI period required')
    if period == 14:
        return candidate_rsi_wilder(closes).value
    if len(closes) <= period:
        return None
    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    # Wilder's smoothing factor 1/period equals EMA alpha at span 2*period-1.
    def average(values):
        return _ema([sum(values[:period]) / period, *values[period:]], 2 * period - 1)
    gain, loss = average(gains), average(losses)
    return 100 - 100 / (1 + gain / loss) if loss else (100.0 if gain else 50.0)
