"""Build immutable Backtest Lab output offline. Use --demo for synthetic bars."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.backtest_lab.strategies import PROFILES, evaluate
from domain.backtest.data import Bar, Manifest, Session
from domain.backtest.engine import Costs, Signal, replay
from domain.strategy import DEFAULT_STRATEGY_REGISTRY


def demo():
    rng = random.Random(7)
    start = datetime(2026, 3, 2, tzinfo=timezone.utc)
    dates = []
    while len(dates) < 150:
        if start.weekday() < 5: dates.append(start)
        start += timedelta(days=1)
    sessions = tuple(Session(d.date().isoformat(), d.replace(hour=7), d.replace(hour=15)) for d in dates)
    charts, manifests = {}, []
    for name, initial, drift in (('SOL', 9800, .0012), ('NPN', 31000, .0009), ('SBK', 19500, .0004), ('ETF_STX40', 10000, .0005)):
        price = initial; bars = []; rows = []
        for session in sessions:
            opening = price; price *= 1+rng.gauss(drift, .017)
            high = max(opening,price)*(1+abs(rng.gauss(0,.006)))
            low = min(opening,price)*(1-abs(rng.gauss(0,.006)))
            volume = int(rng.uniform(.6e6,1.4e6)*(1.8 if abs(price/opening-1)>.02 else 1))
            values = [round(v,2) for v in (opening,high,low,price)]
            rows.append(dict(timestamp=session.key,open=values[0],high=values[1],low=values[2],close=values[3],volume=volume))
            bars.append(Bar(session.key, session.close_at+timedelta(hours=9), *(Decimal(str(v)) for v in values), Decimal(volume)))
        charts[name] = rows
        manifests.append(Manifest(name, 'EQUITY', 'ZAR', 'SYNTHETIC_FIXTURE', sessions[-1].close_at+timedelta(days=1),
            'RAW', 'TRADED_SHARES', 'TOY_WEEKDAY', True, 'SYNTHETIC', 'TOY_FIXED', 'NONE_VERIFIED', '1', sessions, tuple(bars)))
    return charts, manifests


def load_real(path, payload=None):
    """Load retained whole-source bars and separate benchmark closes for research."""
    from application.opportunities.source_resolution import archived_iress_research
    from application.backtest_lab.observed_history import from_chart, verify_ost_benchmark
    path = Path(path)
    if payload is None:
        payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('schema') != 'local-swing-dataset-v3':
        raise ValueError('local-swing-dataset-v3 required')
    share = archived_iress_research('SASOL', path.parent)
    benchmark = payload.get('charts', {}).get('ETF_STX40')
    if not share or not benchmark:
        raise ValueError('Archived IRESS Sasol and OST benchmark required')
    verify_ost_benchmark(benchmark, path.parent)
    history = from_chart('SASOL', share)
    history.admit(history.sessions[0].key, history.sessions[-1].key,
                  max(b.available_at for b in history.bars), activity_required=True)
    return {'SASOL': share['bars'], 'ETF_STX40': benchmark['bars']}, [history]


def add_research_histories(charts, manifests, intake_root):
    """Attach separate archived IRESS bars; never replace or graft a bar."""
    from application.backtest_lab.observed_history import from_chart, research_intake_history
    root = Path(intake_root)
    if not root.exists():
        return charts, manifests
    keys = set()
    for path in sorted((root/'normalized').glob('*.json')):
        try:
            if path.stat().st_size > 4_000_000:
                continue
            item = json.loads(path.read_text(encoding='utf-8'))
            key = item.get('instrument_id')
            if isinstance(key, str) and re.fullmatch('[A-Z]{2,8}', key) and item.get('product') == 'cash_equity':
                keys.add(key)
        except (OSError, ValueError, TypeError):
            continue
    if len(keys) > 20:
        raise ValueError('research intake exceeds bounded 20-share replay universe')
    choices = {key:research_intake_history(key, root) for key in keys if key != 'SASOL'}
    benchmark_days = [row['timestamp'][:10] for row in charts['ETF_STX40']]
    lo, hi = min(benchmark_days), max(benchmark_days)
    for key, payload in sorted(choices.items()):
        if payload is None:
            continue
        rows = [{'timestamp': b['session'], **{field: float(b[field]) for field in ('open', 'high', 'low', 'close', 'volume')}}
                for b in payload['bars'] if b.get('ohlc_consistent') and lo <= b['session'] <= hi and all(b.get(k) is not None for k in ('open','high','low','close','volume'))]
        # Do not silently bridge missing observations inside the selected window.
        expected = [b['session'] for b in payload['bars'] if lo <= b['session'] <= hi]
        if len(rows) < 51 or [r['timestamp'] for r in rows] != expected:
            continue
        chart = {'bars': rows, 'provenance': {'provider':'IRESS', 'source_sha256':payload['raw_hash'].removeprefix('sha256:'), 'acquired_at':payload['acquired_at']}}
        history = from_chart(key, chart)
        history.admit(history.sessions[0].key, history.sessions[-1].key, max(b.available_at for b in history.bars), activity_required=True)
        charts[key] = rows
        manifests.append(history)
    return charts, manifests


def append_public_bars(charts, manifests, capture_dir, *, allow_disagreements=False):
    """Append valid same-instrument Yahoo bars only after close overlap agreement."""
    from application.backtest_lab.observed_history import from_chart
    from application.opportunities.radar_price_capture import latest_close_history
    from application.opportunities.session_freshness import next_session
    updated = []
    for manifest in manifests:
        key = manifest.instrument
        try:
            public = latest_close_history(capture_dir, key)
        except (OSError, ValueError, KeyError, TypeError):
            updated.append(manifest); continue
        rows = charts[key]
        prior = {r['timestamp'][:10]: Decimal(str(r['close'])).quantize(Decimal('.01')) for r in rows}
        overlap = [(r['session'], prior[r['session']], Decimal(str(r['close'])).quantize(Decimal('.01')))
                   for r in public['rows'] if r['session'] in prior]
        recent = overlap[-60:]
        if ((not allow_disagreements and (len(recent) < 20 or any(a != b for _, a, b in recent)))
                or (allow_disagreements and recent and not any(a == b for _, a, b in recent))):
            updated.append(manifest); continue
        last = rows[-1]['timestamp'][:10]
        additions = []
        for row in public['rows']:
            if row['session'] <= last:
                continue
            if next_session(last) != row['session']:
                break
            if not row['ohlc_valid'] or row.get('volume') is None or row['volume'] < 0:
                break
            additions.append({'timestamp': row['session'], **{k:row[k] for k in ('open','high','low','close','volume')}, '_source':'YAHOO'})
            last = row['session']
        if not additions:
            updated.append(manifest); continue
        charts[key] = [{**r, '_source':'IRESS'} for r in rows] + additions
        receipt = {'provider':'YAHOO', 'capture_sha256':public['source_sha256'],
                   'acquired_at':public['acquired_at'], 'first_session':additions[0]['timestamp'],
                   'overlap':len(overlap), 'mismatches':sum(a != b for _, a, b in overlap),
                   'mismatch_sessions':[day for day,a,b in overlap if a != b][:100],
                   'recent_overlap':len(recent), 'recent_mismatches':sum(a != b for _, a, b in recent),
                   'basis':'SOURCE_LABELLED_RESEARCH_WITH_RETAINED_DIFFERENCES' if allow_disagreements else 'MATCHED_CLOSES_NOT_VERIFIED_PROVIDER_BASIS'}
        provenance = {'provider':'IRESS+YAHOO', 'source_sha256':manifest.source_sha256,
                      'acquired_at':manifest.acquired_at, 'supplemental_sources':[receipt]}
        history = from_chart(key, {'bars':charts[key], 'provenance':provenance})
        history.admit(history.sessions[0].key, history.sessions[-1].key, max(b.available_at for b in history.bars), activity_required=True)
        updated.append(history)
    return charts, updated


def append_sharedata_bars(charts, manifests, capture_dir):
    """Continue each mapped share using intact, source-labelled ShareData bars."""
    from application.backtest_lab.observed_history import from_chart
    from application.opportunities.session_freshness import next_session
    from application.opportunities.swing_data_quality import real_ohlc
    from application.opportunities.radar_price_capture import latest_close_history
    from application.opportunities.zebra_instruments import mappings
    from application.opportunities.zebra_public_handover import identity
    capture_dir = Path(capture_dir)
    symbols = mappings(capture_dir.parent/'radar-public-prices')
    updated = []
    for manifest in manifests:
        key = manifest.instrument
        code = symbols.get(key)
        paths = list(capture_dir.glob(code+'-*.json')) if code else []
        if not paths:
            updated.append(manifest); continue
        try:
            path = max(paths, key=lambda p:p.stat().st_mtime_ns)
            raw = path.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
            capture = json.loads(raw)
            if (path.stem != code+'-'+digest or capture.get('schema') != 'sharedata-chart-capture-v1'
                    or capture.get('symbol') != code or capture.get('provider') != 'SHAREDATA'
                    or capture.get('currency') != 'ZAR'):
                raise ValueError('ShareData identity or hash mismatch')
            from scripts.capture_sharedata_prices import verify_identity_receipt
            verify_identity_receipt(capture, capture_dir)
            for receipt in capture['raw_responses']:
                original = capture_dir/'raw'/(receipt['raw_sha256']+'.json')
                if hashlib.sha256(original.read_bytes()).hexdigest() != receipt['raw_sha256']:
                    raise ValueError('ShareData source hash mismatch')
            try:
                public = latest_close_history(capture_dir.parent/'radar-public-prices', key)
                public_closes = {r['session']:Decimal(str(r['close'])).quantize(Decimal('.01')) for r in public['rows']}
            except (OSError, ValueError, KeyError, TypeError):
                public, public_closes = None, {}
            consensus_file = capture_dir.parent.parent/'local-backtest'/('zebra-consensus-'+key+'.json')
            consensus = {}
            if consensus_file.exists():
                report = json.loads(consensus_file.read_text(encoding='utf-8'))
                if (report.get('instrument') != key or report.get('sha256') != identity({k:v for k,v in report.items() if k != 'sha256'})):
                    raise ValueError('consensus identity or hash mismatch')
                consensus = {r['session']:r for r in report['rows']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            updated.append(manifest); continue
        rows = charts[key]
        prior = {r['timestamp'][:10]: Decimal(str(r['close'])).quantize(Decimal('.01')) for r in rows}
        overlaps = [(r['session'],prior[r['session']],Decimal(str(r['close'])).quantize(Decimal('.01')))
                    for r in capture['rows'] if r['session'] in prior and r.get('close') is not None]
        recent = overlaps[-60:]
        if recent and not any(a == b for _,a,b in recent):
            updated.append(manifest); continue
        last = rows[-1]['timestamp'][:10]; additions = []
        for row in capture['rows']:
            if row['session'] <= last: continue
            if next_session(last) != row['session'] or not real_ohlc(row) or row.get('volume') is None or float(row['volume']) < 0: break
            value = Decimal(str(row['close'])).quantize(Decimal('.01'))
            decision = consensus.get(row['session'], {})
            additions.append({'timestamp':row['session'], **{k:float(row[k]) for k in ('open','high','low','close','volume')}, '_source':'SHAREDATA'})
            last = row['session']
        if not additions:
            updated.append(manifest); continue
        charts[key] = rows + additions
        receipt = {'provider':'SHAREDATA','capture_sha256':digest,'acquired_at':capture['acquired_at'],
                   'first_session':additions[0]['timestamp'],'overlap':len(overlaps),
                   'recent_overlap':len(recent),'recent_mismatches':sum(a != b for _,a,b in recent),
                   'basis':'SOURCE_LABELLED_RESEARCH_WITH_RETAINED_DIFFERENCES'}
        provenance = {'provider':manifest.provider+'+SHAREDATA', 'source_sha256':manifest.source_sha256,
                      'acquired_at':manifest.acquired_at,
                      'supplemental_sources':list(manifest.supplemental_sources)+[receipt]}
        history = from_chart(key, {'bars':charts[key],'provenance':provenance})
        history.admit(history.sessions[0].key,history.sessions[-1].key,max(b.available_at for b in history.bars),activity_required=True)
        updated.append(history)
    return charts, updated


def append_sharedata_benchmark(charts, provenance, capture_dir):
    """Extend the benchmark's close-only research series with matched observations."""
    from application.opportunities.session_freshness import next_session
    from application.opportunities.zebra_public_handover import identity
    from scripts.capture_sharedata_prices import verify_identity_receipt
    capture_dir = Path(capture_dir)
    paths = list(capture_dir.glob('STX40-*.json'))
    if not paths: return charts, provenance
    try:
        path = max(paths,key=lambda p:p.stat().st_mtime_ns); raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest(); data = json.loads(raw)
        if (path.stem != 'STX40-'+digest or data.get('schema') != 'sharedata-chart-capture-v1'
                or data.get('symbol') != 'STX40' or data.get('provider') != 'SHAREDATA'
                or data.get('currency') != 'ZAR'):
            raise ValueError('benchmark source identity mismatch')
        verify_identity_receipt(data,capture_dir)
        for receipt in data['raw_responses']:
            original = capture_dir/'raw'/(receipt['raw_sha256']+'.json')
            if hashlib.sha256(original.read_bytes()).hexdigest() != receipt['raw_sha256']:
                raise ValueError('benchmark source hash mismatch')
        report_path = capture_dir.parent.parent/'local-backtest/zebra-consensus-ETF_STX40.json'
        decisions = {}
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding='utf-8'))
            if report.get('instrument') != 'ETF_STX40' or report.get('sha256') != identity({k:v for k,v in report.items() if k != 'sha256'}):
                raise ValueError('benchmark consensus mismatch')
            decisions = {r['session']:r for r in report['rows']}
        rows = charts['ETF_STX40']
        prior = {r['timestamp'][:10]:Decimal(str(r['close'])).quantize(Decimal('.01')) for r in rows}
        overlaps = [(r['session'],prior[r['session']],Decimal(str(r['close'])).quantize(Decimal('.01')))
                    for r in data['rows'] if r['session'] in prior and r.get('close') is not None]
        recent = overlaps[-60:]
        if recent and not any(a==b for _,a,b in recent): return charts, provenance
        last = rows[-1]['timestamp'][:10]; additions = []
        for row in data['rows']:
            if row['session'] <= last: continue
            if next_session(last) != row['session'] or row.get('close') is None: break
            close = Decimal(str(row['close'])).quantize(Decimal('.01'))
            decision = decisions.get(row['session'],{})
            additions.append({'timestamp':row['session'],'open':None,'high':None,'low':None,
                              'close':float(close),'volume':None,'_source':'SHAREDATA'})
            last = row['session']
        if additions:
            charts['ETF_STX40'] = rows+additions
            provenance = {**provenance, 'supplemental_sources':list(provenance.get('supplemental_sources',[])) + [
                {'provider':'SHAREDATA','capture_sha256':digest,'acquired_at':data['acquired_at'],
                 'first_session':additions[0]['timestamp'],'recent_overlap':len(recent),
                 'recent_mismatches':sum(a!=b for _,a,b in recent),
                 'basis':'SOURCE_LABELLED_RESEARCH_WITH_RETAINED_DIFFERENCES'}]}
        return charts, provenance
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return charts, provenance


