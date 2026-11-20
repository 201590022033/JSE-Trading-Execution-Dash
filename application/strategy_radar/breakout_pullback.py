"""Isolated completed-daily-bar breakout and pullback research."""
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from operator import ge, gt, lt
import re
from statistics import median

from application.opportunities.session_freshness import next_session
from domain.backtest.component_engine import atr
from domain.strategy.registry import BREAKOUT_PULLBACK_PROFILE
from ichimoku_features import calculate_ichimoku
from research_indicators import DataCapabilities, MarketBar

from .intraday_indicators import research_wilder_rsi
from .intraday_store import _session, _time


REFERENCE = BREAKOUT_PULLBACK_PROFILE.reference
_FIELDS = ('open', 'high', 'low', 'close', 'volume')
_CLOUD_BARS = 78
_SHA256 = re.compile(r'[0-9a-f]{64}')


@dataclass(frozen=True)
class Settings:
    N_BREAKOUT: int = 20
    W_PULLBACK: int = 5
    ATR_PERIOD: int = 14
    PB_TOUCH_ATR: float = 0.5
    PB_BUFFER_ATR: float = 0.5
    PB_TOUCH_PCT: float = 0.01
    PB_BUFFER_PCT: float = 0.015
    RSI_PERIOD: int = 14
    RSI_MIN: float = 50
    RSI_MAX: float = 70
    N_VOLUME: int = 20
    VOL_MIN: float = 1.0
    BENCHMARK_LOOKBACK: int = 20
    MIN_EXCESS_RETURN: float = 0.0
    STOP_ATR_BUFFER: float = 0.25
    TARGET_R: float = 2.0
    HOLD_MIN: int = 3
    HOLD_MAX: int = 5
    MAX_ACTIVE: int = 1
    MAX_GAP_SESSIONS: int = 3
    MIN_BARS: int = 10
    WT_STRUCTURE: float = 0.35
    WT_TREND: float = 0.20
    WT_MOMENTUM: float = 0.20
    WT_VOLUME: float = 0.15
    WT_RELATIVE: float = 0.10
    RELATIVE_SCORE_SCALE: float = 0.05

    def __post_init__(self):
        windows = (self.N_BREAKOUT, self.W_PULLBACK, self.ATR_PERIOD, self.RSI_PERIOD,
                   self.N_VOLUME, self.BENCHMARK_LOOKBACK, self.MIN_BARS)
        if any(type(value) is not int or value < 1 for value in windows):
            raise ValueError('Positive integer windows required')
        if (any(type(value) is not int for value in (self.MAX_ACTIVE, self.HOLD_MIN, self.HOLD_MAX))
                or type(self.MAX_GAP_SESSIONS) is not int or self.MAX_GAP_SESSIONS < 0
                or self.MAX_ACTIVE != 1 or self.HOLD_MIN not in (3, 4, 5)
                or self.HOLD_MAX not in (3, 4, 5) or self.HOLD_MIN > self.HOLD_MAX):
            raise ValueError('Unsupported setup or replay bounds')
        positive = (self.PB_TOUCH_ATR, self.PB_TOUCH_PCT, self.TARGET_R, self.RELATIVE_SCORE_SCALE)
        nonnegative = (self.PB_BUFFER_ATR, self.PB_BUFFER_PCT, self.STOP_ATR_BUFFER,
                       self.VOL_MIN, *self.weights().values())
        if (any(not isfinite(value) or value <= 0 for value in positive)
                or any(not isfinite(value) or value < 0 for value in nonnegative)
                or not any(self.weights().values()) or not isfinite(self.MIN_EXCESS_RETURN)
                or not 0 <= self.RSI_MIN <= self.RSI_MAX <= 100):
            raise ValueError('Invalid research thresholds or weights')

    def weights(self):
        return {'structure': self.WT_STRUCTURE, 'trend': self.WT_TREND, 'momentum': self.WT_MOMENTUM,
                'volume': self.WT_VOLUME, 'relative_strength': self.WT_RELATIVE}


def _clock(day):
    # Same next-UTC-day research completion convention as the exact daily review.
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(days=1)


