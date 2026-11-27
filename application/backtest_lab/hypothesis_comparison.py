"""Matched daily hypothesis comparisons over the existing exact replay engines."""
from bisect import bisect_left
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from math import isfinite
import json
import os
from pathlib import Path
import re

from application.opportunities.research_classification import classifications
from application.opportunities.session_freshness import latest_expected_session, next_session
from application.opportunities.zebra_screen_data import load_zebra_screen_data

from . import exact_run_job as exact
from . import zebra_field_windows as benchmarks
from .hypothesis_coverage import GROUPS


REQUEST_KIND = 'hypothesis-comparison-v1'
FIELDS = {'instrument', 'profiles', 'families', 'first_session', 'last_session'}
WARMUP = exact.WARMUP - 1
RULE_VERSION = '1.0.0'
RESOURCE = {'AGL': 'ETF_STXRES', 'BHP': 'ETF_STXRES', 'SASOL': 'BZ_F'}
GOLD = {'GFI', 'RNG'}
TELECOM = {'MTN': 'VOD', 'VOD': 'MTN'}
RULES = {
    'H1': 'Run the exact selected daily strategy against the share’s mapped sector ETF or broad-market reference.',
    'H2': 'Require positive prior five-observation resource-proxy and USD/ZAR returns on the selected strategy trigger.',
    'H3': 'Require a verified company-specific external driver and peer confirmation for continuation.',
    'H4': 'Require a dated financial shock, a technical reclaim and prior sector recovery.',
    'H5': 'Test a USD/ZAR impulse under a separate currency product and activity contract.',
    'H6': 'Require positive prior five-observation USD gold and ZAR-converted gold returns on mapped gold-share triggers.',
    'H7': 'Require positive prior five-observation return in the other telecom share, using the existing broad benchmark.',
}
UNAVAILABLE = {
    'H3': 'Missing a dated company-to-driver exposure mapping and an exact global-demand confirmation runner.',
    'H4': 'Missing a dated shock/sector-recovery input and an exact post-shock reclaim runner.',
    'H5': 'Missing a USD/ZAR product, cost and macro-impulse runner. The retained FX study reports gross price moves.',
}
REQUIRED_CONTEXT = {
    'H3': ('dated business exposure', 'timestamped external driver', 'aligned peer closes'),
    'H4': ('dated shock evidence', 'reclaim level', 'aligned sector closes'),
    'H5': ('USD/ZAR OHLC', 'timestamped macro surprise', 'currency product and fee schedule',
           'qualified activity or a price-only rule version'),
}


def references(family, instrument):
    if family == 'H2' and instrument in RESOURCE:
        return RESOURCE[instrument], 'ZAR_X'
    if family == 'H6' and instrument in GOLD:
        return 'GC_F', 'ZAR_X'
    if family == 'H7' and instrument in TELECOM:
        return (TELECOM[instrument],)
    return ()


def contract(instrument):
    recommendation = (
        ('H2', 'Mapped resource exposure with a retained resource-equity or Brent proxy.') if instrument in RESOURCE
        else ('H6', 'Mapped gold exposure with USD gold and currency context.') if instrument in GOLD
        else ('H7', 'Mapped telecom share with a separate telecom peer.') if instrument in TELECOM
        else ('H1', 'The selected-share strategy has no mapped specialist overlay.')
    )
    rows = []
    for family, title, _ in GROUPS:
        inputs = references(family, instrument)
        reason = UNAVAILABLE.get(family)
        if family not in {'H1', *UNAVAILABLE} and not inputs:
            reason = {
                'H2': f'{instrument} has no mapped resource proxy and currency exposure for H2.',
                'H6': f'{instrument} has no mapped gold exposure for H6.',
                'H7': f'{instrument} has no mapped telecom peer for H7.',
            }[family]
        rows.append(dict(id=family, name=title, rule=RULES[family], reason=reason,
                         fields=[*(exact._FIELDS if family != 'H5' else ()), *REQUIRED_CONTEXT.get(family, ())],
                         references=list(inputs), timeframe='1d',
                         compatible_profiles=[] if reason else [list(p) for p in sorted(exact.SUPPORTED_IDENTITIES)],
                         runner=None if reason else 'EXACT_DAILY_CASH_SHARE', version=RULE_VERSION))
    return {'families': rows, 'recommended': recommendation[0], 'reason': recommendation[1]}