def add_sharedata_histories(charts, manifests, capture_dir):
    """Use a separate valid observed window for each additional mapped share."""
    from application.backtest_lab.observed_history import from_chart
    from application.opportunities.zebra_instruments import mappings
    from application.opportunities.zebra_public_handover import identity
    from application.opportunities.radar_price_capture import latest_close_history
    from application.opportunities.session_freshness import next_session
    from application.opportunities.swing_data_quality import real_ohlc
    from scripts.capture_sharedata_prices import verify_identity_receipt
    capture_dir = Path(capture_dir)
    symbols = mappings(capture_dir.parent/'radar-public-prices')
    benchmark_dates = [r['timestamp'][:10] for r in charts['ETF_STX40']]
    lo, hi = min(benchmark_dates), max(benchmark_dates)
    present = {m.instrument for m in manifests}
    for key, code in symbols.items():
        if key in present or key.startswith('ETF_'): continue
        paths = list(capture_dir.glob(code+'-*.json'))
        if not paths: continue
        try:
            path = max(paths,key=lambda p:p.stat().st_mtime_ns); raw = path.read_bytes()
            digest=hashlib.sha256(raw).hexdigest(); data=json.loads(raw)
            if (path.stem != code+'-'+digest or data.get('schema') != 'sharedata-chart-capture-v1'
                    or data.get('symbol') != code or data.get('provider') != 'SHAREDATA' or data.get('currency') != 'ZAR'):
                raise ValueError('source identity mismatch')
            verify_identity_receipt(data,capture_dir)
            for receipt in data['raw_responses']:
                if hashlib.sha256((capture_dir/'raw'/(receipt['raw_sha256']+'.json')).read_bytes()).hexdigest() != receipt['raw_sha256']:
                    raise ValueError('source receipt mismatch')
            # Without another retained provider to check symbol and scale, keep
            # the capture available to research but do not manufacture a replay.
            public = latest_close_history(capture_dir.parent/'radar-public-prices',key)
            public_by_day = {r['session']:Decimal(str(r['close'])).quantize(Decimal('.01')) for r in public['rows']}
            common = [(r['session'],Decimal(str(r['close'])).quantize(Decimal('.01')),public_by_day[r['session']])
                      for r in data['rows'] if r.get('close') is not None and r['session'] in public_by_day]
            # Establish a minimum identity/scale cross-check, then let the
            # per-session consensus split conflicting dates below. A handful of
            # disagreements must not discard unrelated, well-observed history.
            if common and not any(a==b for _,a,b in common): continue
            decisions = {}
            report_path = capture_dir.parent.parent/'local-backtest'/('zebra-consensus-'+key+'.json')
            if report_path.exists():
                report=json.loads(report_path.read_text(encoding='utf-8'))
                if report.get('instrument') != key or report.get('sha256') != identity({k:v for k,v in report.items() if k!='sha256'}):
                    raise ValueError('consensus mismatch')
                decisions={r['session']:r for r in report['rows']}
            groups=[]; current=[]
            for row in data['rows']:
                day=row['session']
                if not lo <= day <= hi: continue
                decision=decisions.get(day,{})
                value=Decimal(str(row['close'])).quantize(Decimal('.01')) if row.get('close') is not None else None
                conflicting = decision.get('state') in ('CONFLICT_AWAITING_THREE','NO_UNAMBIGUOUS_VOTES')
                if decision.get('state') == 'THREE_PROVIDER_AGREEMENT' and Decimal(decision['accepted_close']) != value: conflicting=True
                if day in public_by_day and value != public_by_day[day]:
                    evidence={(o['provider'],o['source_sha256'].removeprefix('sha256:')) for o in decision.get('observations',[])}
                    if (decision.get('state') != 'THREE_PROVIDER_AGREEMENT' or Decimal(decision['accepted_close']) != value
                            or ('SHAREDATA',digest) not in evidence or ('YAHOO',public['source_sha256']) not in evidence):
                        conflicting=True
                valid = (real_ohlc(row) and row.get('volume') is not None and float(row['volume'])>=0)
                gap = current and next_session(current[-1]['timestamp']) not in (None,day)
                if not valid or gap:
                    if current: groups.append(current); current=[]
                if valid:
                    current.append({'timestamp':day, **{k:float(row[k]) for k in ('open','high','low','close','volume')}, '_source':'SHAREDATA'})
            if current: groups.append(current)
            groups=[group for group in groups if len(group)>=51]
            if not groups: continue
            chosen=max(groups,key=lambda group:(group[-1]['timestamp'],len(group)))
            source={'provider':'SHAREDATA','source_sha256':digest,'acquired_at':data['acquired_at']}
            history=from_chart(key,{'bars':chosen,'provenance':source})
            history.admit(history.sessions[0].key,history.sessions[-1].key,max(b.available_at for b in history.bars),activity_required=True)
            charts[key]=chosen; manifests.append(history)
        except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError):
            continue
    return charts, manifests