def _selected(detail, day, cutoff, *, volume=False):
    try:
        if isinstance(detail['value'], bool):
            return None
        value = float(detail['value'])
        when = _time(detail['acquired_at'])
        if (not isfinite(value) or not detail['source'] or
                value < 0 or (not volume and value == 0)
                or not _SHA256.fullmatch(detail.get('source_sha256') or '') or not _clock(day) - timedelta(hours=9) <= when <= cutoff):
            return None
        return value
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def _choose_row(row, cutoff):
    day = row['session']
    details = row.get('fields') or {}
    values = {name: _selected(details.get(name) or {}, day, cutoff, volume=name == 'volume')
              for name in _FIELDS}
    if all(value is None for value in values.values()):
        return None
    if (values['high'] is not None and values['low'] is not None and values['low'] > values['high']
            or any(values[name] is not None and values['close'] is not None and invalid(values['close'], values[name])
                   for name, invalid in (('low', lt), ('high', gt)))):
        values.update(high=None, low=None)
    opening, low, high = (values[name] for name in ('open', 'low', 'high'))
    if opening is not None and (low is not None and opening < low or high is not None and opening > high):
        values['open'] = None
    volume = details.get('volume') or {}
    alternatives = {}
    for detail in volume.get('alternatives', ()):
        value = _selected(detail, day, cutoff, volume=True)
        if value is not None and detail['source'] != volume.get('source'):
            alternatives[detail['source']] = value
    inputs = {name: {**details[name], 'alternatives': [
        detail for detail in details[name].get('alternatives', ())
        if _selected(detail, day, cutoff, volume=name == 'volume') is not None],
        'provider_revisions': {
            source: [revision for revision in revisions if _selected(
                revision, day, cutoff, volume=name == 'volume') is not None]
            for source, revisions in details[name].get('provider_revisions', {}).items()}}
              for name, value in values.items() if value is not None}
    source = volume.get('source') if values['volume'] is not None else None
    return {'session': day, **values, 'input_receipts': inputs,
            'volume_source': source, 'provider_volumes': {**alternatives, **({source: values['volume']} if source else {})}}


def _missing_between(first, last):
    cursor = next_session(first)
    missing = []
    while cursor is not None and cursor < last:
        missing.append(cursor)
        cursor = next_session(cursor)
    return missing if cursor == last else None


def _scan_windows(rows, config):
    gaps = []
    start = 0
    for index, (previous, current) in enumerate(zip(rows, rows[1:]), 1):
        previous, current = previous['session'], current['session']
        missing = _missing_between(previous, current)
        if missing is None or missing:
            gaps.append({'after': previous, 'before': current, 'missing_sessions': missing})
        if missing is not None and len(missing) > config.MAX_GAP_SESSIONS:
            start = index
    return rows[start:], gaps


def _suffix(rows, names):
    start = len(rows)
    for row in reversed(rows):
        if any(row[name] is None for name in names):
            break
        start -= 1
    return rows[start:]


def _ratio(values):
    if not values or any(value is None for value in values):
        return None
    baseline = median(values[:-1])
    return values[-1] / baseline if baseline > 0 else None


def _cloud(bars):
    if len(bars) < _CLOUD_BARS:
        return None
    cloud = calculate_ichimoku(bars[-_CLOUD_BARS:], DataCapabilities(has_ohlc=True))
    return max(cloud.values['current_senkou_a'], cloud.values['current_senkou_b']) if cloud.available else None


