"""Point-in-time daily research rules; video-derived thresholds are estimates."""
from statistics import mean
from application.opportunities.swing_technical import snapshot
from domain.features.technical import _ema

PROFILES = (
    ('swing', 'Swing baseline', 'jse_swing_3_5d', '1.3.0'),
    ('vcp', 'VCP daily approximation', 'vcp_daily_research', '1.0.0'),
    ('box', 'Box breakout daily approximation', 'box_breakout_daily_research', '1.0.0'),
    ('pull', 'Pullback daily approximation', 'pullback_daily_research', '1.0.0'),
)


def condition(name, text, value, passed):
    return {'c': name, 't': text, 'v': round(value, 4) if value is not None else None,
            'ok': passed is True}


def evaluate(strategy, instrument, i, bars_context):
    """Only bars through i and the aligned benchmark may enter the decision."""
    rows = bars_context[instrument][:i + 1]
    if len(rows) < 51:
        return [], None
    close = [float(x['close']) for x in rows]
    high = [float(x['high']) for x in rows]
    low = [float(x['low']) for x in rows]
    volumes = [float(x['volume']) for x in rows]
    session = rows[-1]['timestamp'][:10]
    if strategy == 'swing':
        from application.opportunities.public_research import _available_at
        from datetime import timedelta
        benchmark = [x for x in bars_context.get('ETF_STX40', []) if x['timestamp'][:10] <= session]
        chart = {'interval': '1d', 'currency': 'ZAR', 'symbol': instrument, 'bars': rows}
        bchart = {'interval': '1d', 'currency': 'ZAR', 'symbol': 'ETF_STX40', 'bars': benchmark} if benchmark else None
        result = snapshot(chart, evaluated_at=_available_at(session) + timedelta(seconds=1), benchmark_chart=bchart)
        c = result.get('conditions', {}); v = result.get('values', {}); geometry = result.get('geometry', {})
        traces = [condition('Trend', 'EMA20/50 uptrend', v.get('ema20'), c.get('ema_uptrend')),
            condition('Breakout or reclaim', '20-session breakout or EMA20 reclaim', v.get('prior_high20'), bool(c.get('breakout20') or c.get('ema20_reclaim'))),
            condition('Momentum', 'Wilder RSI 50–70', v.get('rsi14_wilder'), c.get('rsi_50_70')),
            condition('Volume', 'Volume above prior 20-session average', v.get('relative_volume20'), c.get('volume_above_prior20')),
            condition('Benchmark', 'Outperform aligned benchmark over 20 sessions', v.get('relative_return20'), c.get('outperforming_benchmark20')),
            condition('Snapshot eligibility', 'Complete snapshot and valid shadow stop', None, c.get('core_setup'))]
        return traces, geometry.get('stop')
    e9, e21 = _ema(close, 9), _ema(close, 21)
    avgvol = mean(volumes[-21:-1]); rv = volumes[-1] / avgvol if avgvol else None
    trend = close[-1] > e9 > e21
    if strategy == 'vcp':
        recent = mean(high[j]-low[j] for j in range(i-5, i)); prior = mean(high[j]-low[j] for j in range(i-20, i-5))
        ratio = recent/prior if prior else None
        traces = [condition('Trend', 'Close above EMA9 above EMA21', close[-1]-e9, trend),
            condition('Contraction', 'Prior five-bar range ≤ 0.8× previous fifteen', ratio, ratio is not None and ratio <= .8),
            condition('Breakout', 'Close above prior 10-bar high', close[-1]-max(high[-11:-1]), close[-1]>max(high[-11:-1])),
            condition('Volume', 'Volume at least 1.3× prior 20-bar average', rv, rv is not None and rv>=1.3)]
        stop = min(low[-6:])
    elif strategy == 'box':
        top, bottom = max(high[-9:-1]), min(low[-9:-1]); width = (top-bottom)/close[-2]*100
        traces = [condition('Trend', 'Close above EMA9 above EMA21', close[-1]-e9, trend),
            condition('Tight box', 'Prior eight-bar range ≤ 6%', width, width<=6),
            condition('Breakout', 'Close above prior box high', close[-1]-top, close[-1]>top),
            condition('Volume', 'Volume at least 1.2× prior average', rv, rv is not None and rv>=1.2)]
        stop = bottom
    elif strategy == 'pull':
        dd = (1-close[-2]/max(high[-11:-2]))*100
        traces = [condition('Trend', 'EMA9 above EMA21 and EMA21 rising over five bars', e9-e21, e9>e21 and e21>_ema(close[:-5],21)),
            condition('Pullback', 'Prior close 1–7% below earlier high', dd, 1<=dd<=7),
            condition('Trigger', 'Close above prior high', close[-1]-high[-2], close[-1]>high[-2]),
            condition('Volume', 'Volume at least 1.1× prior average', rv, rv is not None and rv>=1.1)]
        stop = min(low[-4:])
    else:
        raise ValueError('unknown strategy')
    traces.append(condition('Stop geometry', 'Positive stop below signal close', stop, 0 < stop < close[-1]))
    return traces, stop