def append_eodhd_benchmark(charts, provenance, capture_dir):
    """Extend the benchmark with observed EODHD closes, never invented bars."""
    from application.opportunities.session_freshness import next_session
    from scripts.capture_eodhd_history import load_eodhd_history
    folder = Path(capture_dir).parent
    try:
        source = load_eodhd_history(folder,'ETF_STX40','STX40')
        rows = charts['ETF_STX40']; prior = {r['timestamp'][:10]:Decimal(str(r['close'])).quantize(Decimal('.01')) for r in rows}
        overlap = [(r['session'], prior[r['session']], Decimal(str(r['close'])).quantize(Decimal('.01')))
                   for r in source['rows'] if r['session'] in prior]
        if overlap and not any(a == b for _,a,b in overlap): return charts, provenance
        last = rows[-1]['timestamp'][:10]; additions = []
        for row in source['rows']:
            if row['session'] <= last: continue
            if next_session(last) != row['session']: break
            additions.append({'timestamp':row['session'],'open':None,'high':None,'low':None,
                              'close':float(row['close']),'volume':None,'_source':'EODHD'})
            last = row['session']
        if additions:
            charts['ETF_STX40'] = rows + additions
            provenance = {**provenance, 'supplemental_sources':list(provenance.get('supplemental_sources',[])) + [
                {'provider':'EODHD','capture_sha256':source['source_sha256'],'raw_sha256':source['raw_sha256'],
                 'acquired_at':source['acquired_at'],'first_session':additions[0]['timestamp'],
                 'recent_overlap':len(overlap),'recent_mismatches':sum(a != b for _,a,b in overlap),
                 'basis':'SOURCE_LABELLED_RESEARCH_WITH_RETAINED_DIFFERENCES'}]}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError):
        pass
    return charts, provenance