def _features(rows, benchmark, config):
    current = rows[-1]
    completed = len(rows) >= config.MIN_BARS
    prices = _suffix(rows, ('close', 'high', 'low')) if completed else []
    bars = [MarketBar(close=row['close'], high=row['high'], low=row['low']) for row in prices]
    atr_value = atr(bars, config.ATR_PERIOD)
    closes = _suffix(rows, ('close',)) if completed else []
    rsi = research_wilder_rsi([row['close'] for row in closes], config.RSI_PERIOD)
    prior_rsi = research_wilder_rsi([row['close'] for row in closes[:-1]], config.RSI_PERIOD)
    volume_window = rows[-config.N_VOLUME-1:] if completed and len(rows) > config.N_VOLUME else []
    volume = _ratio([row['volume'] for row in volume_window])
    previous_volume = _ratio([row['volume'] for row in rows[-config.N_VOLUME-2:-1]]) if volume_window and len(rows) > config.N_VOLUME + 1 else None
    alternatives = {}
    for provider in sorted(current['provider_volumes']):
        if provider == current['volume_source']:
            continue
        ratio = _ratio([row['provider_volumes'].get(provider) for row in volume_window])
        alternatives[provider] = {'ratio': ratio, 'would_flip': None if ratio is None or volume is None else
                                  (ratio >= config.VOL_MIN) != (volume >= config.VOL_MIN)}
    highs = [row['high'] for row in rows[-config.N_BREAKOUT-1:-1]]
    prior_high = max(highs) if completed and len(highs) == config.N_BREAKOUT and None not in highs else None
    relative = None
    endpoints = []
    if completed and len(rows) > config.BENCHMARK_LOOKBACK:
        start = rows[-config.BENCHMARK_LOOKBACK-1]
        endpoints = [benchmark[day] for day in (start['session'], current['session']) if day in benchmark]
        if len(endpoints) == 2 and all(row['close'] is not None for row in (start, current, *endpoints)):
            relative = current['close'] / start['close'] - endpoints[1]['close'] / endpoints[0]['close']
    return {'atr': None if atr_value is None else float(atr_value), 'rsi': rsi, 'prior_rsi': prior_rsi,
            'cloud': _cloud(bars), 'prior_cloud': _cloud(bars[:-1]), 'volume': volume,
            'previous_volume': previous_volume, 'alternate_volume': alternatives, 'prior_high': prior_high,
            'relative': relative, 'benchmark_endpoints': endpoints,
            'previous_high': rows[-2]['high'] if completed and len(rows) > 1 else None}


@dataclass
class _Setup:
    session: str
    level: float
    bar_high: float | None
    rsi: float | None
    elapsed: int = 0
    touched: bool = False
    pullback_low: float | None = None
    best_touch: float | None = None
    levels_touched: set = field(default_factory=set)
    previous_rsis: list = field(default_factory=list)
    previous_volumes: list = field(default_factory=list)


def _rule(condition, value, reference=None):
    return {'state': 'NO_DATA' if condition is None else 'PASS' if condition else 'FAIL',
            'value': value, 'reference': reference}


def _compare(left, right, predicate):
    return None if left is None or right is None else predicate(left, right)


def _rank(components, weights):
    enabled = {label: value for label, value in components.items() if value is not None and weights[label] > 0}
    if not enabled:
        return None
    return round(100 * sum(value * weights[label] for label, value in enabled.items()) /
                 sum(weights[label] for label in enabled), 8)


def _score(setup, state, rules, features, config):
    rsi, volume, relative = (features[name] for name in ('rsi', 'volume', 'relative'))
    prior_rsi, prior_volume = features['prior_rsi'], features['previous_volume']
    cloud, prior_cloud = features['cloud'], features['prior_cloud']
    return {
        'structure': 0 if state == 'INVALIDATED' else setup.best_touch if setup else None,
        'trend': ((rules['cloud']['state'] == 'PASS') + (cloud > prior_cloud)) / 2
        if None not in (cloud, prior_cloud) and rules['cloud']['state'] != 'NO_DATA' else None,
        'momentum': ((min(setup.previous_rsis) < setup.rsi)
                     + (rsi > prior_rsi and config.RSI_MIN <= rsi <= config.RSI_MAX)) / 2
        if setup and setup.previous_rsis and None not in (setup.rsi, rsi, prior_rsi, *setup.previous_rsis) else None,
        'volume': ((min(setup.previous_volumes) < config.VOL_MIN)
                   + (volume >= config.VOL_MIN and volume > prior_volume)) / 2
        if setup and setup.previous_volumes and None not in (volume, prior_volume, *setup.previous_volumes) else None,
        'relative_strength': min(1, max(0, relative / config.RELATIVE_SCORE_SCALE))
        if relative is not None else None,
    }


