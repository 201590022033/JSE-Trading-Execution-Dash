"""Adapt supported exact daily strategy contracts to immutable Lab results."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from application.opportunities.session_freshness import latest_expected_session
from application.opportunities.zebra_screen_data import load_zebra_screen_data
from application.opportunities.zebra_instruments import mappings
from application.opportunities.research_classification import classifications
from application.strategy_radar.exact_daily_review import PROFILE, WARMUP, _qualified
from application.strategy_radar.swing_radar import _FEATURE_PROFILE_VERSION, _FIELDS, _NAMES, snapshot
from domain.backtest import engine as lab_engine
from domain.backtest.component_engine import Costs, Signal, replay
from domain.strategy import DEFAULT_STRATEGY_REGISTRY

from . import zebra_field_windows as benchmarks
from .components import Components, evaluate as evaluate_component, signal_for
from .observed_history import from_chart
from .strategies import PROFILES


EXACT_IDENTITY = PROFILE, _FEATURE_PROFILE_VERSION
COMPONENT = Components()
COMPONENT_IDENTITY = COMPONENT.profile_id, COMPONENT.profile_version
LAB_IDENTITIES = {(identity, version): key for key, _, identity, version in PROFILES}
SUPPORTED_IDENTITIES = {EXACT_IDENTITY, COMPONENT_IDENTITY, *LAB_IDENTITIES}
EXACT_REQUEST = 'exact-daily-backtest-v1'
FIELDS = ('instrument', 'family', 'strategy_id', 'strategy_version', 'product', 'timeframe',
          'first_session', 'last_session', 'request_id')
INITIAL_CASH = 1000000
MAX_NOTIONAL = 100000
RISK_BUDGET = 5000
LAB_MAX_NOTIONAL = 420000
LAB_RISK_BUDGET = 12000
HORIZON = 3
TARGET_R = Decimal(2)
COSTS = Costs(fee_bps=8, minimum_fee=60, spread_bps=20, slippage_bps=5)
TRACE_NAMES = ('EMA trend', 'Breakout or EMA reclaim', 'Wilder RSI', 'Relative volume', 'Benchmark return',
               'Research stop reference')
MIN_SAMPLE_TRADES = 30


class RunUnavailable(ValueError):
    """A bounded explanation that can be returned to the local operator."""


def dependency_reason():
    if not all(callable(getattr(benchmarks, name, None)) for name in ('research_benchmarks', 'benchmark_input_keys')):
        return 'The B04 benchmark policy must be installed before this exact replay is available.'
    return None


def _unsupported(profile):
    if profile.decision_timeframe != '1d' or 'JSE_CASH_EQUITIES' not in profile.universe_scope:
        return 'This profile has no compatible daily cash-share replay.'
    capability_ids = {capability.capability_id for capability in profile.capabilities}
    if 'daily_shadow_policy' in capability_ids:
        return 'This version has a per-signal shadow comparison without a compatible portfolio replay.'
    if 'swing_technical_horizons' in capability_ids:
        return 'This version has a technical trace or forward labels without a retained exact fill replay contract.'
    if 'canonical_research' in capability_ids:
        return 'This version belongs to the canonical ranking or paper workflow without an exact Lab replay.'
    return 'This strategy version has no compatible adapter in this Lab replay runner.'


def available_profiles():
    result = []
    dependency = dependency_reason()
    for profile in DEFAULT_STRATEGY_REGISTRY.registered_profiles():
        identity = profile.reference.strategy_profile_id, profile.reference.strategy_profile_version
        reason = dependency if identity in SUPPORTED_IDENTITIES else _unsupported(profile)
        result.append({'id': identity[0], 'version': identity[1], 'name': profile.display_name,
                       'available': reason is None, 'reason': reason})
    return sorted(result, key=lambda item: (not item['available'], item['id'], item['version']))


def replay_instruments(root):
    """List recognized cash shares; the worker validates their retained bars."""
    from market_chart_registry import MARKET_CHART_INSTRUMENTS

    codes = mappings(Path(root) / 'runtime/local-swing-data/radar-public-prices')
    labels = classifications(codes)['instruments']
    return [
        {'instrument': key, 'symbol': symbol}
        for key, symbol in codes.items()
        if (MARKET_CHART_INSTRUMENTS[key].asset_class == 'cash_equity'
            if key in MARKET_CHART_INSTRUMENTS
            else 'ETF' not in labels.get(key, {}).get('industry', '').upper())
    ]


def validate_request(body, service):
    if not isinstance(body, dict) or set(body) != set(FIELDS) or any(not isinstance(body[key], str) for key in FIELDS):
        raise RunUnavailable('Supply the share, family, exact strategy version, product, timeframe and date range.')
    if not re.fullmatch(r'[A-Z0-9_]{2,16}', body['instrument']) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', body['request_id']):
        raise RunUnavailable('Use a research share code and a valid request ID.')
    identity = body['strategy_id'], body['strategy_version']
    try:
        DEFAULT_STRATEGY_REGISTRY.resolve(*identity)
    except KeyError:
        raise RunUnavailable('That strategy ID and version are not registered.') from None
    if identity not in SUPPORTED_IDENTITIES or (body['product'], body['timeframe']) != ('CASH_SHARE', '1d'):
        raise RunUnavailable('That exact identity has no supported cash-share daily replay.')
    if body['family'] != 'H1':
        raise RunUnavailable('This exact setup replay implements H1 selected-share research.')
    try:
        first, last = (date.fromisoformat(body[key]).isoformat() for key in ('first_session', 'last_session'))
    except ValueError:
        raise RunUnavailable('Use valid start and end dates.') from None
    if (first, last) != (body['first_session'], body['last_session']) or first > last:
        raise RunUnavailable('Use an ordered start and end date in YYYY-MM-DD format.')
    latest = latest_expected_session(service.clock())
    if not latest or last > latest:
        raise RunUnavailable('End the range on or before the latest completed session in the reviewed JSE calendar.')
    reason = dependency_reason()
    if reason:
        raise RunUnavailable(reason)
    if not any(item['instrument'] == body['instrument'] for item in replay_instruments(service.root)):
        raise RunUnavailable('Select a recognized Zebra cash share. Saved results can use a different instrument code.')
    return dict(body)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _inputs(item, last, as_of):
    dates = Counter(row['session'] for row in item['rows'] if row['session'] <= last)
    qualified, lineage, partial = [], {}, set()
    for row in sorted(item['rows'], key=lambda row: row['session']):
        day = row['session']
        if day > last:
            break
        fields = row.get('fields', {})
        if dates[day] != 1:
            partial.add(day)
            continue
        lineage[day] = fields
        clock = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        if clock + timedelta(days=1, seconds=1) > as_of:
            partial.add(day)
            continue
        allowed = {key: _qualified(fields.get(key) or {}, clock + timedelta(hours=15), as_of,
                                   allow_zero=key == 'volume')[1] is not None for key in _FIELDS}
        if not all(allowed.values()):
            partial.add(day)
            continue
        bar = {'timestamp': day, '_source': fields['close']['source'],
               **{key: float(fields[key]['value']) for key in _FIELDS}}
        if not bar['low'] <= min(bar['open'], bar['close']) <= max(bar['open'], bar['close']) <= bar['high']:
            partial.add(day)
            continue
        qualified.append(bar)
    return qualified, lineage, partial


def replay_history(service, instrument):
    """Describe the same qualified share bars that the replay runner uses."""
    now = service.clock()
    last = latest_expected_session(now)
    if not last:
        raise RunUnavailable('The latest completed JSE session is unavailable.')
    item = load_zebra_screen_data(service.root, now=now, instruments={instrument})['instruments'].get(instrument)
    if item is None or item.get('asset_class') != 'cash_equity':
        raise RunUnavailable('No eligible retained Zebra cash-share history was found for this share.')
    bars, _, partial = _inputs(item, last, now)
    if not bars:
        raise RunUnavailable('No qualified retained daily OHLCV bars are available for this share.')
    return {
        'instrument': instrument,
        'first_session': bars[0]['timestamp'],
        'last_session': bars[-1]['timestamp'],
        'qualified_sessions': len(bars),
        'unqualified_observed_sessions': len(partial),
        'close_sources': sorted({bar['_source'] for bar in bars}),
    }


def _radar_trace(instrument, history, benchmark, reference, clock):
    chart = {'symbol': instrument, 'interval': '1d', 'currency': 'ZAR', 'bars': history}
    benchmark_chart = {'symbol': benchmark, 'interval': '1d', 'currency': 'ZAR', 'bars': reference}
    result = snapshot(chart, evaluated_at=clock, benchmark_chart=benchmark_chart,
                      feature_profile_version=_FEATURE_PROFILE_VERSION)
    conditions = result.get('conditions', {})
    breakout, reclaim = (conditions.get(name) for name in ('breakout20', 'ema20_reclaim'))
    entry = True if breakout is True or reclaim is True else (
        False if breakout is False and reclaim is False else None)
    geometry = result.get('geometry', {})
    values = [conditions.get('ema_uptrend'), entry, conditions.get('rsi_50_70'),
              conditions.get('volume_above_prior20'), conditions.get('outperforming_benchmark20'),
              True if geometry.get('state') == 'SHADOW_REFERENCE' else None]
    definitions = (_NAMES[0][1], 'Either exact-profile entry rule passes', _NAMES[3][1], _NAMES[4][1],
                   _NAMES[5][1], 'Existing shadow geometry available')
    trace = [{'c': label, 't': definition, 'ok': value is True,
              'v': 'NO_DATA' if value is None else ('PASS' if value else 'FAIL')}
             for label, definition, value in zip(TRACE_NAMES, definitions, values)]
    return trace, geometry.get('stop'), conditions.get('core_setup') is True, any(v is None for v in values)


def _signals(instrument, bars, start, matches, series, identity):
    traces, rejected, signals = [], [], []
    checked = unknown = 0
    condition_names, funnel = [], []
    legacy_lab = identity in LAB_IDENTITIES
    for index, bar in enumerate(bars):
        day = bar['timestamp']
        if day < start:
            continue
        checked += 1
        history = bars[max(0, index + 1 - WARMUP):index + 1] if identity == EXACT_IDENTITY else bars[:index + 1]
        benchmark = matches[day]['instrument']
        benchmark_series = series.get(benchmark, {})
        reference = [
            {'timestamp': row['timestamp'], 'close': benchmark_series[row['timestamp']]['close']}
            for row in history if row['timestamp'] in benchmark_series
            and benchmark_series[row['timestamp']]['close'] is not None
        ]
        clock = datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(days=1, seconds=1)
        if identity == EXACT_IDENTITY:
            trace, stop, passed, unavailable = _radar_trace(instrument, history, benchmark, reference, clock)
        else:
            charts = {instrument: history, 'ETF_STX40': reference}
            evaluator_index = len(history) - 1
            if legacy_lab:
                trace, stop = benchmarks.evaluate_mixed(LAB_IDENTITIES[identity], instrument, evaluator_index, charts)
                unavailable = not trace or any(
                    row['c'] == 'Benchmark' and row['v'] is None for row in trace)
            else:
                trace, stop = evaluate_component(COMPONENT, instrument, evaluator_index, charts)
                unavailable = not trace or any(row['state'] == 'UNKNOWN' for row in trace)
            passed = bool(trace) and all(row['ok'] for row in trace) and stop is not None
        if unavailable:
            unknown += 1
        names = [row['c'] for row in trace]
        if names and len(names) > len(condition_names):
            condition_names, funnel = names, [0] * len(names)
        if names == condition_names:
            for i, row in enumerate(trace):
                if not row['ok']:
                    break
                funnel[i] += 1
        if not passed:
            rejected.append({'inst': instrument, 'session': day, 'trace': trace})
            continue
        signal_id = f'{instrument}-{day}'
        if identity == COMPONENT_IDENTITY:
            signal = signal_for(COMPONENT, instrument, day, clock, stop)
        else:
            maker = lab_engine.Signal if legacy_lab else Signal
            signal = maker(signal_id, instrument, day, clock, Decimal(str(stop)),
                           Decimal(LAB_MAX_NOTIONAL if legacy_lab else MAX_NOTIONAL),
                           Decimal(LAB_RISK_BUDGET if legacy_lab else RISK_BUDGET),
                           horizon=HORIZON, target_r=TARGET_R,
                           strategy_profile_id=identity[0], strategy_profile_version=identity[1])
        signals.append(signal)
        traces.append({'id': signal_id, 'inst': instrument, 'session': day, 'stop': stop, 'trace': trace})
    return signals, traces, rejected, condition_names, {'checked': checked, 'passed': funnel}, unknown


def build_run(spec, instruments, as_of):
    """Build an immutable-format report from retained inputs and the existing engine."""
    instrument = spec['instrument']
    item = instruments.get(instrument)
    if item is None or item.get('asset_class') != 'cash_equity':
        raise RunUnavailable('No eligible retained Zebra cash-share history was found for this share.')
    start, last = spec['first_session'], spec['last_session']
    identity = spec['strategy_id'], spec['strategy_version']
    legacy_lab = identity in LAB_IDENTITIES
    if identity == EXACT_IDENTITY:
        risk_budget, notional, horizon, target_r = RISK_BUDGET, MAX_NOTIONAL, HORIZON, TARGET_R
        source = 'Exact daily Radar setup trace with the labelled research benchmark'
    elif identity == COMPONENT_IDENTITY:
        risk_budget, notional, horizon, target_r = (COMPONENT.risk_budget, COMPONENT.max_notional,
                                                   COMPONENT.horizon, COMPONENT.target_r)
        source = 'Pinned baseline Swing component configuration'
    else:
        risk_budget, notional, horizon, target_r = LAB_RISK_BUDGET, LAB_MAX_NOTIONAL, HORIZON, TARGET_R
        source = 'Existing Zebra mixed-source Lab evaluator'
    bars, lineage, partial = _inputs(item, last, as_of)
    in_scope = [bar for bar in bars if bar['timestamp'] >= start]
    if not in_scope:
        raise RunUnavailable('No qualified retained daily OHLCV bars in the requested date range. Choose a range with usable history.')
    warmup = [bar for bar in bars if bar['timestamp'] < start]
    if identity == EXACT_IDENTITY:
        warmup = warmup[-(WARMUP - 1):]
    bars = warmup + in_scope
    sessions = [bar['timestamp'] for bar in bars]
    assignments, references = benchmarks.research_benchmarks(instrument, instruments, sessions, lookback=20)
    signals, traces, rejected, names, funnel, unknown = _signals(instrument, bars, start, assignments, references, identity)
    session_set = set(sessions)
    used_lineage = {day: fields for day, fields in lineage.items() if day in session_set or start <= day <= last}
    source_hash = sha256(_json(used_lineage)).hexdigest()
    receipts = [{'instrument': instrument, 'product': 'cash_equity', 'provider': 'ZEBRA_SELECTED_FIELDS',
                 'source_sha256': source_hash, 'acquired_at': as_of.isoformat(),
                 'hash_basis': 'CANONICAL_FIELD_LINEAGE_PACKET_NOT_RAW_PROVIDER_BYTES'}] if in_scope else []
    manifests = [from_chart(instrument, {'bars': in_scope, 'provenance': receipts[0]})] if in_scope else []
    costs = lab_engine.Costs(fee_bps=COSTS.fee_bps, minimum_fee=COSTS.minimum_fee,
                             spread_bps=COSTS.spread_bps, slippage_bps=COSTS.slippage_bps) if legacy_lab else COSTS
    runner = lab_engine.replay if legacy_lab else replay
    run = runner(manifests, signals, as_of=as_of, initial_cash=Decimal(INITIAL_CASH), costs=costs)
    equity, trades = run['equity'], run['trades']
    peak = INITIAL_CASH
    drawdown = 0
    for entry in equity:
        amount = float(entry['equity'])
        peak = max(peak, amount)
        drawdown = min(drawdown, amount / peak - 1)
    last_equity = float(equity[-1]['equity']) if equity else INITIAL_CASH
    segments = benchmarks.valid_segments(
        [{'session': row['timestamp'], **{key: row[key] for key in _FIELDS}} for row in in_scope], _FIELDS)
    gaps = len(segments) > 1 or any(start <= day <= last for day in partial)
    states = {field.get('state') for day, fields in used_lineage.items() if start <= day <= last
              for field in fields.values() if isinstance(field, dict)}
    if gaps:
        quality = 'GAP_TOLERATED'
    elif unknown or not in_scope or 'CONFLICT_NO_CONSENSUS' in states:
        quality = 'PARTIAL'
    elif 'SINGLE_SOURCE' in states:
        quality = 'SINGLE_SOURCE'
    else:
        quality = 'CONFIRMED'
    benchmark_days = {bar['timestamp']: assignments[bar['timestamp']] for bar in in_scope}
    benchmark_lineage_keys = set()
    for choice in benchmark_days.values():
        if choice.get('members'):
            benchmark_lineage_keys.update(choice['members'])
        elif choice['instrument']:
            benchmark_lineage_keys.add(choice['instrument'])
    benchmark_lineage = {key: {r['session']: r.get('fields', {}).get('close')
                               for r in instruments.get(key, {}).get('rows', [])
                               if sessions and sessions[0] <= r['session'] <= last}
                         for key in sorted(benchmark_lineage_keys)}
    report_bars = {instrument: [[row['timestamp'], row['open'], row['high'], row['low'], row['close']]
                                for row in in_scope]}
    profile = DEFAULT_STRATEGY_REGISTRY.resolve(*identity)
    strategies = [{
        'id': LAB_IDENTITIES.get(identity, 'swing_component' if identity == COMPONENT_IDENTITY else 'exact_daily_radar'),
        'name': profile.display_name,
        'strategy_profile_id': identity[0], 'strategy_profile_version': identity[1], 'timeframe': '1d',
        'source': source, 'desc': 'Retrospective close-proxy fills with recorded research replay assumptions.',
        'conds': names, 'funnel': funnel, 'engine_config_hash': run['config_hash'],
        'sum': {
            'signals': len(signals), 'traded': len(trades),
            'win': round(sum(float(trade['net_pnl']) > 0 for trade in trades) / len(trades) * 100) if trades else None,
            'net': round(last_equity - INITIAL_CASH, 2), 'mdd': round(drawdown * 100, 2),
            'stocks': len({trade['instrument'] for trade in trades}),
            'verdict': 'Fewer than 30 closed trades. Evidence is inconclusive.' if len(trades) < MIN_SAMPLE_TRADES else
                       'Descriptive research evidence.',
        },
        'run': {'signals': traces, 'rejected_bars': rejected, 'decisions': run['decisions'],
                'trades': trades, 'equity': equity},
    }]
    meta = {
        'grade': 'ASSUMPTION_LIMITED', 'data_basis': 'ZEBRA_EXACT_DAILY_RESEARCH', 'data_quality': quality,
        'created_at': as_of.isoformat(), 'created_at_basis': 'RUN_CAPTURE_CLOCK', 'live_execution': False,
        'hypothesis_family': spec['family'], 'requested_date_range': [start, last],
        'cost_basis': costs.basis, 'initial_cash': INITIAL_CASH,
        'replay_assumptions': {
            'initial_cash_zar': INITIAL_CASH, 'max_notional_zar': notional, 'risk_budget_zar': risk_budget,
            'horizon_observed_sessions': horizon, 'target_r': str(target_r),
            'fee_bps_per_side': str(costs.fee_bps), 'minimum_fee_zar': str(costs.minimum_fee),
            'spread_bps': str(costs.spread_bps), 'slippage_bps_per_side': str(costs.slippage_bps),
        },
        'coverage': {instrument: {'observed_sessions': len(in_scope),
                                  'longest_contiguous_sessions': max(map(len, segments), default=0),
                                  'contiguous_segment_lengths': [len(segment) for segment in segments],
                                  'unqualified_observed_sessions': len({day for day in partial if start <= day <= last}),
                                  'no_data_decisions': unknown, 'warmup_observed_sessions': len(warmup)}},
        'source_receipts': receipts, 'field_lineage': {instrument: used_lineage},
        'benchmark_close_lineage': benchmark_lineage,
        'sector_benchmarks_by_session': {instrument: benchmark_days},
        'sector_benchmarks': {instrument: benchmark_days[in_scope[-1]['timestamp']]} if in_scope else {},
        'limitations': ['HYPOTHETICAL_CLOSE_PROXY_FILLS', 'EXACT_ENTRY_TRACE_WITH_RESEARCH_EXIT_ASSUMPTIONS',
                        'RECONSTRUCTED_HISTORICAL_AVAILABILITY', 'OBSERVED_BARS_ONLY_GAPS_CAN_HIDE_STOPS',
                        'UNVERIFIED_CORPORATE_ACTION_BASIS', f'SOURCE_QUALITY_{quality}'] +
                       (['SMALL_SAMPLE_FEWER_THAN_30_CLOSED_TRADES'] if len(trades) < MIN_SAMPLE_TRADES else []),
    }
    result = {'meta': meta, 'bars': report_bars, 'strategies': strategies}
    meta['config_hash'] = sha256(_json(result)).hexdigest()
    return result


def publish(folder, run):
    """Publish fully written bytes with exclusive, atomic re-upload semantics."""
    folder.mkdir(parents=True, exist_ok=True)
    digest = run['meta']['config_hash']
    path = folder / (digest + '.json')
    raw = _json(run) + b'\n'
    if len(raw) > 64_000_000:
        raise RunUnavailable('The retained result exceeds the Lab size limit. Choose a shorter date range.')
    with NamedTemporaryFile(dir=folder, suffix='.partial', delete=False) as pending:
        temporary = Path(pending.name)
        try:
            pending.write(raw)
            pending.close()
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise RunUnavailable('A conflicting result already exists for this evidence hash.')
        finally:
            pending.close()
            temporary.unlink(missing_ok=True)
    return digest


def run_job(service, spec):
    reason = dependency_reason()
    if reason:
        raise RunUnavailable(reason)
    destination = os.environ.get('LOCAL_BACKTEST_REPORT_DIR')
    if not destination:
        raise RunUnavailable('The dashboard saved-results folder is not configured.')
    now = service.clock()
    keys = benchmarks.benchmark_input_keys(service.root, {spec['instrument']})
    instruments = load_zebra_screen_data(service.root, now=now, instruments=keys)['instruments']
    run = build_run(spec, instruments, now)
    return publish(Path(destination) / 'lab', run)
