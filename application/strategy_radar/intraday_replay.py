"""Point-in-time, descriptive next-bar shadow replay for intraday profiles.

No broker, provider, scheduler or model operations. This is not a fill simulation,
profit forecast, strategy promotion or evidence of profitable execution.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

from .intraday_store import _time, merge_bars, normalize_bar

PROFILES = {'intraday_5m_research_v1': (5, '1.0.0'),
            'intraday_30m_research_v1': (30, '1.0.0')}


def _number(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _inputs_digest(records):
    raw = json.dumps(records, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return sha256(raw).hexdigest()


def replay_intraday(profile_id, instrument, records, *, round_trip_cost_bps=0,
                    benchmark_records=(), daily_gate=None, evaluator=None, as_of=None):
    """Evaluate as receipts arrive, then compare with a next-bar baseline.

    For every source-verified closed bar, decision is the earliest actual
    receipt at/after its end. No later receipt or correction enters that
    decision. Outcomes use the first eligible subsequent bar's observed open/close
    after it closes; that bar must begin no earlier than the decision, with an
    intervening bar retained when receipt arrives after the immediate start. Thus a late receipt never creates a retrospective entry.
    Baseline measures all eligible bars; candidate measures ENTRY_MET bars on
    the same outcome definition. Cost is an explicit hypothetical round trip.
    """
    if profile_id not in PROFILES:
        raise ValueError('unknown intraday strategy')
    interval, version = PROFILES[profile_id]
    if not isinstance(instrument, str) or not instrument:
        raise ValueError('instrument required')
    try:
        cost = Decimal(str(round_trip_cost_bps))
    except InvalidOperation:
        raise ValueError('finite nonnegative cost required')
    if not cost.is_finite() or cost < 0 or cost > 10000:
        raise ValueError('finite nonnegative cost within 10000 bps required')
    cutoff = _time(as_of if as_of is not None else datetime.now(timezone.utc))
    raw = list(records)
    benchmark = list(benchmark_records)
    parameters = {'lookback_contiguous_bars': 4, 'entry': 'close_above_previous_high',
                  'trend': 'close_above_mean_prior_3', 'momentum': 'close_above_previous_close',
                  'volume': 'at_least_1.2_times_prior_3_mean', 'benchmark': 'three_interval_return_outperformance',
                  'developing_fraction': '0.8', 'stop_percent': '2', 'target_r': '2',
                  'trailing': 'NONE', 'exit_horizon_bars': 3, 'daily_gate': daily_gate,
                  'outcome': 'first_eligible_next_bar_open_to_close', 'round_trip_cost_bps': str(cost)}
    configuration_sha256 = _inputs_digest({'strategy_id':profile_id, 'strategy_version':version,
                                             'timeframe_minutes':interval, 'parameters':parameters})
    if evaluator is None:
        from .intraday_evaluation import evaluate_intraday
        evaluator = evaluate_intraday
    relevant, unknown, rejected, excluded = [], [], [], []
    for index, record in enumerate(raw):
        try:
            n = normalize_bar(record)
            if n['instrument'] != instrument:
                excluded.append({'index': index, 'reason': 'OTHER_INSTRUMENT'})
            elif n['interval_minutes'] != interval:
                excluded.append({'index': index, 'reason': 'OTHER_INTERVAL'})
            elif (_time(n['received_at']) > cutoff or
                  (n['source_timestamp'] is not None and _time(n['source_timestamp']) > cutoff)):
                excluded.append({'index': index, 'reason': 'FUTURE_SOURCE_OR_RECEIPT'})
            elif not n['interval_verified']:
                unknown.append(index)
            else:
                relevant.append((record, n))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            rejected.append({'index': index, 'reason': type(exc).__name__})
    eligible_benchmark = []
    benchmark_excluded = []
    for index, record in enumerate(benchmark):
        try:
            n = normalize_bar(record)
            if n['interval_minutes'] != interval:
                benchmark_excluded.append({'index':index, 'reason':'OTHER_INTERVAL'})
            elif (_time(n['received_at']) > cutoff or
                  (n['source_timestamp'] is not None and _time(n['source_timestamp']) > cutoff)):
                benchmark_excluded.append({'index':index, 'reason':'FUTURE_SOURCE_OR_RECEIPT'})
            else:
                eligible_benchmark.append(record)
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            benchmark_excluded.append({'index':index, 'reason':'INVALID_' + type(exc).__name__})
    # A decision candidate exists only if a completed interval was actually
    # received. A provisional receipt alone is not a completed observation.
    arrivals = {}
    for original, n in relevant:
        end, receipt = _time(n['bar_end']), _time(n['received_at'])
        if n['provisional'] or receipt < end:
            continue
        arrivals.setdefault(n['bar_start'], []).append(receipt)
    steps, baseline, strategy = [], [], []
    for start in sorted(arrivals, key=_time):
        decision_at = min(arrivals[start])
        asof_records = [record for record, n in relevant if _time(n['received_at']) <= decision_at]
        asof_benchmark = []
        for record in eligible_benchmark:
            try:
                if _time(record['received_at']) <= decision_at:
                    asof_benchmark.append(record)
            except (KeyError, TypeError, ValueError):
                continue
        snapshot = merge_bars(asof_records)['bars']
        current = next((x for x in snapshot if x['bar_start'] == start), None)
        if not current:
            continue
        # Don't re-evaluate an old bar after a newer interval has completed.
        later = any(_time(x['bar_end']) > _time(current['bar_end']) and
                    _time(x['bar_end']) <= decision_at for x in snapshot)
        if later:
            steps.append({'bar_start': start, 'decision_at': decision_at.isoformat(),
                          'state': 'SKIPPED', 'reason': 'LATE_RECEIPT_NEWER_BAR_PRESENT'})
            continue
        result = evaluator(profile_id, instrument, asof_records, decision_at,
                           benchmark_records=asof_benchmark, daily_gate=daily_gate, historical_replay=True)
        step = {'bar_start': start, 'bar_end': current['bar_end'], 'decision_at': decision_at.isoformat(),
                'state': result['state'], 'trace': result.get('rules', []),
                'strategy_id': result.get('strategy_id', profile_id),
                'strategy_version': result.get('strategy_version', version),
                'input_digest': _inputs_digest(asof_records), 'input_snapshot': asof_records,
                'benchmark_input_snapshot': asof_benchmark, 'outcome': None}
        immediate = _time(current['bar_end'])
        next_start = immediate
        if decision_at > immediate:
            next_start = immediate + timedelta(minutes=interval)
            if decision_at > next_start:
                step['outcome_reason'] = 'RECEIPT_TOO_LATE'
                steps.append(step)
                continue
            # The intervening bar must exist; otherwise continuity is unknown.
            if not arrivals.get(immediate.isoformat()):
                step['outcome_reason'] = 'INTERVENING_BAR_MISSING_OR_UNCLOSED'
                steps.append(step)
                continue
        next_arrivals = arrivals.get(next_start.isoformat(), [])
        if not next_arrivals:
            step['outcome_reason'] = 'NEXT_BAR_MISSING_OR_UNCLOSED'
            steps.append(step)
            continue
        exit_receipt = min(next_arrivals)
        # The store enforces local exchange hours for verified records; retain
        # an additional same-local-date check to avoid overnight comparisons.
        from .intraday_store import SAST
        if next_start.astimezone(SAST).date() != _time(current['bar_start']).astimezone(SAST).date():
            step['outcome_reason'] = 'SESSION_BOUNDARY'
            steps.append(step)
            continue
        outcome_records = [record for record, n in relevant if _time(n['received_at']) <= exit_receipt]
        later_snapshot = merge_bars(outcome_records)['bars']
        next_bar = next((x for x in later_snapshot if x['bar_start'] == next_start.isoformat()), None)
        if not next_bar or next_bar['provisional']:
            step['outcome_reason'] = 'NEXT_BAR_MISSING_OR_UNCLOSED'
            steps.append(step)
            continue
        op, cl = next_bar['fields']['open'], next_bar['fields']['close']
        # Disputed endpoints are not chosen silently for a numerical result.
        if op['state'] != 'AVAILABLE' or cl['state'] != 'AVAILABLE':
            step['outcome_reason'] = 'NEXT_BAR_ENDPOINT_MISSING_OR_CONFLICTED'
            steps.append(step)
            continue
        opening = _number(op['selected']['value']); closing = _number(cl['selected']['value'])
        if opening is None or closing is None:
            step['outcome_reason'] = 'NEXT_BAR_ENDPOINT_INVALID'
            steps.append(step)
            continue
        gross = (closing / opening - 1) * Decimal(10000)
        outcome = {'bar_start': next_bar['bar_start'], 'bar_end': next_bar['bar_end'],
                   'observed_at': exit_receipt.isoformat(), 'open': op['selected'], 'close': cl['selected'],
                   'gross_bps': str(gross), 'assumed_round_trip_cost_bps': str(cost),
                   'net_bps': str(gross-cost), 'classification': 'HYPOTHETICAL_NEXT_BAR_NOT_A_FILL'}
        step['outcome'] = outcome
        baseline.append(gross-cost)
        if result['state'] == 'ENTRY_MET':
            strategy.append(gross-cost)
        steps.append(step)
    def summary(values):
        return {'sample_count': len(values), 'mean_net_bps': str(sum(values)/len(values)) if values else None}
    return {'schema': 'strategy-radar-shadow-replay-v1', 'strategy_id': profile_id,
            'strategy_version': version, 'instrument': instrument, 'timeframe_minutes': interval,
            'parameters': parameters, 'configuration_sha256': configuration_sha256, 'replay_as_of': cutoff.isoformat(),
            'input_sha256': _inputs_digest(raw), 'inputs': raw,
            'benchmark_input_sha256': _inputs_digest(benchmark), 'benchmark_inputs': benchmark,
            'daily_gate': daily_gate, 'round_trip_cost_bps': str(cost), 'steps': steps,
            'unknown_clock_record_indices': unknown, 'invalid_records': rejected,
            'excluded_records': excluded, 'benchmark_excluded_records': benchmark_excluded,
            'input_counts': {'total':len(raw), 'eligible_verified':len(relevant),
                             'unknown_clock':len(unknown), 'invalid':len(rejected),
                             'other_instrument':sum(x['reason']=='OTHER_INSTRUMENT' for x in excluded),
                             'other_interval':sum(x['reason']=='OTHER_INTERVAL' for x in excluded),
                             'future':sum(x['reason']=='FUTURE_SOURCE_OR_RECEIPT' for x in excluded)},
            'candidate': summary(strategy), 'baseline': summary(baseline),
            'limitations': ['HYPOTHETICAL_NEXT_BAR_NOT_A_FILL', 'NO_INTRABAR_PATH_OR_CAPACITY',
                            'NO_SKILL_OR_PROMOTION_CLAIM', 'COST_ASSUMPTION_NOT_BROKER_VERIFIED'],
            'research_only': True, 'live_execution': False}