def validate(body, service):
    if not isinstance(body, dict) or set(body) not in (FIELDS, FIELDS | {'preview_id'}):
        raise exact.RunUnavailable('Select a share, exact strategy versions, hypotheses and a date mode.')
    instrument = body['instrument']
    if not isinstance(instrument, str) or instrument not in {row['instrument'] for row in exact.replay_instruments(service.root)}:
        raise exact.RunUnavailable('Select a recognized Zebra cash share.')
    profiles, families = body['profiles'], body['families']
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= len(exact.SUPPORTED_IDENTITIES) or any(
        not isinstance(p, list) or len(p) != 2 or not all(isinstance(value, str) for value in p)
        or tuple(p) not in exact.SUPPORTED_IDENTITIES for p in profiles
    ):
        raise exact.RunUnavailable('Select one or more compatible exact strategy versions.')
    if not isinstance(families, list) or not 1 <= len(families) <= len(RULES) or any(
        not isinstance(f, str) or f not in RULES for f in families
    ):
        raise exact.RunUnavailable('Select one or more hypotheses from H1 to H7.')
    first, last = body['first_session'], body['last_session']
    if first is not None or last is not None:
        try:
            if date.fromisoformat(first).isoformat() != first or date.fromisoformat(last).isoformat() != last or first > last:
                raise ValueError
        except (ValueError, TypeError):
            raise exact.RunUnavailable('Use ordered start and end dates in YYYY-MM-DD format.') from None
    latest = latest_expected_session(service.clock())
    if not latest or (last and last > latest):
        raise exact.RunUnavailable('End on or before the latest completed session in the reviewed JSE calendar.')
    result = dict(instrument=instrument, profiles=[list(p) for p in sorted({tuple(p) for p in profiles})],
                  families=sorted(set(families)), first_session=first, last_session=last)
    if 'preview_id' in body:
        preview_id = body['preview_id']
        if not isinstance(preview_id, str) or not re.fullmatch('[a-f0-9]{64}', preview_id):
            raise exact.RunUnavailable('Review the retained data before starting a comparison.')
        result['preview_id'] = preview_id
    return result


def _iress_first(instruments):
    """Keep the selected IRESS field and retain every Zebra alternative."""
    for item in instruments.values():
        for row in item['rows']:
            for name, field in row['fields'].items():
                if field.get('source') == 'IRESS':
                    continue
                alternatives = field.get('alternatives', [])
                primary = next((candidate for candidate in alternatives if candidate['source'] == 'IRESS'), None)
                if primary:
                    selection = {key: field[key] for key in ('source', 'value', 'acquired_at', 'received_at',
                                                             'source_sha256', 'field_source_sha256') if key in field}
                    chosen = {key: value for key, value in field.items() if key not in selection}
                    chosen.update(primary, alternatives=[selection, *(c for c in alternatives if c is not primary)])
                    if selection['value'] != primary['value']:
                        chosen['state'] = 'CONFLICT_NO_CONSENSUS'
                    row['fields'][name] = chosen
                    row[name] = primary['value']
    return instruments


def _cross_asset(root, key, now):
    symbol, product, units = {
        'ZAR_X': ('ZAR=X', 'USD_ZAR_SPOT_REFERENCE', 'ZAR_PER_USD'),
        'BZ_F': ('BZ=F', 'CONTINUOUS_BRENT_FUTURES_REFERENCE', 'USD'),
        'GC_F': ('GC=F', 'CONTINUOUS_GOLD_FUTURES_REFERENCE', 'USD'),
    }[key]
    folder = Path(root) / 'runtime/local-swing-data/cross-asset-research'
    captures = []
    for path in folder.glob(key + '-*.json'):
        try:
            if path.stat().st_size > 32_000_000:
                continue
            raw = path.read_bytes()
            digest = sha256(raw).hexdigest()
            source = json.loads(raw)
            clock = datetime.fromisoformat(source['acquired_at'])
            if (path.stem != f'{key}-{digest}' or clock > now
                    or (source['symbol'], source['product'], source['expected_units'], source['provider_interval'])
                    != (symbol, product, units, '1d') or source['identity']['symbol'] != symbol):
                continue
            rows = {}
            for row in source['rows']:
                if row.get('close') is None:
                    continue
                day = row['session']
                value = float(row['close'])
                if (date.fromisoformat(day).isoformat() == day and day < clock.date().isoformat()
                        and not row['current_session_not_completed'] and isfinite(value) and value > 0):
                    if day in rows:
                        raise ValueError('Duplicate reference session')
                    rows[day] = value
            if rows:
                captures.append((clock, digest, rows, source))
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            continue
    if not captures:
        return {}, None
    _, digest, rows, source = max(captures, key=lambda row: row[:2])
    receipt = {key: source[key] for key in ('symbol', 'provider', 'acquired_at', 'historical_availability')}
    return rows, dict(receipt, source_sha256=digest)


