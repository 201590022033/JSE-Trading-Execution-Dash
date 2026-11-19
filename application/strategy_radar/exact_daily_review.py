"""Audit the retained inputs required by the exact daily Swing research trace."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from application.opportunities.session_freshness import latest_expected_session, next_session
from .swing_radar import _FEATURE_PROFILE_VERSION, _FIELDS, _STATES

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'artifacts/research/radar-exact-daily/vod-v1.1.2.json'
PROFILE = 'jse_swing_3_5d'
WINDOW_START = '2026-05-04'
WARMUP = 100  # Match Radar's maximum daily history suffix.


def _index_rows(history):
    raw = json.dumps(history, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    rows = {}
    repeated = set()
    for row in history:
        session = row['session']
        if session in rows:
            repeated.add(session)
        rows[session] = row['fields']
    for session in repeated:
        rows[session] = {}
    return rows, sha256(raw).hexdigest()


def _qualified(field, session_close, as_of, *, allow_zero):
    state = field.get('state')
    if state not in _STATES and state != 'CONFLICT_NO_CONSENSUS':
        return state or 'MISSING', None
    try:
        received = datetime.fromisoformat(field['acquired_at'])
        value = float(field['value'])
        valid_value = math.isfinite(value) and (value >= 0 if allow_zero else value > 0)
        if not (valid_value and field.get('source')
                and re.fullmatch('[a-f0-9]{64}', field['source_sha256'])
                and session_close <= received <= as_of):
            raise ValueError('Unqualified receipt')
    except (KeyError, TypeError, ValueError, OverflowError):
        return 'UNQUALIFIED_RECEIPT', None
    return ('ZEBRA_SELECTED_DISPUTED' if state == 'CONFLICT_NO_CONSENSUS' else 'QUALIFIED'), received


def _retrospective(instrument, benchmark, segment, as_of, source_hash):
    from dataclasses import replace
    from decimal import Decimal
    from application.backtest_lab.observed_history import from_chart
    from domain.backtest.component_engine import Costs, Signal, replay
    from .swing_radar import snapshot

    if len(segment) < WARMUP + 3:
        return {'state': 'INSUFFICIENT_CONTIGUOUS_INPUT', 'segments_sessions': len(segment)}
    share_bars = [{'timestamp': day, **{f: values[f] for f in _FIELDS}} for day, values in segment]
    benchmark_bars = [{'timestamp': day, 'close': values['benchmark_close']} for day, values in segment]
    # The engine models availability on the following UTC day. All original
    # receipt clocks remain in Zebra, and the point-in-time check is separate.
    manifest = from_chart(instrument, {'bars': share_bars, 'provenance': {
        'provider': 'ZEBRA_SELECTED_FIELDS', 'source_sha256': source_hash, 'acquired_at': as_of.isoformat()}})
    signals = []
    evaluated = unknown = 0
    for index in range(WARMUP - 1, len(segment) - 3):
        day = share_bars[index]['timestamp']
        clock = manifest.bars[index].available_at + timedelta(seconds=1)
        share = {'symbol': instrument, 'interval': '1d', 'currency': 'ZAR',
                 'bars': share_bars[index-WARMUP+1:index+1]}
        reference = {'symbol': benchmark, 'interval': '1d', 'currency': 'ZAR',
                     'bars': benchmark_bars[index-WARMUP+1:index+1]}
        result = snapshot(share, evaluated_at=clock, benchmark_chart=reference,
                          feature_profile_version=_FEATURE_PROFILE_VERSION)
        core = (result.get('conditions') or {}).get('core_setup')
        evaluated += 1
        unknown += core is None
        if core:
            signals.append(Signal(f'{instrument}-{day}', instrument, day, clock,
                                  Decimal(str(result['geometry']['stop'])), Decimal(100000), Decimal(5000),
                                  strategy_profile_id=PROFILE, strategy_profile_version=_FEATURE_PROFILE_VERSION))
    costs = Costs(fee_bps=8, minimum_fee=60, spread_bps=20, slippage_bps=5)
    trials = []
    for target in (Decimal(2), Decimal('1.5')):
        plan = [replace(signal, target_r=target) for signal in signals]
        output = replay([manifest], plan, as_of=as_of, initial_cash=Decimal(1000000), costs=costs)
        trades = output['trades']
        trials.append({'target_r': str(target), 'signals': len(plan), 'closed_trades': len(trades),
                       'net_pnl_zar': str(sum((Decimal(t['net_pnl']) for t in trades), Decimal('0.00'))),
                       'exit_reasons': dict(Counter(t['reason'] for t in trades)),
                       'engine_config_hash': output['config_hash']})
    return {'state': 'DESCRIPTIVE_REPLAY', 'window': [segment[0][0], segment[-1][0]],
            'decision_sessions': evaluated, 'unknown_decision_sessions': unknown,
            'input_manifest_sha256': manifest.sha256, 'cost_basis': costs.basis,
            'costs': {'fee_bps_per_side': 8, 'minimum_fee_zar': 60, 'spread_bps': 20, 'slippage_bps_per_side': 5},
            'initial_cash_zar': 1000000, 'max_notional_zar': 100000, 'risk_budget_zar': 5000,
            'hold_sessions': 3, 'fill_basis': 'NEXT_SESSION_CLOSE_PROXY', 'trials': trials, 'limitations': [
                'RECONSTRUCTED_AVAILABILITY', 'ZEBRA_SELECTED_DISPUTED_FIELDS_ALLOWED',
                'UNVERIFIED_CORPORATE_ACTION_BASIS', 'NO_UNSEEN_VALIDATION', 'NO_PROMOTION']}


def review(histories, *, as_of, instrument, benchmark):
    """Measure coverage and historical receipt timing without simulating fills."""
    if as_of.utcoffset() is None:
        raise ValueError('An explicit timezone is required')
    end = latest_expected_session(as_of)
    if not end or end < WINDOW_START:
        raise ValueError('Reviewed JSE calendar window is unavailable')
    share, share_hash = _index_rows(histories[instrument]['rows'])
    reference, reference_hash = _index_rows(histories[benchmark]['rows'])
    counts = {field: Counter() for field in (*_FIELDS, 'benchmark_close')}
    total = qualified_run = longest_run = complete = clocked = clocked_windows = 0
    receipt_window = []
    segment, latest_eligible = [], []
    session = WINDOW_START
    while session and session <= end:
        total += 1
        midnight = datetime.fromisoformat(session).replace(tzinfo=timezone.utc)
        start_next = next_session(session)
        close = midnight + timedelta(hours=15)
        fields = share.get(session, {})
        inputs = {**{name: fields.get(name) or {} for name in _FIELDS},
                  'benchmark_close': reference.get(session, {}).get('close') or {}}
        receipts = []
        for name, field in inputs.items():
            reason, received = _qualified(field, close, as_of, allow_zero=name == 'volume')
            counts[name][reason] += 1
            if received is not None:
                receipts.append(received)
        if len(receipts) == len(inputs):
            o, h, low, c = (float(inputs[key]['value']) for key in ('open', 'high', 'low', 'close'))
            if low <= min(o, c) <= max(o, c) <= h:
                complete += 1
                qualified_run += 1
                segment.append((session, {name: inputs[name]['value'] for name in inputs}))
                longest_run = max(longest_run, qualified_run)
                receipt_window.append(max(receipts))
                if len(receipt_window) > WARMUP:
                    receipt_window.pop(0)
                if start_next:
                    cutoff = datetime.fromisoformat(start_next).replace(tzinfo=timezone.utc) + timedelta(hours=7)
                    on_time = receipt_window[-1] <= cutoff
                    clocked += on_time
                    clocked_windows += (len(receipt_window) == WARMUP and max(receipt_window) <= cutoff)
                session = start_next
                continue
        receipt_window.clear()
        if len(segment) >= WARMUP + 3:
            latest_eligible = segment
        segment = []
        qualified_run = 0
        session = start_next
    from application.opportunities.zebra_volume_reconciliation import reconcile_volume
    retrospective = _retrospective(instrument, benchmark, segment if len(segment) >= WARMUP + 3 else latest_eligible,
                                   as_of, share_hash)
    return {
        'schema': 'exact-daily-input-review-v1',
        'instrument': instrument, 'benchmark': benchmark, 'product': 'CASH_SHARE',
        'strategy_id': PROFILE, 'strategy_version': _FEATURE_PROFILE_VERSION, 'timeframe_minutes': None,
        'window': [WINDOW_START, end], 'sessions': total,
        'checked_at': as_of.isoformat(), 'input_sha256': {instrument: share_hash, benchmark: reference_hash},
        'input_hash_basis': 'CANONICAL_JSON_ZEBRA_SELECTED_ROWS',
        'field_counts': counts, 'qualified_sessions': complete, 'longest_qualified_run': longest_run,
        'on_time_sessions': clocked, 'on_time_warmup_windows': clocked_windows, 'warmup_sessions': WARMUP,
        'state': 'INPUT_CANDIDATE' if clocked_windows else 'INSUFFICIENT_POINT_IN_TIME_INPUT',
        'retrospective_comparison': retrospective,
        'volume_reconciliation': reconcile_volume(
            ({'session': day, 'fields': fields} for day, fields in share.items() if WINDOW_START <= day <= end),
            as_of=as_of),
        'research_only': True, 'live_execution': False,
    }


def retained_review(instrument, profile, version, timeframe, benchmark):
    try:
        item = json.loads(REPORT.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    expected = (instrument, profile, version, timeframe, benchmark, 'CASH_SHARE')
    fields = ('instrument', 'strategy_id', 'strategy_version', 'timeframe_minutes', 'benchmark', 'product')
    return item if tuple(item.get(field) for field in fields) == expected else None


def main():
    import argparse
    from application.opportunities.zebra_screen_data import load_zebra_screen_data

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=datetime.fromisoformat, required=True)
    parser.add_argument('--instrument', required=True)
    parser.add_argument('--benchmark', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    benchmark = args.benchmark
    if not all(re.fullmatch(r'[A-Z0-9_]{2,16}', name) for name in (args.instrument, benchmark)):
        parser.error('Explicit share and benchmark identifiers are required')
    histories = load_zebra_screen_data(root=ROOT, now=args.as_of, max_rows=600,
                                     instruments={args.instrument, benchmark})['instruments']
    if not {args.instrument, benchmark}.issubset(histories):
        parser.error('Both the share and benchmark need retained Zebra source observations')
    result = review(histories, as_of=args.as_of, instrument=args.instrument, benchmark=benchmark)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