def _advance(setup, row, values, config, touch_mode):
    close, low, rsi, volume = row['close'], row['low'], values['rsi'], values['volume']
    relative, cloud, atr_value = values['relative'], values['cloud'], values['atr']
    prior_high, previous_high = values['prior_high'], values['previous_high']
    rules = {
        'breakout': _rule(_compare(close, prior_high, gt), close, prior_high),
        'hold': _rule(None, close), 'touch': _rule(None, low),
        'resumption': _rule(_compare(close, previous_high, gt), close, previous_high),
        'rsi': _rule(None if rsi is None else config.RSI_MIN <= rsi <= config.RSI_MAX,
                     rsi, (config.RSI_MIN, config.RSI_MAX)),
        'volume': _rule(_compare(volume, float(config.VOL_MIN), ge), volume, config.VOL_MIN),
        'cloud': _rule(_compare(close, cloud, gt), close, cloud),
        'relative_strength': _rule(_compare(relative, float(config.MIN_EXCESS_RETURN), gt),
                                   relative, config.MIN_EXCESS_RETURN),
    }
    if setup is None:
        if rules['breakout']['state'] == 'PASS':
            return _Setup(row['session'], prior_high, row['high'], rsi), 'BREAKOUT_SEEN', rules
        return None, 'WATCHING', rules

    setup.elapsed += 1
    if low is not None:
        setup.pullback_low = low if setup.pullback_low is None else min(setup.pullback_low, low)
    levels = {'breakout_level': setup.level, **({'cloud_top': cloud} if cloud is not None else {})}
    if touch_mode == 'PERCENT':
        buffer = config.PB_BUFFER_PCT * setup.level
        tolerances = {label: level * config.PB_TOUCH_PCT for label, level in levels.items()}
    else:
        buffer = config.PB_BUFFER_ATR * atr_value if atr_value is not None else None
        tolerances = {label: config.PB_TOUCH_ATR * atr_value for label in levels} if atr_value is not None else {}
    floor = setup.level - buffer if buffer is not None else None
    hold = _compare(close, floor, ge)
    eligible = {label: abs(low - levels[label]) for label in tolerances} if low is not None else {}
    touches = {label: 1 - distance / tolerances[label] if tolerances[label] else 1.0
               for label, distance in eligible.items() if distance <= tolerances[label]}
    rules['hold'] = _rule(hold, close, floor)
    rules['touch'] = _rule(bool(touches) if eligible else None, low, levels)
    if hold is False:
        return setup, 'INVALIDATED', rules

    was_touched = setup.touched
    if hold is True and touches:
        setup.touched = True
        setup.levels_touched.update(touches)
        setup.best_touch = max(*touches.values(), setup.best_touch or 0)
    if (was_touched and hold is True and rules['resumption']['state'] == 'PASS'
            and all(rules[name]['state'] != 'FAIL' for name in ('rsi', 'volume', 'cloud', 'relative_strength'))):
        return setup, 'TRIGGERED', rules
    if setup.elapsed >= config.W_PULLBACK:
        return setup, 'EXPIRED', rules
    return setup, 'IN_PULLBACK_ZONE' if setup.touched else 'BREAKOUT_SEEN', rules


def _quality(row, gaps, features, short_history, config):
    if any(gap['missing_sessions'] is None or len(gap['missing_sessions']) > config.MAX_GAP_SESSIONS for gap in gaps):
        return 'PARTIAL'
    if gaps:
        return 'GAP_TOLERATED'
    if (short_history or any(row[field] is None for field in _FIELDS)
            or any(item.get('state') == 'CONFLICT_NO_CONSENSUS' for item in row['input_receipts'].values())
            or any(features[name] is None for name in ('atr', 'rsi', 'volume', 'cloud', 'relative'))):
        return 'PARTIAL'
    if any(item.get('state') == 'SINGLE_SOURCE' for item in row['input_receipts'].values()):
        return 'SINGLE_SOURCE'
    return 'CONFIRMED'