def _daily_close(items, key):
    return {day: entry['value'] for day, entry in
            benchmarks._selected_closes(items.get(key, {}).get('rows', [])).items()}


def _benchmark(share):
    sector = classifications({share})['instruments'][share]['sector']
    key = benchmarks.SECTOR_PROXY.get(sector, benchmarks.BROAD_BENCHMARK)
    label = f'Sector ETF {key}' if key != benchmarks.BROAD_BENCHMARK else benchmarks.broad_benchmark_label(sector)
    return key, sector, label


def _benchmark_inputs(items, sessions, policy):
    key, sector, label = policy
    closes = _daily_close(items, key)
    assignments = {day: dict(instrument=key if all(day in closes for day in sessions[max(0, i - 20):i + 1]) else None,
                             label=label, sector=sector, basis='PINNED_CURRENT_RESEARCH_CLASSIFICATION')
                   for i, day in enumerate(sessions)}
    return assignments, {key: {day: {'close': value} for day, value in closes.items()}}


def _prior_returns(series, sessions):
    """Only earlier dated observations, with an explicit staleness bound."""
    days = sorted(series)
    results = {}
    for day in sessions:
        index = bisect_left(days, day)
        if index >= 6 and (date.fromisoformat(day) - date.fromisoformat(days[index - 1])).days <= 5:
            first, last = days[index - 6], days[index - 1]
            if (date.fromisoformat(last) - date.fromisoformat(first)).days <= 12:
                results[day] = {'first': first, 'last': last, 'return': series[last] / series[first] - 1}
    return results


def _segments(sessions, observed):
    next_observed = dict(zip(observed, observed[1:]))
    segments = []
    for day in sessions:
        previous = segments[-1][-1] if segments else None
        if (previous is None or next_observed.get(previous) != day
                or (day >= '2026-01-01' and previous >= '2026-01-01' and next_session(previous) != day)):
            segments.append([])
        segments[-1].append(day)
    return segments


