"""Daily radar built from retained Zebra observations; no provider requests."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median
import json
import math
from .intraday_evaluation import _trace
from application.opportunities.session_freshness import latest_expected_session, next_session
from application.opportunities.swing_technical import ema20_reclaimed, snapshot

_FIELDS = ('open', 'high', 'low', 'close', 'volume')
_STATES = {'SINGLE_SOURCE', 'AGREEMENT', 'THREE_PROVIDER_AGREEMENT'}
_FEATURE_PROFILE_VERSION = '1.1.2'
_NAMES = (('ema_uptrend', 'Close above EMA20 above EMA50'),
          ('breakout20', 'Close above prior 20-session high'),
          ('ema20_reclaim', 'Price reclaims EMA20 within the last 3 sessions in an uptrend'),
          ('rsi_50_70', 'RSI between 50 and 70'),
          ('volume_above_prior20', 'Volume above its prior 20-session median'),
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


def _research_chart(folder, instrument, now, *, include_volume_alternatives=False):
    """Use the latest contiguous Zebra close suffix, with explicit quality.

    Retained priority selections in a conflict are research candidates, never
    consensus; absent fields remain absent. Future receipts are never used.
    """
    if not instrument or not instrument.replace('_', '').isalnum():
        return None, None
    expected = latest_expected_session(now)
    cutoff=expected or (now.astimezone(timezone.utc).date()-timedelta(days=1)).isoformat()
    try:
        daily=json.loads((Path(folder)/'daily-cache'/(instrument+'.json')).read_text(encoding='utf-8'))['daily']
        rows=daily['history']['rows']
        by_day={}; ambiguous=set()
        for row in rows:
            try:
                day=row['session']; datetime.strptime(day,'%Y-%m-%d')
            except (KeyError,TypeError,ValueError):
                continue
            if day in ambiguous: continue
            if day in by_day:
                # Do not silently select a revision. Treat only this date as a gap.
                by_day.pop(day); ambiguous.add(day); continue
            if day <= cutoff: by_day[day]=row
        accepted=[]
        for day in sorted(by_day):
            row=by_day[day]; bar={'timestamp':day+'T00:00:00+00:00'}; provenance=[]
            fields=row.get('fields')
            if not isinstance(fields,dict): continue
            for field in _FIELDS:
                detail=fields.get(field,{})
                if not isinstance(detail,dict): continue
                state=detail.get('state'); stamp_text=detail.get('acquired_at')
                if state not in _STATES and state!='CONFLICT_NO_CONSENSUS': continue
                if not stamp_text or not detail.get('source'): continue
                try: stamp=datetime.fromisoformat(stamp_text.replace('Z','+00:00'))
                except (ValueError,TypeError,AttributeError): continue
                if stamp.tzinfo is None or stamp.utcoffset() is None or not datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(hours=15) <= stamp <= now: continue
                try: value=float(detail['value'])
                except (ValueError,TypeError,KeyError,OverflowError): continue
                if not math.isfinite(value) or (value<0 if field=='volume' else value<=0): continue
                bar[field]=value
                alternatives=[]; omitted=0
                if state=='CONFLICT_NO_CONSENSUS' or (field=='volume' and include_volume_alternatives):
                    candidates=detail.get('alternatives',[])
                    if not isinstance(candidates,list): candidates=[]; omitted+=1
                    for candidate in candidates:
                        try:
                            if not isinstance(candidate,dict) or not isinstance(candidate.get('source'),str) or not candidate['source'].strip(): raise ValueError('source required')
                            received=datetime.fromisoformat(candidate['acquired_at'].replace('Z','+00:00'))
                            candidate_value=float(candidate['value'])
                            if received.tzinfo is None or received.utcoffset() is None or not datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(hours=15) <= received <= now: raise ValueError('receipt outside evaluation window')
                            if not math.isfinite(candidate_value) or (candidate_value<0 if field=='volume' else candidate_value<=0): raise ValueError('invalid value')
                            alternatives.append({'source':candidate['source'],'value':candidate_value,
                                'acquired_at':received.isoformat(),'source_sha256':candidate.get('source_sha256'),
                                'field_source_sha256':candidate.get('field_source_sha256')})
                        except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
                            omitted+=1
                provenance.append({'field':field,'session':day,'source':detail['source'],
                    'value':value,'source_sha256':detail.get('source_sha256'),
                    'field_source_sha256':detail.get('field_source_sha256'),
                    'upstream_independence':detail.get('upstream_independence'),
                    'received_at':stamp.isoformat(),'state':state,
                    'alternatives':alternatives,'omitted_alternatives':omitted})
            if 'close' in bar: accepted.append((day,bar,provenance))
        if not accepted: return None, None
        suffix=[accepted[-1]]
        if expected:
            for item in reversed(accepted[:-1]):
                if next_session(item[0])!=suffix[0][0]: break
                suffix.insert(0,item)
                if len(suffix)>=100: break
        bars=[item[1] for item in suffix]
        provenance=[entry for _,_,entries in suffix for entry in entries]
        stale=(suffix[-1][0]!=expected) if expected else None
        conflicts=[p for p in provenance if p['state']=='CONFLICT_NO_CONSENSUS']
        metadata_session=daily.get('latest_session')
        metadata_mismatch=bool(metadata_session and metadata_session!=suffix[-1][0])
        partial=bool(ambiguous or metadata_mismatch) or any(any(field not in bar for field in _FIELDS) for bar in bars)
        quality={'state':'CALENDAR_UNVERIFIED' if not expected else 'STALE_RESEARCH' if stale else 'PROVISIONAL_RESEARCH' if conflicts else 'PARTIAL_RESEARCH' if partial else 'CURRENT_RESEARCH',
                 'expected_session':expected,'session':suffix[-1][0], 'stale':stale,
                 'calendar_unverified':not bool(expected), 'provisional':bool(conflicts), 'partial':partial, 'conflict_count':len(conflicts), 'fields':provenance,
                 'metadata_latest_session':metadata_session, 'metadata_session_mismatch':metadata_mismatch,
                 'ambiguous_sessions':sorted(ambiguous), 'omitted_alternatives':sum(p['omitted_alternatives'] for p in provenance),
                 'limitation':'Historical calculations use currently retained receipts; not a point-in-time availability claim.'}
        return {'symbol':instrument,'interval':'1d','currency':'ZAR','bars':bars}, quality
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError):
        return None, None


def _volume_sensitivity(rows, volume_by_session, lookback, max_gaps):
    """Compare observed alternative providers against their own prior medians."""
    if len(rows) < lookback + 1:
        return []
    prior_rows = rows[-lookback-1:-1]
    selected_prior = [row['volume'] for row in prior_rows if 'volume' in row]
    last = volume_by_session.get(rows[-1]['timestamp'][:10])
    minimum = lookback - max_gaps
    if not last or len(selected_prior) < minimum or median(selected_prior) <= 0:
        return []
    selected_pass = last['value'] > median(selected_prior)
    comparisons = []
    for alternative in last['alternatives']:
        source = alternative['source']
        if source == last['source']:
            continue
        history = []
        for row in prior_rows:
            field = volume_by_session.get(row['timestamp'][:10])
            if field is None:
                continue
            matches = [item['value'] for item in [field, *field['alternatives']] if item['source'] == source]
            if len(matches) == 1:
                history.extend(matches)
        if len(history) < minimum or median(history) <= 0:
            continue
        baseline = median(history)
        comparisons.append({'source':source, 'prior_sessions':len(history), 'prior_median':baseline,
                            'volume':alternative['value'], 'acquired_at':alternative['acquired_at'],
                            'classification_changed':(alternative['value'] > baseline) != selected_pass})
    return comparisons


def momentum_state(service, instrument, trace):
    """Display-only daily reference using the selected fields available at evaluation."""
    from application.backtest_lab.momentum_targets import (
        MAX_GAP_SESSIONS, VOLUME_LOOKBACK, features, peer_projection, prepare_peers,
    )
    from .sector_context import sector_context

    if not trace.get('session'):
        return None
    now = datetime.fromisoformat(trace['evaluated_at'])
    chart, quality = _research_chart(service.folder, instrument, now, include_volume_alternatives=True)
    horizon = 3
    minimum_samples = 30
    projection = {'status':'FIXED_TARGET_FALLBACK', 'sample_count':0, 'minimum_samples':minimum_samples,
                  'horizon_sessions':horizon, 'fixed_target_r':2}
    result = {'session':trace['session'], 'data_quality':'PARTIAL', 'exhaustion_label':'NO_DATA',
              'projected_excursion':projection}
    if not chart or quality['session'] != trace['session']:
        return result

    rows = chart['bars']
    current = features(rows, len(rows)-1, max_volume_gaps=MAX_GAP_SESSIONS)
    result['stale'] = quality['stale']
    if current is None:
        return result

    momentum = current['momentum_atr']
    change = current['momentum_change_atr']
    steady_band = 0.25  # ATR units, display classification only.
    if abs(change) <= steady_band:
        label = 'STEADY'
    elif change > 0:
        label = 'RISING'
    else:
        label = 'EXHAUSTION_RISK' if momentum <= 0 else 'SLOWING'

    volume_fields = {item['session']:item for item in quality['fields'] if item['field']=='volume'}
    prior = rows[-VOLUME_LOOKBACK-1:-1]
    missing = sum('volume' not in row for row in prior)
    last_volume = volume_fields.get(quality['session'], {})
    ratio = current['relative_volume']
    recent_fields = [item for item in quality['fields']
                     if item['field'] in ('close','high','low','volume') and item['session'] >= prior[0]['timestamp'][:10]]
    provisional = any(item['state'] == 'CONFLICT_NO_CONSENSUS' for item in recent_fields)
    if ratio is not None and missing:
        result['data_quality'] = 'GAP_TOLERATED'
    elif ratio is None or provisional or quality['calendar_unverified']:
        result['data_quality'] = 'PARTIAL'
    elif any(item['state'] == 'SINGLE_SOURCE' for item in recent_fields):
        result['data_quality'] = 'SINGLE_SOURCE'
    else:
        result['data_quality'] = 'CONFIRMED'
    result.update(momentum_atr=momentum, momentum_change_atr=change, exhaustion_label=label, provisional=provisional,
                  relative_volume=ratio, volume_source=last_volume.get('source'),
                  volume_value=last_volume.get('value'), volume_acquired_at=last_volume.get('received_at'),
                  volume_prior_sessions=len(prior)-missing, volume_missing_sessions=missing,
                  alternate_volume=_volume_sensitivity(rows, volume_fields, VOLUME_LOOKBACK, MAX_GAP_SESSIONS))

    peers = {}
    for peer in sector_context(service, instrument, now=now)['universe']:
        if peer == instrument:
            continue
        peer_chart, _ = _research_chart(service.folder, peer, now)
        if peer_chart:
            peers[peer] = [peer_chart['bars']]
    cases = prepare_peers(peers, horizon)
    estimate = peer_projection(rows, len(rows)-1, horizon, cases, minimum_samples=minimum_samples)
    projection.update({k:v for k,v in estimate.items() if k not in ('features','variant')})
    return result


def _apply_component_windows(data, chart):
    """Evaluate the existing breakout/reclaim rules on their own real fields.

    The shared snapshot gates all OHLC-dependent values on the entire chart.
    This research-only adapter keeps the same rule thresholds while limiting
    the required highs to the explicit 20/10-session windows. It does not
    construct missing OHLC bars or treat provisional inputs as consensus.
    """
    if not chart or not data.get('conditions') or not data.get('values'):
        return []
    bars=chart['bars']; values=data['values']; conditions=data['conditions']; used=[]
    def valid_highs(items):
        try:
            return all(math.isfinite(float(b['high'])) and float(b['high'])>0 and
                       float(b['high'])>=float(b['close']) for b in items)
        except (KeyError,ValueError,TypeError,OverflowError):
            return False
    if conditions.get('breakout20') is None and len(bars)>=21 and valid_highs(bars[-21:-1]):
        high=max(float(b['high']) for b in bars[-21:-1])
        values['prior_high20']=high
        conditions['breakout20']=float(bars[-1]['close'])>high
        used.append('breakout20')
    if conditions.get('ema20_reclaim') is None and len(bars)>=50 and valid_highs(bars[-11:-1]) and conditions.get('ema_uptrend') is not None:
        closes=[float(b['close']) for b in bars]
        values['prior_high10']=max(float(b['high']) for b in bars[-11:-1])
        conditions['ema20_reclaim']=bool(conditions['ema_uptrend'] and ema20_reclaimed(closes))
        used.append('ema20_reclaim')
    return used


def evaluate_watches(service, *, now=None, instrument=None):
    now = now or datetime.now(timezone.utc)
    watches = service.store.list_watches()
    if instrument is not None:
        watches = [watch for watch in watches if watch['instrument'] == instrument]
    from .benchmark_refresh import resolve_benchmark_chart
    charts = {}
    chart_quality = {}
    for key in {w['instrument'] for w in watches}:
        # The research path may show Zebra priority selections, with conflicts
        # and older sessions distinctly labelled; never fill absent OHLC fields.
        charts[key], chart_quality[key] = _research_chart(service.folder, key, now)
    benchmark_results = {}
    results = {}
    for watch in watches:
        key = watch['instrument']
        chart=charts.get(key); quality=chart_quality.get(key)
        benchmark_key=watch.get('benchmark')
        target=quality.get('session') if quality else None
        cache_key=(benchmark_key,target)
        if benchmark_key and cache_key not in benchmark_results:
            benchmark_results[cache_key]=resolve_benchmark_chart(service, benchmark_key, now=now, target_session=target)
        benchmark_chart, benchmark_state=benchmark_results.get(cache_key,(None,'UNAVAILABLE'))
        calc_clock=now
        if chart and quality and (quality['stale'] or quality['calendar_unverified']):
            calc_clock=datetime.fromisoformat(quality['session']).replace(tzinfo=timezone.utc)+timedelta(days=1,seconds=1)
        data = snapshot(chart, evaluated_at=calc_clock, benchmark_chart=benchmark_chart,
                        feature_profile_version=_FEATURE_PROFILE_VERSION)
        component_windows = _apply_component_windows(data, chart)
        conditions = data.get('conditions', {})
        rules = []
        values = data.get('values', {})
        details = {
            'ema_uptrend': (data.get('last_close'), 'EMA20 %s; EMA50 %s' % (values.get('ema20'), values.get('ema50'))),
            'breakout20': (data.get('last_close'), values.get('prior_high20')),
            'ema20_reclaim': (data.get('last_close'), values.get('ema20')),
            'rsi_50_70': (values.get('rsi14_wilder'), '50 to 70'),
            'volume_above_prior20': (values.get('relative_volume20_median'), '1.0 times prior median (mean if median is zero)'),
            'outperforming_benchmark20': (values.get('relative_return20'), '0 excess return'),
        }
        for name, description in _NAMES:
            passed_rule = conditions.get(name)
            value, threshold = details[name] if passed_rule is not None else (None, None)
            rules.append(_trace(name, False, passed_rule, value, threshold, [], description if passed_rule is not None else description + ' - missing or disputed source fields'))
        passed = sum(r['state'] == 'PASS' for r in rules)
        unknown = sum(r['state'] == 'UNKNOWN' for r in rules)
        results[key] = {'instrument': key, 'strategy_id': 'jse_swing_3_5d',
                        'strategy_version': _FEATURE_PROFILE_VERSION,
                        'timeframe_minutes': None, 'evaluated_at': now.isoformat(),
                        'state': 'UNKNOWN' if unknown == len(rules) else 'WATCHING', 'rules': rules,
                        'entry_conditions_met': conditions.get('core_setup') if not (quality or {}).get('stale') and not (quality or {}).get('calendar_unverified') else None,
                        'passed': passed, 'unknown': unknown, 'applicable': len(rules),
                        'session': data.get('session'), 'missing': data.get('missing', []),
                        'source_bars': data.get('source_bars', 0), 'source_sha256': data.get('source_sha256'), 'values': data.get('values', {}), 'benchmark_instrument': watch.get('benchmark'),
                        'benchmark_cache_status': benchmark_state,
                        'benchmark_quality': benchmark_chart.get('data_quality') if benchmark_chart else None,
                        'data_quality': quality, 'calculation_clock': calc_clock.isoformat(),
                        'component_evaluation_version':'zebra-component-windows-v2', 'component_window_rules':component_windows,
                        'research_only': True, 'live_signal': False}
    return results