def evaluate(instrument, rows, benchmark_rows, *, as_of, benchmark=None, config=Settings(), touch_mode='ATR',
             retrospective=False):
    """Use selected Zebra rows, preserving receipt dates and immutable setup state.

    Default decisions filter every field at the session decision clock.
    Retrospective mode is explicit and admits only receipts known at as_of.
    """
    as_of = _time(as_of)
    if touch_mode not in ('ATR', 'PERCENT'):
        raise ValueError('Unknown touch variant')
    rows = _ordered(rows, as_of)
    benchmark_rows = _ordered(benchmark_rows, as_of)
    if retrospective:
        share_at_cutoff = {row['session']: _choose_row(row, as_of) for row in rows}
        benchmark_at_cutoff = {row['session']: _choose_row(row, as_of) for row in benchmark_rows}
    setup = None
    observations = []
    for index, record in enumerate(rows):
        decision = _clock(record['session'])
        cutoff = as_of if retrospective else decision
        if retrospective:
            share = [selected for item in rows[:index+1]
                     if (selected := share_at_cutoff[item['session']]) is not None]
        else:
            share = [selected for item in rows[:index+1] if (selected := _choose_row(item, cutoff)) is not None]
        if not share or share[-1]['session'] != record['session']:
            continue
        observed = share[-1]
        window, gaps = _scan_windows(share, config)
        reference = {}
        if len(window) > config.BENCHMARK_LOOKBACK:
            days = {window[-config.BENCHMARK_LOOKBACK-1]['session'], observed['session']}
            reference = {item['session']: selected for item in benchmark_rows if item['session'] in days
                         and (selected := (benchmark_at_cutoff[item['session']] if retrospective
                                          else _choose_row(item, cutoff))) is not None}
        span = max(_CLOUD_BARS, config.N_BREAKOUT+1, config.N_VOLUME+2, config.BENCHMARK_LOOKBACK+1,
                   config.RSI_PERIOD+2, config.ATR_PERIOD+1)
        horizon_start = share[max(0, len(share)-span)]['session']
        gaps = [gap for gap in gaps if gap['before'] >= horizon_start]
        features = _features(window, reference, config)
        setup, state, rules = _advance(setup, observed, features, config, touch_mode)
        # Price the stop only from observed lows and trigger-time ATR.
        stop = target = None
        close = observed['close']
        if state == 'TRIGGERED':
            visible_lows = [item['low'] for item in share if item['session'] > setup.session and item['low'] is not None]
            setup.pullback_low = min(visible_lows, default=None)
        if state == 'TRIGGERED' and setup.pullback_low is not None and features['atr'] is not None:
            candidate = setup.pullback_low - config.STOP_ATR_BUFFER * features['atr']
            if 0 < candidate < close:
                stop = candidate
                target = close + config.TARGET_R * (close - stop)
        if setup and setup.elapsed and state != 'TRIGGERED':
            setup.previous_rsis.append(features['rsi'])
            setup.previous_volumes.append(features['volume'])
        components = _score(setup, state, rules, features, config)
        weights = config.weights()
        low_confidence = len(window) < max(config.MIN_BARS, config.N_BREAKOUT+1)
        remaining = max(0, config.W_PULLBACK - setup.elapsed) if setup else None
        terminal = state in ('TRIGGERED', 'EXPIRED', 'INVALIDATED')
        projected_end = _project_end(observed['session'], remaining) if remaining is not None and not terminal else None
        window_end = observed['session'] if terminal else projected_end
        observations.append({
            'instrument': instrument, 'session': observed['session'], 'decision_at': decision.isoformat(),
            'state': state, 'breakout_date': setup.session if setup else None, 'breakout_level': setup.level if setup else None,
            'breakout_bar_high': setup.bar_high if setup else None, 'pullback_low': setup.pullback_low if setup else None,
            'touch_levels': sorted(setup.levels_touched) if setup else [], 'windows_elapsed': setup.elapsed if setup else None,
            'sessions_left': 0 if terminal else remaining, 'window_ends': window_end,
            'window_end_basis': 'TERMINAL_SESSION' if terminal else 'PROJECTED_JSE_CALENDAR' if projected_end else None,
            'stop_reference': stop, 'target_reference': target, 'rules': rules,
            'rules_evaluable': sum(rule['state'] != 'NO_DATA' for rule in rules.values()),
            'score': _rank(components, weights),
            'equal_weight_score': _rank(components, dict.fromkeys(components, 1)),
            'score_components': components, 'components_evaluable': sum(value is not None for value in components.values()),
            'data_quality': _quality(observed, gaps, features, low_confidence, config), 'low_confidence': low_confidence,
            'gaps': gaps, 'missing_context': [name for name in ('atr', 'rsi', 'volume', 'cloud', 'relative')
                                              if features[name] is None],
            'volume_source': observed['volume_source'], 'alternate_volume': features['alternate_volume'],
            'input_receipts': observed['input_receipts'], 'benchmark': benchmark,
            'benchmark_inputs': [{'session': item['session'], 'close': item['input_receipts'].get('close')}
                                 for item in features['benchmark_endpoints']],
            'note': 'Trigger retained without a replayable stop reference.' if state == 'TRIGGERED' and stop is None
            else 'Completed daily research rank. No execution authority.',
        })
        if terminal:
            setup = None
    return {'strategy_id': REFERENCE.strategy_profile_id, 'strategy_version': REFERENCE.strategy_profile_version,
            'instrument': instrument, 'as_of': as_of.isoformat(), 'research_only': True, 'live_execution': False,
            'availability_basis': 'RECONSTRUCTED_AT_RETAINED_CUTOFF' if retrospective else 'RECEIPTS_BY_DECISION',
            'parameters': asdict(config), 'touch_mode': touch_mode, 'observations': observations}