def prepare(service, spec):
    now = service.clock()
    share = spec['instrument']
    latest = latest_expected_session(now)
    policy = contract(share)
    selected = {row['id']: row for row in policy['families'] if row['id'] in spec['families']}
    keys = {key for row in selected.values() for key in row['references']}
    cross_keys = keys & {'BZ_F', 'ZAR_X', 'GC_F'}
    benchmark = _benchmark(share)
    input_keys = {share, benchmark[0]} | (keys - cross_keys)
    items = _iress_first(load_zebra_screen_data(service.root, now=now, instruments=input_keys)['instruments'])
    item = items.get(share, {})
    bars, lineage, partial = exact._inputs(item or {'rows': []}, latest, now)
    sessions = [bar['timestamp'] for bar in bars]
    assignments, series = _benchmark_inputs(items, sessions, benchmark)
    earliest, end = spec['first_session'], spec['last_session']
    candidates = [day for index, day in enumerate(sessions) if index >= WARMUP
                  and (not earliest or earliest <= day <= end) and assignments[day]['instrument']]
    returns, receipts, reference_values = {}, {}, {}
    for key in sorted(keys):
        if key in cross_keys:
            values, receipt = _cross_asset(service.root, key, now)
            if receipt:
                receipts[key] = receipt
        else:
            values = _daily_close(items, key)
        reference_values[key] = values
        returns[key] = _prior_returns(values, candidates)
    if 'H6' in selected and {'GC_F', 'ZAR_X'} <= cross_keys:
        gold, fx = reference_values['GC_F'], reference_values['ZAR_X']
        overlap = gold.keys() & fx.keys()
        returns['GOLD_ALIGNED'] = _prior_returns({day: gold[day] for day in overlap}, candidates)
        returns['GOLD_ZAR_ALIGNED'] = _prior_returns({day: gold[day] * fx[day] for day in overlap}, candidates)
    # Resolve a common calendar for actionable families. Missing input cells
    # stay visible without preventing the other families from using their data.
    eligible, unavailable = {}, {}
    for family, row in selected.items():
        relevant = set(candidates)
        required = ('GOLD_ALIGNED', 'GOLD_ZAR_ALIGNED') if family == 'H6' and row['references'] else row['references']
        for key in required:
            relevant.intersection_update(returns[key])
        if row['reason']:
            unavailable[family] = row['reason']
        elif not candidates:
            unavailable[family] = (f'Requires daily OHLCV, 99 prior usable bars and aligned {benchmark[0]} closes. '
                                   'No such decision session is retained in the requested range.')
        elif not relevant:
            missing = [key for key in row['references'] if not returns[key]]
            unavailable[family] = ('No usable retained completed observations for ' + ', '.join(missing) + '.'
                                   if missing else 'No shared completed sessions for ' + ', '.join(row['references']) + '.')
        else:
            eligible[family] = relevant
    common = set.intersection(*eligible.values()) if eligible else set()
    if eligible and not common:
        for family in list(eligible):
            if family != 'H1':
                unavailable[family] = 'No shared completed sessions across the selected hypotheses.'
                del eligible[family]
        common = eligible.get('H1', set())
    matched = max(_segments(sorted(common), sessions), key=lambda group: (len(group), group[-1]), default=[])
    covered = set(matched)
    sources, corroborating, clocks, disputed = set(), set(), {}, set()
    for day in matched:
        for field in lineage[day].values():
            if field.get('source'):
                sources.add(field['source'])
            if field.get('state') == 'CONFLICT_NO_CONSENSUS':
                disputed.add(day)
            for evidence in (field, *field.get('alternatives', [])):
                if evidence.get('source') and evidence.get('acquired_at'):
                    source, clock = evidence['source'], evidence['acquired_at']
                    clocks[source] = max(clocks.get(source, ''), clock)
            corroborating.update(alt['source'] for alt in field.get('alternatives', []))
    # Enumerate reviewed calendar gaps as well as gaps observed in retained history.
    excluded = {day for day in set(sessions) | partial if (earliest or (sessions[WARMUP] if candidates else latest))
                <= day <= (end or latest) and day not in covered}
    day = max(earliest or (candidates[0] if candidates else latest), '2026-01-01')
    while day and day <= (end or latest):
        if next_session((date.fromisoformat(day) - timedelta(days=1)).isoformat()) == day and day not in covered:
            excluded.add(day)
        day = next_session(day)
    cells = [dict(profile_id=identity[0], version=identity[1], family=family,
                  state='UNAVAILABLE' if family in unavailable else 'READY',
                  reason=unavailable.get(family), rule=selected[family]['rule'])
             for identity in spec['profiles'] for family in selected]
    preview = dict(instrument=share, first_session=matched[0] if matched else None,
                   last_session=matched[-1] if matched else None, qualified_sessions=len(matched),
                   warmup_sessions=WARMUP, warmup_total_available=sessions.index(matched[0]) if matched else 0,
                   warmup_first_session=sessions[sessions.index(matched[0]) - WARMUP] if matched else None,
                   earliest_retained_session=sessions[0] if sessions else None,
                   close_sources=sorted(sources), corroborating_sources=sorted(corroborating),
                   provider_acquired_at=clocks, excluded_sessions=sorted(excluded),
                   disputed_share_sessions=len(disputed),
                   missing_share_sessions=sorted(excluded - set(sessions)),
                   benchmarks=sorted({assignments[day]['label'] for day in matched}),
                   references=receipts, cells=cells, requested_dates=[earliest, end], latest_completed=latest)
    if matched:
        end_day = matched[-1]
        fields = {key: [(row['session'], row['fields'] if key == share else row['fields'].get('close'))
                        for row in item['rows'] if row['session'] <= end_day] for key, item in items.items()}
        preview['preview_id'] = sha256(exact._json((preview, fields, returns))).hexdigest()
    return preview, (now, bars, lineage, assignments, series, items, returns, selected, eligible, matched)