def add_eodhd_histories(charts, manifests, capture_dir):
    """Use complete observed EODHD bars when they extend available research."""
    from application.backtest_lab.observed_history import from_chart
    from dataclasses import replace
    from application.opportunities.session_freshness import next_session
    from application.opportunities.swing_data_quality import real_ohlc
    from application.opportunities.zebra_instruments import mappings
    from scripts.capture_eodhd_history import load_eodhd_history

    folder = Path(capture_dir).parent
    registry = mappings(folder/'radar-public-prices')
    benchmark = charts.get('ETF_STX40', [])
    if not benchmark: return charts, manifests, {}
    lo, hi = benchmark[0]['timestamp'][:10], benchmark[-1]['timestamp'][:10]
    by_key = {m.instrument:m for m in manifests}; diagnostics = {}
    for key, code in sorted(registry.items()):
        if key.startswith('ETF_'): continue
        try:
            source = load_eodhd_history(folder,key,code)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError):
            continue
        groups = []; current = []
        for row in source['rows']:
            day = row['session']
            if not lo <= day <= hi: continue
            valid = real_ohlc(row) and row.get('volume') is not None and row['volume'] >= 0
            gap = current and next_session(current[-1]['timestamp']) not in (None,day)
            if not valid or gap:
                if current: groups.append(current); current=[]
            if valid:
                current.append({'timestamp':day, **{f:float(row[f]) for f in ('open','high','low','close','volume')}, '_source':'EODHD'})
        if current: groups.append(current)
        groups = [g for g in groups if len(g) >= 51]
        if not groups:
            diagnostics[key] = {'state':'NO_COMPLETE_RESEARCH_WINDOW'}; continue
        selected = max(groups,key=lambda g:(g[-1]['timestamp'],len(g)))
        existing = charts.get(key,[])
        if existing:
            # Keep an existing longer and equally recent coherent history.
            if existing[-1]['timestamp'][:10] >= selected[-1]['timestamp'] and len(existing) >= len(selected):
                diagnostics[key] = {'state':'EXISTING_HISTORY_RETAINED','eodhd_rows':len(selected)}; continue
            peer = {r['timestamp'][:10]:Decimal(str(r['close'])).quantize(Decimal('.01')) for r in existing}
            overlap = [r for r in selected if r['timestamp'] in peer]
            if overlap and not any(Decimal(str(r['close'])).quantize(Decimal('.01')) == peer[r['timestamp']] for r in overlap):
                diagnostics[key] = {'state':'SCALE_MISMATCH_EXISTING_RETAINED','eodhd_rows':len(selected)}; continue
            tail = [r for r in selected if r['timestamp'] > existing[-1]['timestamp'][:10]]
            if tail and next_session(existing[-1]['timestamp'][:10]) == tail[0]['timestamp']:
                old = by_key[key]
                existing_with_source = [{**r, '_source':r.get('_source', old.provider)} for r in existing]
                receipt = {'provider':'EODHD','capture_sha256':source['source_sha256'],'raw_sha256':source['raw_sha256'],
                           'acquired_at':source['acquired_at'],'first_session':tail[0]['timestamp'],
                           'recent_overlap':len(overlap),
                           'recent_mismatches':sum(Decimal(str(r['close'])).quantize(Decimal('.01')) != peer[r['timestamp']] for r in overlap),
                           'basis':'SOURCE_LABELLED_RESEARCH_WITH_RETAINED_DIFFERENCES'}
                provenance = {'provider':old.provider+'+EODHD','source_sha256':old.source_sha256,
                              'acquired_at':old.acquired_at,'supplemental_sources':list(old.supplemental_sources)+[receipt]}
                selected = existing_with_source+tail
                history = replace(from_chart(key,{'bars':selected,'provenance':provenance}),product=old.product)
                history.admit(history.sessions[0].key,history.sessions[-1].key,max(b.available_at for b in history.bars),activity_required=True)
                charts[key] = selected; by_key[key] = history
                diagnostics[key] = {'state':'REPLAY_HISTORY_EXTENDED','added_rows':len(tail),'rows':len(selected),
                    'first_session':selected[0]['timestamp'],'last_session':selected[-1]['timestamp'],
                    'raw_sha256':source['raw_sha256'],'acquired_at':source['acquired_at'],
                    'upstream_independence':'UNVERIFIED','product':history.product}
                continue
            if len(existing) >= len(selected):
                diagnostics[key] = {'state':'LONGER_EXISTING_HISTORY_RETAINED','eodhd_rows':len(selected)}; continue
        provenance = {'provider':'EODHD','source_sha256':source['source_sha256'],'acquired_at':source['acquired_at']}
        history = from_chart(key,{'bars':selected,'provenance':provenance})
        # AGOGE is an actively managed ETF, not an ordinary company share.
        if key == 'AGOGE': history = replace(history, product='ETF')
        history.admit(history.sessions[0].key,history.sessions[-1].key,max(b.available_at for b in history.bars),activity_required=True)
        charts[key] = selected; by_key[key] = history
        diagnostics[key] = {'state':'REPLAY_HISTORY_SELECTED','rows':len(selected),
            'first_session':selected[0]['timestamp'],'last_session':selected[-1]['timestamp'],
            'raw_sha256':source['raw_sha256'],'acquired_at':source['acquired_at'],
            'upstream_independence':'UNVERIFIED','product':history.product}
    ordered = [by_key[m.instrument] for m in manifests]
    ordered.extend(by_key[k] for k in sorted(set(by_key)-{m.instrument for m in manifests}))
    return charts, ordered, diagnostics


