"""Bounded source receipts for prospective research; never canonical prices."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from shadow_learning import timestamp
from .public_research import _available_at

MAPPINGS = {'SASOL': ('SOL.JO', 'IRESS', 'SOL.JSE', 'OHLCV'),
            'ETF_STX40': ('STX40.JO', 'OST', 'STX40', 'HLCV_CLOSE_BENCHMARK')}


def validate_receipt(key, chart, observed):
    if key in MAPPINGS:
        symbol, provider, origin, purpose = MAPPINGS[key]
    else:
        from .ost_data import catalog
        item = catalog()[key]
        if item['asset_class'] != 'equity':
            raise ValueError('Registered cash-share IRESS identity required')
        symbol, provider, origin, purpose = item['symbol'], 'IRESS', item['ost_code']+'.JSE', 'OHLCV'
    p = chart['provenance']
    if chart['symbol'] != symbol or not isinstance(p, dict) or set(p) != {
        'provider', 'origin_symbol', 'source_sha256', 'acquired_at', 'purpose',
        'price_basis', 'volume_basis', 'historical_availability'}:
        raise ValueError('explicit source receipt required')
    if (p['provider'], p['origin_symbol'], p['purpose']) != (provider, origin, purpose):
        raise ValueError('source identity mismatch')
    if any(p[k] != 'UNVERIFIED' for k in ('price_basis', 'volume_basis', 'historical_availability')):
        raise ValueError('source semantics have not been admitted')
    if not isinstance(p['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', p['source_sha256']):
        raise ValueError('source hash required')
    acquired = timestamp(p['acquired_at'])
    if acquired > observed or observed-acquired > timedelta(days=4):
        raise ValueError('current source acquisition required')
    # Capture may follow the JSE 17:00 SAST close before our conservative
    # next-UTC-day usability cutoff. Validation above already enforces that
    # cutoff at upload observation; retain the actual earlier capture time.
    if any(datetime.fromisoformat(b['timestamp'][:10]).replace(tzinfo=timezone.utc)
           + timedelta(hours=15) > acquired for b in chart['bars']):
        raise ValueError('source captured before the session close')
    if provider == 'IRESS':
        from .swing_data_quality import real_ohlc
        if not all(real_ohlc(b) for b in chart['bars']):
            raise ValueError('complete whole-source OHLC required')
    elif any(b.get('open') is not None for b in chart['bars']):
        raise ValueError('OST benchmark opens are unavailable')
    return {**p, 'acquired_at': acquired.isoformat()}


def current_research_charts(dataset, now):
    if (dataset or {}).get('schema') == 'local-swing-dataset-v3':
        from .ost_data import fresh_charts
        result = fresh_charts(dataset, now)
        for key, chart in dataset.get('research_charts', {}).items():
            # An explicitly selected expired research receipt does not silently
            # fall back to another provider for the same numerical snapshot.
            result.pop(key, None)
            acquired = timestamp(chart['provenance']['acquired_at'])
            if acquired <= now and now-acquired <= timedelta(days=4):
                result[key] = deepcopy(chart)
        return result
    result = {}
    for key, chart in (dataset or {}).get('research_charts', {}).items():
        acquired = timestamp(chart['provenance']['acquired_at'])
        if acquired <= now and now-acquired <= timedelta(days=4):
            result[key] = deepcopy(chart)
    return result


def input_status(dataset, now):
    from .swing_technical import snapshot
    charts = current_research_charts(dataset, now)
    sasol = charts.get('SASOL')
    benchmark = charts.get('ETF_STX40')
    feature = snapshot(sasol, evaluated_at=now, benchmark_chart=benchmark) if sasol else None
    return {'state': 'INTEGRATED_RESEARCH_ONLY' if charts else 'UNAVAILABLE',
        'schema': (dataset or {}).get('schema'), 'real_data_admitted': False,
        'historical_evaluation_allowed': False,
        'charts': {key: {'provider': c['provenance']['provider'],
            'origin_symbol': c['provenance']['origin_symbol'],
            **{field: c['provenance'][field] for field in ('price_basis', 'volume_basis', 'historical_availability')},
            'source_sha256': c['provenance']['source_sha256'],
            'acquired_at': c['provenance']['acquired_at'],
            'last_session': c['bars'][-1]['timestamp'],
            'bars': len(c['bars']), 'purpose': c['provenance']['purpose'],
            'missing_open_bars': sum(b.get('open') is None for b in c['bars']),
            'latest_open': c['bars'][-1].get('open')} for key,c in charts.items()},
        'sasol': {'state': feature['state'], 'session': feature.get('session'),
                  'missing': feature.get('missing', []), 'values': feature.get('values'),
                  'provider': sasol['provenance']['provider'],
                  'latest_open': sasol['bars'][-1].get('open')} if feature else None,
        'limitations': 'Current input preview, not a frozen decision or matured outcome. Source adjustment/actions, volume and historical availability remain unverified.'}