def preview(service, body):
    return prepare(service, validate(body, service))[0]


def _context(family, row, day, returns):
    keys = ('GOLD_ALIGNED', 'GOLD_ZAR_ALIGNED') if family == 'H6' else row['references']
    points = {key: returns[key][day] for key in keys}
    values = {key: point['return'] for key, point in points.items()}
    return {'c': f'{family} confirmation', 't': RULES[family], 'ok': all(value > 0 for value in values.values()),
            'v': ', '.join(f'{key} {100 * value:+.2f}%' for key, value in values.items()),
            'references': points}


def build(spec, readiness, inputs):
    now, bars, lineage, assignments, series, items, returns, selected, eligible, matched = inputs
    if not matched:
        raise exact.RunUnavailable('No selected cell has a matched replay window. Review the data preview.')
    share = spec['instrument']
    matched_set = set(matched)
    scoped = [bar for bar in bars if bar['timestamp'] in matched_set]
    history = [bar for bar in bars if bar['timestamp'] < matched[0]] + scoped
    raw_lineage = {day: lineage[day] for day in (bar['timestamp'] for bar in history)}
    receipt = dict(instrument=share, product='cash_equity', provider='ZEBRA_IRESS_FIRST_FIELDS',
                   source_sha256=sha256(exact._json(raw_lineage)).hexdigest(), acquired_at=now.isoformat(),
                   hash_basis='CANONICAL_FIELD_LINEAGE_PACKET_NOT_RAW_PROVIDER_BYTES')
    manifests = [exact.from_chart(share, {'bars': scoped, 'provenance': receipt})]
    strategies = []
    for profile, version in spec['profiles']:
        identity = profile, version
        legacy = identity in exact.LAB_IDENTITIES
        runner = exact.lab_engine.replay if legacy else exact.replay
        costs = exact.lab_engine.Costs(fee_bps=exact.COSTS.fee_bps, minimum_fee=exact.COSTS.minimum_fee,
                                     spread_bps=exact.COSTS.spread_bps, slippage_bps=exact.COSTS.slippage_bps) if legacy else exact.COSTS
        signals, traces, rejected, names, funnel, unknown = exact._signals(
            share, history, matched[0], assignments, series, identity)
        if identity == exact.COMPONENT_IDENTITY:
            notional, risk, horizon, target_r = (exact.COMPONENT.max_notional, exact.COMPONENT.risk_budget,
                                                exact.COMPONENT.horizon, exact.COMPONENT.target_r)
        else:
            notional = exact.LAB_MAX_NOTIONAL if legacy else exact.MAX_NOTIONAL
            risk = exact.LAB_RISK_BUDGET if legacy else exact.RISK_BUDGET
            horizon, target_r = exact.HORIZON, exact.TARGET_R
        sizing = dict(max_notional_zar=str(notional), risk_budget_zar=str(risk),
                      horizon_observed_sessions=horizon, target_r=str(target_r))
        for family in eligible:
            context = {row['id']: _context(family, selected[family], row['session'], returns)
                       for row in traces} if family != 'H1' else {}
            passed = {row['id'] for row in traces if row['id'] not in context or context[row['id']]['ok']}
            successful = [dict(row, trace=[*row['trace'], context[row['id']]]) if row['id'] in context else row
                          for row in traces if row['id'] in passed]
            missed = [dict(row, trace=[*row['trace'], context[row['id']]]) for row in traces if row['id'] not in passed]
            run = runner(manifests, [signal for signal, row in zip(signals, traces) if row['id'] in passed],
                         as_of=now, initial_cash=Decimal(exact.INITIAL_CASH), costs=costs)
            trades, equity = run['trades'], run['equity']
            peak, drawdown, amount = exact.INITIAL_CASH, 0, exact.INITIAL_CASH
            for point in equity:
                amount = float(point['equity'])
                peak = max(peak, amount)
                drawdown = min(drawdown, amount / peak - 1)
            total_cost = sum(
                -Decimal(entry['amount']) if entry['kind'] == 'FEE' else
                Decimal(entry.get('spread_impact', '0')) + Decimal(entry.get('slippage_impact', '0'))
                for entry in run['ledger'])
            strategies.append(dict(id=f'{profile}@{version}:{family}',
                name=exact.DEFAULT_STRATEGY_REGISTRY.resolve(*identity).display_name + ' · ' + family,
                strategy_profile_id=profile, strategy_profile_version=version, timeframe='1d',
                hypothesis_family=family, hypothesis_version=RULE_VERSION,
                replay_sizing=sizing,
                source='Exact daily strategy and existing cash-share replay engine',
                desc=RULES[family], conds=names + ([family + ' confirmation'] if context else []),
                funnel=dict(funnel, passed=[*funnel['passed'], len(successful)] if context else funnel['passed']),
                engine_config_hash=run['config_hash'], missed_triggers=missed, unavailable_decisions=unknown,
                sum=dict(signals=len(successful), traded=len(trades), net=round(amount - exact.INITIAL_CASH, 2),
                         mdd=round(drawdown * 100, 2), costs=float(total_cost), stocks=int(bool(trades)),
                         win=round(100 * sum(float(t['net_pnl']) > 0 for t in trades) / len(trades), 1) if trades else None,
                         verdict='Fewer than 30 closed trades' if len(trades) < exact.MIN_SAMPLE_TRADES else 'Descriptive research'),
                run=dict(signals=successful, rejected_bars=[*rejected, *missed], decisions=run['decisions'],
                         trades=trades, equity=equity, open_positions=run['open_positions'], ledger=run['ledger'])))
    benchmark_lineage = {key: {row['session']: row['fields'].get('close') for row in record['rows']
                                if history[0]['timestamp'] <= row['session'] <= matched[-1]}
                         for key, record in items.items() if key != share}
    meta = dict(grade='ASSUMPTION_LIMITED', data_basis='ZEBRA_MATCHED_HYPOTHESIS_COMPARISON',
                data_quality='GAP_TOLERATED' if readiness['excluded_sessions'] else 'RECONSTRUCTED',
                created_at=now.isoformat(), created_at_basis='RUN_CAPTURE_CLOCK',
                live_execution=False, cost_basis=exact.COSTS.basis, initial_cash=exact.INITIAL_CASH,
                source_receipts=[receipt], field_lineage={share: raw_lineage}, benchmark_close_lineage=benchmark_lineage,
                sector_benchmarks={share: assignments[matched[-1]]},
                sector_benchmarks_by_session={share: {day: assignments[day] for day in matched}},
                comparison=readiness, replay_assumptions=dict(
                    capital_zar=exact.INITIAL_CASH, fee_bps_per_side=str(exact.COSTS.fee_bps),
                    minimum_fee_zar=str(exact.COSTS.minimum_fee), spread_bps=str(exact.COSTS.spread_bps),
                    slippage_bps_per_side=str(exact.COSTS.slippage_bps),
                    sizing_and_exits='Pinned by exact strategy version across hypotheses'),
                limitations=['CLOSE_PROXY_FILLS', 'RECONSTRUCTED_HISTORICAL_AVAILABILITY',
                             'UNVERIFIED_CORPORATE_ACTION_BASIS', 'OBSERVED_CALENDAR_BEFORE_2026']
                + (['RESOURCE_ETF_IS_AN_EXPOSURE_PROXY_AND_CAN_HOLD_THE_SUBJECT']
                   if 'H2' in eligible and RESOURCE.get(share) == 'ETF_STXRES' else []))
    result = {'meta': meta, 'bars': {share: [[bar['timestamp'], bar['open'], bar['high'], bar['low'], bar['close']]
                                              for bar in scoped]}, 'strategies': strategies}
    meta['config_hash'] = sha256(exact._json(result)).hexdigest()
    return result


def run_job(service, spec):
    destination = os.environ.get('LOCAL_BACKTEST_REPORT_DIR')
    if not destination:
        raise exact.RunUnavailable('The dashboard saved-results folder is not configured.')
    readiness, inputs = prepare(service, spec)
    if spec.get('preview_id') != readiness.get('preview_id'):
        raise exact.RunUnavailable('Retained inputs changed after review. Refresh the data preview and try again.')
    return exact.publish(Path(destination) / 'lab', build(spec, readiness, inputs))