def apply_consensus_windows(charts, manifests, report_dir, *, allow_disagreements=False):
    """Keep observed contiguous research windows and report source conflicts."""
    from application.backtest_lab.observed_history import from_chart
    from application.opportunities.zebra_public_handover import identity
    from application.opportunities.session_freshness import next_session
    diagnostics = {}; updated = []
    by_key = {m.instrument:m for m in manifests}
    for key in list(by_key) + (['ETF_STX40'] if 'ETF_STX40' in charts else []):
        path = Path(report_dir)/('zebra-consensus-'+key+'.json')
        if not path.exists():
            diagnostics[key] = {'state':'NO_COMPARISON_AVAILABLE'}
            if key in by_key: updated.append(by_key[key])
            continue
        try:
            report = json.loads(path.read_text(encoding='utf-8'))
            if (report.get('schema') != 'zebra-close-consensus-v1' or report.get('instrument') != key
                    or report.get('sha256') != identity({k:v for k,v in report.items() if k!='sha256'})):
                raise ValueError('consensus identity or hash mismatch')
            checks = {r['session']:r for r in report['rows']}
            groups=[]; current=[]; differences=[]; excluded=0
            for row in charts[key]:
                day = row['timestamp'][:10]; decision = checks.get(day)
                differs = False
                if decision:
                    if decision['state'] in ('CONFLICT_AWAITING_THREE','NO_UNAMBIGUOUS_VOTES'):
                        differs = True
                        differences.append({'session':day,'state':decision['state'],'source_close':str(row['close']),'accepted_close':decision.get('accepted_close')})
                    elif decision.get('accepted_close') is not None:
                        if Decimal(str(row['close'])).quantize(Decimal('.01')) != Decimal(decision['accepted_close']):
                            differs = True
                            differences.append({'session':day,'state':'SELECTED_SOURCE_DIFFERS_FROM_CONSENSUS','source_close':str(row['close']),'accepted_close':decision['accepted_close']})
                gap = current and next_session(current[-1]['timestamp'][:10]) not in (None,day)
                if gap or (differs and not allow_disagreements):
                    if current: groups.append(current); current=[]
                if differs and not allow_disagreements: excluded += 1
                else: current.append(row)
            if current: groups.append(current)
            minimum = 51 if key != 'ETF_STX40' else 21
            usable = [group for group in groups if len(group)>=minimum]
            diagnostics[key] = {'state':'WINDOW_AVAILABLE' if usable else 'NO_USABLE_WINDOW',
                'excluded_conflicting_sessions':excluded,'conflicting_sessions':len(differences),'differences':differences,'valid_windows':len(groups),
                'comparison_checked_at':report.get('checked_at')}
            if not usable:
                if key == 'ETF_STX40': charts[key] = []
                else: charts.pop(key,None)
                continue
            chosen = max(usable,key=lambda group:(group[-1]['timestamp'],len(group)))
            diagnostics[key].update(first_session=chosen[0]['timestamp'][:10],last_session=chosen[-1]['timestamp'][:10],rows=len(chosen))
            charts[key] = chosen
            if key in by_key:
                m = by_key[key]
                provenance = {'provider':m.provider,'source_sha256':m.source_sha256,'acquired_at':m.acquired_at,
                              'supplemental_sources':list(m.supplemental_sources)}
                from dataclasses import replace
                updated.append(replace(from_chart(key,{'bars':chosen,'provenance':provenance}),product=m.product))
        except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError):
            diagnostics[key] = {'state':'COMPARISON_UNAVAILABLE'}
            if key in by_key: updated.append(by_key[key])
    return charts, updated, diagnostics