def _ordered(rows, as_of):
    result = sorted((row for row in rows if _clock(row['session']) <= as_of
                     and _session(date.fromisoformat(row['session'])) is not False),
                    key=lambda row: row['session'])
    if len({row['session'] for row in result}) != len(result):
        raise ValueError('One selected record per completed session required')
    return result


def _project_end(session, remaining):
    for _ in range(remaining):
        session = next_session(session)
        if session is None:
            break
    return session


def replay_setups(result, manifest, *, horizon, initial_cash, max_notional, risk_budget, costs):
    """Pass qualified signals to the existing engine, with execution coverage separate."""
    from domain.backtest.component_engine import CashEquity, Signal, replay

    params = result['parameters']
    if (type(horizon) is not int or not params['HOLD_MIN'] <= horizon <= params['HOLD_MAX']
            or result['instrument'] != manifest.instrument):
        raise ValueError('Aligned instrument and configured replay horizon required')
    by_session = {bar.session: bar for bar in manifest.bars}
    if not by_session:
        return {'state': 'REPLAY_INPUT_UNAVAILABLE', 'reason': 'No native execution bars.',
                'unreplayed_triggers': sum(row['state'] == 'TRIGGERED' for row in result['observations'])}
    first, last = min(by_session), max(by_session)
    observations = [row for row in result['observations'] if first <= row['session'] <= last]
    uncovered = sorted({row['session'] for row in observations} - by_session.keys())
    if uncovered:
        return {'state': 'REPLAY_INPUT_UNAVAILABLE', 'reason': 'Native execution bars omit observed sessions.',
                'uncovered_sessions': uncovered,
                'unreplayed_triggers': sum(row['state'] == 'TRIGGERED' for row in result['observations'])}
    try:
        CashEquity().validate(manifest)
        manifest.admit(first, last, _time(result['as_of']), activity_required=True)
    except (ValueError, TypeError, ArithmeticError) as exc:
        return {'state': 'REPLAY_INPUT_UNAVAILABLE', 'reason': str(exc),
                'unreplayed_triggers': sum(row['state'] == 'TRIGGERED' for row in result['observations'])}

    signals = []
    for row in observations:
        if row['state'] != 'TRIGGERED' or row['stop_reference'] is None:
            continue
        clock = _time(row['decision_at'])
        if by_session[row['session']].available_at > clock:
            continue
        signals.append(Signal(f"{manifest.instrument}-{row['session']}", manifest.instrument, row['session'],
                              clock, row['stop_reference'], max_notional, risk_budget, horizon=horizon,
                              target_r=params['TARGET_R'], strategy_profile_id=REFERENCE.strategy_profile_id,
                              strategy_profile_version=REFERENCE.strategy_profile_version))
    evaluated = replay([manifest], signals, as_of=_time(result['as_of']), initial_cash=initial_cash, costs=costs)
    return {'state': 'RESEARCH_REPLAY', 'signals': [signal.id for signal in signals],
            'unreplayed_triggers': sum(row['state'] == 'TRIGGERED' for row in result['observations']) - len(signals),
            'availability_basis': result['availability_basis'], **evaluated}
