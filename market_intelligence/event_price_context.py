"""Read source-bound, forward-only paired prices as descriptive event context.

This is not an event forecast or an estimate of model skill. The provider's
adjustment and corporate-action rules and complete exchange calendar are unknown.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from application.opportunities.source_resolution import parse_iress_export
from shadow_learning import timestamp
from . import anticipatory_radar as radar
from . import research_calendar as calendar

INSTRUMENTS = {'SASOL': 'SOL.JSE', 'ETF_STX40': 'STX40.JSE'}


@calendar._write
def register_plan(repo, folder, watch_id, event_date, baseline, evidence_id, explanation, now):
    """Record a descriptive protocol with an existing watch and date review."""
    now = timestamp(now.isoformat() if isinstance(now, datetime) else now)
    day = date.fromisoformat(event_date)
    watch = repo.paper_record(watch_id)
    evidence = repo.paper_record(evidence_id)
    if (not watch or watch.get('schema') != radar.VERSION or not watch_id.startswith('radar-watch-')
            or timestamp(watch['received_at']) > now or not evidence or evidence.get('watch_id') != watch_id
            or timestamp(evidence['received_at']) > now):
        raise ValueError('Available source-reviewed individual watch required')
    if any(w.get('parent_watch_id') == watch_id for w in radar.rows(repo, 'watch', now)):
        raise ValueError('Individual watch required')
    timing = evidence_id.startswith('radar-watch-timing-') and evidence.get('event_date') == event_date
    pending = (evidence_id.startswith('radar-watch-source-review-')
        and evidence.get('assessment') == 'LATER_REPORT_EVENT_PENDING')
    if not timing and not pending:
        raise ValueError('Source date or pending-event review required')
    if day < now.astimezone(radar.SAST).date():
        raise ValueError('A future or still-pending event date is required')
    if not isinstance(baseline, dict) or set(baseline) != set(INSTRUMENTS):
        raise ValueError('Both explicitly named source captures are required')
    reference = {key: _capture(Path(folder), key, name, now) for key, name in baseline.items()}
    if (reference['SASOL']['session'] != reference['ETF_STX40']['session']
            or reference['SASOL']['session'] >= event_date):
        raise ValueError('Aligned pre-event date reference required')
    payload = {'plan_schema': 'radar-price-context-plan-v1', 'watch_id': watch_id, 'event_date': event_date,
        'baseline': dict(baseline), 'reference_source_hashes': {k: reference[k]['source_sha256'] for k in INSTRUMENTS},
        'reference_capture_hashes': {k: reference[k]['capture_sha256'] for k in INSTRUMENTS},
        'date_evidence_id': evidence_id, 'date_basis': 'SOURCE_DATE_CANDIDATE' if timing else 'ASSISTANT_INTERPRETED_PENDING_REPORT',
        'date_explanation': calendar._text(explanation, 1500), 'registered_at': now.isoformat(),
        'prediction': None, 'comparator': 'ZERO_EXCESS_RETURN_REFERENCE_NOT_A_MODEL_FORECAST',
        'horizons': [1, 3], 'horizon_basis': 'PAIRED_OBSERVED_CAPTURES_AFTER_EVENT_DATE_NOT_VERIFIED_EXCHANGE_SESSIONS',
        'event_occurrence': 'SEPARATE_SOURCE_REVIEW_REQUIRED', 'source_definitions': 'UNVERIFIED',
        'scope': 'DESCRIPTIVE_CONTEXT_ONLY_NOT_CAUSAL_OR_A_PREDICTIVE_MODEL', 'live_execution': False}
    # Registration time belongs to the immutable record, not its identity.
    existing = [p for p in radar.rows(repo, 'price-context-plan', now)
                if p['watch_id'] == watch_id and p['event_date'] == event_date]
    if existing:
        for key in ('baseline', 'date_evidence_id', 'date_explanation', 'reference_source_hashes', 'reference_capture_hashes'):
            if existing[0][key] != payload[key]:
                raise ValueError('An existing event price plan is frozen; a changed reference requires a new plan version')
        return existing[0]
    return radar.save(repo, 'price-context-plan', [watch_id, event_date], payload, now)


def _capture(folder, instrument, filename, now):
    if instrument not in INSTRUMENTS or Path(filename).name != filename:
        raise ValueError('Exact capture identity required')
    path = folder / 'prospective-price-captures' / instrument / 'IRESS' / filename
    raw_receipt = path.read_bytes()
    saved = json.loads(raw_receipt)
    if (saved.get('schema') != 'prospective-price-capture-v1' or saved.get('instrument_id') != instrument
            or saved.get('provider') != 'IRESS' or saved.get('research_only') is not True):
        raise ValueError('Expected IRESS research receipt')
    acquired = timestamp(saved['acquired_at'])
    stored = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    if acquired > now or stored > now or stored < acquired:
        raise ValueError('Capture was not yet available')
    digest = saved['source_sha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Source hash required')
    raw = (folder / 'alternative-exports' / (instrument + '-IRESS-' + digest + '.csv')).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError('Raw source hash mismatch')
    parsed = parse_iress_export(raw, instrument, INSTRUMENTS[instrument], acquired.isoformat(), acquired)
    if parsed['bars'] != saved['bars']:
        raise ValueError('Receipt differs from the original source')
    return {'instrument': instrument, 'file': filename, 'capture_sha256': sha256(raw_receipt).hexdigest(),
        'source_sha256': digest, 'acquired_at': acquired.isoformat(), 'stored_at': stored.isoformat(),
        'session': parsed['bars'][-1]['timestamp'], 'close_zar': parsed['bars'][-1]['close'],
        'bars': parsed['bars']}


def _public(endpoint):
    return {key: value for key, value in endpoint.items() if key != 'bars'}


def _pct(value, reference):
    return (Decimal(str(value)) / Decimal(str(reference)) - 1) * 100


def review(folder, plan, now):
    """Compare only actually captured newer endpoints; missing sessions stay visible."""
    folder, now = Path(folder), timestamp(now.isoformat() if isinstance(now, datetime) else now)
    if plan.get('plan_schema') != 'radar-price-context-plan-v1' or plan.get('prediction') is not None:
        raise ValueError('A descriptive plan without a model prediction is required')
    registered = timestamp(plan['registered_at'])
    event_day = date.fromisoformat(plan['event_date']).isoformat()
    if registered > now:
        raise ValueError('Plan not yet registered')
    baseline = {key: _capture(folder, key, plan['baseline'][key], now) for key in INSTRUMENTS}
    if (baseline['SASOL']['session'] != baseline['ETF_STX40']['session']
            or baseline['SASOL']['session'] >= event_day
            or any(timestamp(x['acquired_at']) > registered or timestamp(x['stored_at']) > registered
                   for x in baseline.values())):
        raise ValueError('Aligned, actually retained pre-event reference required')
    if any(baseline[key]['source_sha256'] != plan['reference_source_hashes'][key]
            or baseline[key]['capture_sha256'] != plan['reference_capture_hashes'][key] for key in INSTRUMENTS):
        raise ValueError('Frozen reference source hash changed')
    captures, invalid = {key: [] for key in INSTRUMENTS}, []
    for instrument in INSTRUMENTS:
        directory = folder / 'prospective-price-captures' / instrument / 'IRESS'
        paths = sorted(directory.glob('*.json')) if directory.exists() else []
        if len(paths) > 2000:
            raise ValueError('Explicit capture archive capacity review required')
        for path in paths:
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > now:
                    continue
                item = _capture(folder, instrument, path.name, now)
            except (ValueError, KeyError, OSError, TypeError, OverflowError):
                invalid.append({'instrument': instrument, 'file': path.name})
                continue
            if timestamp(item['acquired_at']) > registered and timestamp(item['stored_at']) > registered:
                captures[instrument].append(item)
    # Only each capture's latest row can become a prospective observation.
    # Old rows are used exclusively to flag later revisions of consumed closes.
    first = {}
    for instrument, items in captures.items():
        for item in sorted(items, key=lambda x: (x['stored_at'], x['acquired_at'], x['file'])):
            if item['session'] > event_day:
                first.setdefault((instrument, item['session']), item)
    sessions = sorted({session for inst, session in first if inst == 'SASOL'
                       and ('ETF_STX40', session) in first})
    later_captures = [x for items in captures.values() for x in items]
    revisions = []
    for instrument in INSTRUMENTS:
        consumed = [baseline[instrument]] + [first[instrument, session] for session in sessions]
        for target in consumed:
            for item in later_captures:
                if item['instrument'] != instrument or timestamp(item['acquired_at']) <= timestamp(target['acquired_at']):
                    continue
                bar = next((b for b in item['bars'] if b['timestamp'] == target['session']), None)
                if bar and Decimal(str(bar['close'])) != Decimal(str(target['close_zar'])):
                    revisions.append({'instrument': instrument, 'session': target['session'],
                        'original_close_zar': target['close_zar'], 'later_close_zar': bar['close'],
                        'later_capture': item['file']})
    result = []
    revised = {(r['instrument'], r['session']) for r in revisions}
    for index in (1, 3):
        if len(sessions) < index:
            result.append({'paired_observation': index, 'state': 'WAITING_FOR_LATER_PAIRED_CAPTURE'})
            continue
        session = sessions[index - 1]
        share, benchmark = first['SASOL', session], first['ETF_STX40', session]
        share_return = _pct(share['close_zar'], baseline['SASOL']['close_zar'])
        bench_return = _pct(benchmark['close_zar'], baseline['ETF_STX40']['close_zar'])
        affected = any((key, day) in revised for key in INSTRUMENTS
                       for day in (baseline[key]['session'], session))
        result.append({'paired_observation': index, 'session': session,
            'state': 'SOURCE_REVISION_REVIEW_REQUIRED' if affected else 'DESCRIPTIVE_PAIRED_CONTEXT',
            'share_return_pct': float(share_return), 'benchmark_return_pct': float(bench_return),
            'excess_return_pct_points': float(share_return - bench_return),
            'share': _public(share), 'benchmark': _public(benchmark)})
    return {'schema': 'radar-price-context-review-v1', 'watch_id': plan['watch_id'],
        'event_date': event_day, 'plan_registered_at': registered.isoformat(),
        'baseline': {key: _public(value) for key, value in baseline.items()},
        'paired_observed_sessions': sessions, 'results': result, 'revisions': revisions,
        'invalid_captures': invalid, 'calendar_completeness': 'UNVERIFIED',
        'causal_attribution': 'NOT_ESTABLISHED', 'event_occurrence': 'SEPARATE_SOURCE_REVIEW_REQUIRED',
        'forecast_skill': 'NOT_EVALUABLE_WITHOUT_A_FROZEN_NUMERICAL_CANDIDATE',
        'source_definitions': 'UNVERIFIED', 'trading_weight': 0, 'live_execution': False}


def status(repo, folder, now):
    """A damaged or absent source for one plan never hides other plans."""
    plans = radar.rows(repo, 'price-context-plan', now)
    output = []
    for plan in plans:
        try:
            output.append(review(folder, plan, now))
        except (ValueError, KeyError, OSError, TypeError, OverflowError) as exc:
            output.append({'watch_id': plan['watch_id'], 'state': 'REFERENCE_UNAVAILABLE',
                'error_type': type(exc).__name__,
                'forecast_skill': 'NOT_EVALUABLE_WITHOUT_A_FROZEN_NUMERICAL_CANDIDATE'})
    return {'state': 'DESCRIPTIVE_EVENT_PRICE_CONTEXT', 'plans': output}