def build(charts, manifests, benchmark_provenance=None, consensus_windows=None, eodhd_windows=None):
    from domain.backtest.engine import CashEquity
    from application.backtest_lab.observed_history import CashListedETF
    costs = Costs(fee_bps=Decimal(8), minimum_fee=Decimal(60), spread_bps=Decimal(20), slippage_bps=Decimal(5))
    as_of = max(b.available_at for m in manifests for b in m.bars) + timedelta(days=8)
    results = []
    for sid, name, profile, version in PROFILES:
        DEFAULT_STRATEGY_REGISTRY.resolve(profile, version)
        signals, traces, rejected, count, passed = [], [], [], 0, None
        for manifest in manifests:
            if manifest.instrument == 'ETF_STX40': continue
            rows = charts[manifest.instrument]
            for i in range(50, len(rows)):
                conditions, stop = evaluate(sid, manifest.instrument, i, charts)
                if not conditions: continue
                count += 1
                if passed is None: passed = [0]*len(conditions)
                for k in range(len(conditions)):
                    if all(c['ok'] for c in conditions[:k+1]): passed[k] += 1
                if not all(c['ok'] for c in conditions):
                    rejected.append({'inst':manifest.instrument,'session':rows[i]['timestamp'],'trace':conditions})
                if all(c['ok'] for c in conditions) and stop is not None:
                    ident = manifest.instrument+'-'+rows[i]['timestamp']
                    decision = manifest.bars[i].available_at + timedelta(seconds=1)
                    signals.append(Signal(ident,manifest.instrument,rows[i]['timestamp'],decision,Decimal(str(stop)),
                        Decimal(420000),Decimal(12000),horizon=3,target_r=Decimal(2),
                        strategy_profile_id=profile,strategy_profile_version=version))
                    traces.append({'id':ident,'inst':manifest.instrument,'session':rows[i]['timestamp'],'stop':stop,'trace':conditions})
        adapters = {m.instrument:CashListedETF() if m.product == 'ETF' else CashEquity() for m in manifests}
        result = replay(manifests, signals, as_of=as_of, initial_cash=Decimal(1000000), costs=costs, adapters=adapters)
        equity = result['equity']; trades = result['trades']; peak = 1000000; drawdown = 0
        for point in equity:
            value=float(point['equity']); peak=max(peak,value); drawdown=min(drawdown,value/peak-1)
        net=float(equity[-1]['equity'])-1000000 if equity else 0
        stock_count=len({t['instrument'] for t in trades})
        bucket='Incubate: fewer than 30 trades, inconclusive' if len(trades)<30 else 'Reject: lost money' if net<0 else 'Reject: one stock' if stock_count<2 else 'Watchlist: drawdown' if drawdown<-.08 else 'Candidate: needs forward test'
        benchmark = {r['timestamp']:r['close'] for r in charts.get('ETF_STX40', [])}
        relative = []
        for trade in trades:
            start, end = benchmark.get(trade['entry_session']), benchmark.get(trade['exit_session'])
            capital = Decimal(trade['entry'])*Decimal(trade['quantity'])
            excess = (float(Decimal(trade['net_pnl'])/capital) - (end/start-1)) if start and end and capital else None
            relative.append({'id':trade['id'],'benchmark':'ETF_STX40','excess_return':excess,
                'basis':'TRADE_NET_PNL_OVER_ENTRY_NOTIONAL_LESS_MATCHED_BENCHMARK_CLOSE_RETURN' if excess is not None else 'ALIGNED_BENCHMARK_UNAVAILABLE'})
        results.append({'id':sid,'name':name,'source':'Existing snapshot' if sid=='swing' else 'Unvalidated daily-bar approximation',
            'desc':'Fixed 3-session horizon or 2R; no EMA21-close exit.', 'strategy_profile_id':profile,'strategy_profile_version':version,
            'conds':[c['c'] for c in conditions] if count else [],'funnel':{'checked':count,'passed':passed or []},
            'sum':{'signals':len(signals),'traded':len(trades),'win':round(sum(float(t['net_pnl'])>0 for t in trades)/len(trades)*100) if trades else None,
                   'net':round(net,2),'mdd':round(drawdown*100,2),'stocks':stock_count,'verdict':bucket},
            'engine_config_hash':result['config_hash'],'relative_outcomes':relative,'run':{'signals':traces,'rejected_bars':rejected,'decisions':result['decisions'],'trades':trades,'equity':equity}})
    bars = {name:[[r['timestamp'],r['open'],r['high'],r['low'],r['close']] for r in rows] for name,rows in charts.items() if all(r.get('open') is not None for r in rows)}
    synthetic = all(m.grade == 'SYNTHETIC' for m in manifests)
    limitations=['FULL_FILL_ASSUMPTION','CLOSE_PROXY_NOT_BROKER_FILL','DAILY_INTRABAR_PATH_UNKNOWN','DAILY_SETUP_THRESHOLDS_ARE_GUESSES']
    if not synthetic:
        limitations += ['OBSERVED_PROVIDER_SESSIONS_NOT_VERIFIED_EXCHANGE_CALENDAR', 'RECONSTRUCTED_HISTORICAL_AVAILABILITY', 'PRICE_ADJUSTMENT_AND_CORPORATE_ACTIONS_UNVERIFIED', 'NO_CORPORATE_ACTIONS_APPLIED']
        if consensus_windows and any(d.get('conflicting_sessions',0) for d in consensus_windows.values()):
            limitations.append('SOURCE_DISAGREEMENTS_RETAINED_IN_RESEARCH_REPLAY')
        if any(s.get('recent_mismatches',0) for m in manifests for s in m.supplemental_sources):
            limitations.append('SOURCE_HANDOVER_HAS_OVERLAP_DIFFERENCES')
        if any(m.product == 'ETF' for m in manifests):
            limitations.append('ETF_CASH_REPLAY_WITH_HYPOTHETICAL_COSTS')
        if len(manifests) == 1: limitations.append('SINGLE_INSTRUMENT_RESEARCH_ONLY')
    meta={'grade':'SYNTHETIC' if synthetic else 'ASSUMPTION_LIMITED','limitations':limitations,
        'cost_basis':costs.basis,'initial_cash':1000000,'created_at':as_of.isoformat(),
        'created_at_basis':'SIMULATED_AS_OF_NOT_WALL_CLOCK' if synthetic else 'RECONSTRUCTED_REPLAY_AS_OF_NOT_WALL_CLOCK',
        'data_basis':'SYNTHETIC_FIXTURE' if synthetic else 'SOURCE_LABELLED_RECONSTRUCTED_OHLCV_AND_BENCHMARK_CLOSES',
        'source_receipts': [] if synthetic else ([{'instrument':m.instrument,'product':m.product,'provider':m.provider,'source_sha256':m.source_sha256,'acquired_at':m.acquired_at,'supplemental_sources':m.supplemental_sources} for m in manifests] + ([{'instrument':'ETF_STX40','product':'ETF', **benchmark_provenance}] if benchmark_provenance else [])),
        'live_execution':False}
    if consensus_windows is not None: meta['consensus_windows'] = consensus_windows
    if eodhd_windows is not None: meta['eodhd_windows'] = eodhd_windows
    from application.opportunities.research_classification import classifications
    meta['research_classifications'] = classifications(bars)
    identity = {'bars':bars,'strategies':results,'meta':meta}
    config_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {'meta':{**meta,'config_hash':config_hash},'bars':bars,'strategies':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true'); parser.add_argument('--dataset'); parser.add_argument('--output-dir')
    parser.add_argument('--instrument', help='Run a single retained instrument with its original benchmark')
    parser.add_argument('--research-history-dir', default=str(ROOT.parent/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'))
    args=parser.parse_args()
    if args.demo == bool(args.dataset): parser.error('choose --demo or --dataset')
    payload = None if args.demo else json.loads(Path(args.dataset).read_text(encoding='utf-8'))
    charts, manifests = demo() if args.demo else load_real(args.dataset, payload)
    benchmark_provenance = None if args.demo else payload['charts']['ETF_STX40']['provenance']
    consensus_windows = None
    eodhd_windows = None
    if not args.demo:
        charts, benchmark_provenance = append_sharedata_benchmark(charts, benchmark_provenance, Path(args.dataset).parent/'sharedata-prices')
        charts, benchmark_provenance = append_eodhd_benchmark(charts, benchmark_provenance, Path(args.dataset).parent/'eodhd')
        charts, manifests = add_research_histories(charts, manifests, args.research_history_dir)
        charts, manifests = append_public_bars(charts, manifests, Path(args.dataset).parent/'radar-public-prices', allow_disagreements=True)
        charts, manifests = append_sharedata_bars(charts, manifests, Path(args.dataset).parent/'sharedata-prices')
        charts, manifests = add_sharedata_histories(charts, manifests, Path(args.dataset).parent/'sharedata-prices')
        charts, manifests, eodhd_windows = add_eodhd_histories(charts, manifests, Path(args.dataset).parent/'eodhd')
        charts, manifests, consensus_windows = apply_consensus_windows(charts, manifests, Path(args.dataset).parent.parent/'local-backtest', allow_disagreements=True)
    if args.instrument:
        matches = [m for m in manifests if m.instrument == args.instrument]
        if len(matches) != 1: parser.error('instrument must identify one retained history')
        manifests = tuple(matches)
        charts = {key:value for key,value in charts.items() if key in (args.instrument, 'ETF_STX40')}
        if consensus_windows is not None:
            consensus_windows = {k:v for k,v in consensus_windows.items() if k == args.instrument}
        if eodhd_windows is not None:
            eodhd_windows = {k:v for k,v in eodhd_windows.items() if k == args.instrument}
    run=build(charts,manifests,benchmark_provenance,consensus_windows,eodhd_windows)
    directory=Path(args.output_dir or os.environ.get('LOCAL_BACKTEST_REPORT_DIR',''))
    if not args.output_dir and not os.environ.get('LOCAL_BACKTEST_REPORT_DIR'): parser.error('set LOCAL_BACKTEST_REPORT_DIR or --output-dir')
    folder=directory/'lab';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(run['meta']['config_hash']+'.json')
    raw=(json.dumps(run,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
    if target.exists() and target.read_bytes()!=raw: raise ValueError('frozen run collision')
    if not target.exists():
        with target.open('xb') as f:f.write(raw)
    print(json.dumps({'run_id':target.stem,'path':str(target),'grade':run['meta']['grade']}))

if __name__=='__main__': main()
