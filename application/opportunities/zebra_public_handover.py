"""Source-labelled local research handovers for captured public history."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import os
from .radar_price_capture import latest_close_history


def identity(body):
    return sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def save(path, body):
    result = {**body, 'sha256': identity(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temp, path)
    return result


def update_public_handover(instrument, capture_dir, report_dir, research_root=None):
    """Keep Yahoo rows as their own instrument view; fuse Sasol only on overlap agreement."""
    from scripts.local_runtime import process_lock
    with process_lock(Path(report_dir)/'zebra-handover.lock'):
        return _update_public_handover(instrument, capture_dir, report_dir, research_root)


def _update_public_handover(instrument, capture_dir, report_dir, research_root):
    history = latest_close_history(capture_dir, instrument)
    body = {k: v for k, v in history.items() if k not in ('state', 'live_execution')}
    body.update(schema='zebra-public-instrument-v1', live_execution=False,
                source_hash_kind='NORMALIZED_CAPTURE_NOT_RAW_PROVIDER_BYTES')
    if instrument != 'SASOL':
        from application.backtest_lab.observed_history import research_intake_history
        root = Path(research_root) if research_root else Path(__file__).resolve().parents[3]/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'
        retained = research_intake_history(instrument, root)
        if retained:
            previous = {b['session']: Decimal(str(b['close'])).quantize(Decimal('.01')) for b in retained['bars']}
            overlap = [r for r in history['rows'] if r['session'] in previous]
            differences = [r['session'] for r in overlap if Decimal(str(r['close'])).quantize(Decimal('.01')) != previous[r['session']]]
            recent = overlap[-60:]
            recent_differences = [r['session'] for r in recent if Decimal(str(r['close'])).quantize(Decimal('.01')) != previous[r['session']]]
            body['iress_comparison'] = {'overlap':len(overlap), 'mismatch_count':len(differences),
                'mismatch_sessions':differences[:100],
                'recent_overlap':len(recent), 'recent_mismatch_count':len(recent_differences),
                'basis':'MATCHED_CLOSES_NOT_VERIFIED_PROVIDER_BASIS'}
            if len(recent) >= 20 and not recent_differences:
                earlier = [{'session':b['session'], 'close':float(b['close']),
                    'open':float(b['open']), 'high':float(b['high']), 'low':float(b['low']),
                    'volume':float(b['volume']), 'ohlc_valid':b['ohlc_consistent'],
                    'source':'IRESS', 'source_sha256':retained['raw_hash'],
                    'acquired_at':retained['acquired_at']} for b in retained['bars']]
                last = earlier[-1]['session']
                newer = [{**r, 'source':'YAHOO', 'source_sha256':'sha256:'+history['source_sha256'],
                          'acquired_at':history['acquired_at']} for r in history['rows'] if r['session'] > last]
                body['rows'] = earlier + newer
                body['source_policy'] = 'IRESS_FIRST_YAHOO_LATER_AFTER_CENTS_OVERLAP_MATCH'
    directory = Path(report_dir)
    save(directory / ('zebra-public-'+instrument+'.json'), body)
    result = {'instrument': instrument, 'rows': len(body['rows']),
              'state': 'MULTI_SOURCE_RESEARCH_HISTORY' if body.get('source_policy') else 'SEPARATE_PUBLIC_HISTORY'}
    sasol = directory/'zebra-handover.json'
    if instrument != 'SASOL' or not sasol.exists():
        return result
    current = json.loads(sasol.read_text(encoding='utf-8'))
    original = {k:v for k,v in current.items() if k != 'sha256'}
    if current.get('sha256') != identity(original):
        raise ValueError('existing zebra handover hash mismatch')
    prior = {r['session']: Decimal(str(r['close'])) for r in current['rows']}
    overlaps = [(r['session'], prior[r['session']], Decimal(str(r['close'])).quantize(Decimal('.01')))
                for r in history['rows'] if r['session'] in prior]
    mismatches = [date for date, left, right in overlaps if left.quantize(Decimal('.01')) != right]
    recent = overlaps[-60:]
    recent_mismatches = [date for date, left, right in recent if left.quantize(Decimal('.01')) != right]
    comparison = {'provider':'YAHOO', 'capture_sha256':history['source_sha256'],
                  'overlap':len(overlaps), 'mismatch_count':len(mismatches),
                  'mismatch_sessions':mismatches[:100], 'recent_overlap':len(recent),
                  'recent_mismatch_count':len(recent_mismatches), 'basis':'CENTS_OBSERVATION_MATCH_NOT_BASIS_CERTIFICATION'}
    result['comparison'] = comparison
    if len(recent) < 20 or recent_mismatches:
        result['state'] = 'SEPARATE_PENDING_OVERLAP_REVIEW'
        return result
    last = current['rows'][-1]['session']
    added = []
    from datetime import datetime, timedelta, timezone
    for row in history['rows']:
        if row['session'] <= last:
            continue
        day = datetime.fromisoformat(row['session']).replace(tzinfo=timezone.utc)
        added.append({'session':row['session'], 'close':str(row['close']), 'source':'yahoo',
            'raw_hash':None, 'capture_hash':'sha256:'+history['source_sha256'],
            'row_hash':'sha256:'+identity(row), 'available_at':(day+timedelta(days=1)).isoformat(),
            'original_acquired_at':history['acquired_at']})
        last = row['session']
    original['rows'].extend(added)
    original['yahoo_extension_rows'] = original.get('yahoo_extension_rows', 0) + len(added)
    original['yahoo_comparison'] = comparison
    save(sasol, original)
    result.update(state='SASOL_ZEBRA_EXTENDED', added=len(added))
    return result
