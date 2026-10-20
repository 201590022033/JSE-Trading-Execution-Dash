"""Credential-free OST export onboarding; whole-source prospective research."""
import csv
from html.parser import HTMLParser
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
from threading import RLock

from shadow_learning import timestamp
from .public_research import public_share_catalog, public_etf_catalog, _available_at
from .swing_data_quality import real_ohlc

SCHEMA = 'local-swing-dataset-v3'
POLICY = 'OST_PRIMARY_NO_YAHOO_FALLBACK'
LOCK = RLock()
ROOT = Path(__file__).resolve().parents[2] / 'runtime/local-swing-data'
RECEIPT_FIELDS = {'provider', 'origin_symbol', 'source_sha256', 'acquired_at',
                  'purpose', 'price_basis', 'volume_basis', 'historical_availability'}


class _OSTHistoryTable(HTMLParser):
    """Read only the price-history grid from OST's HTML-disguised .xls export."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and dict(attrs).get('id', '').endswith('_gvHistory'):
            self.in_table = True
        elif self.in_table and tag == 'tr':
            self.in_row, self.row = True, []
        elif self.in_row and tag in ('td', 'th'):
            self.in_cell, self.cell = True, []

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.in_cell and tag in ('td', 'th'):
            self.row.append(''.join(self.cell).strip())
            self.in_cell = False
        elif self.in_row and tag == 'tr':
            self.rows.append(self.row)
            if len(self.rows) > 10001:
                raise ValueError('maximum 10000 source rows')
            self.in_row = False
        elif self.in_table and tag == 'table':
            self.in_table = False


def _history_text(raw):
    source = raw.decode('utf-8-sig')
    if not source.lstrip().lower().startswith(('<div', '<table')):
        return source
    table = _OSTHistoryTable()
    table.feed(source)
    if not table.rows:
        raise ValueError('OST price-history table required')
    output = io.StringIO()
    csv.writer(output).writerows(table.rows)
    return output.getvalue()


def catalog():
    result = {}
    for key, row in {**public_share_catalog(), **public_etf_catalog()}.items():
        code = row['yahoo_symbol'].removesuffix('.JO')
        result[key] = {'instrument_id': key, 'name': row['name'],
            'sector': row.get('sector', 'index'), 'symbol': row['yahoo_symbol'],
            'ost_code': code, 'currency': 'ZAR', 'asset_class': row.get('asset_class', 'equity'),
            'history_url': 'https://securities.standardbank.co.za/ost/sp/FrontOfficeSecure/Product/ProductStatisticsHistory.aspx?marketType=18&productCode=' + code}
    return result


def normalize(payload, now):
    """Reuse existing bounded bar validation, then require broker receipts."""
    from .swing_research import validate_dataset
    if payload.get('source_policy') != POLICY:
        raise ValueError('explicit OST primary policy required')
    charts = payload.get('charts')
    cleaned = validate_dataset({'schema': 'local-swing-dataset-v1',
        'observed_at': payload['observed_at'], 'charts': charts}, now)
    observed = timestamp(cleaned['observed_at'])
    registry = catalog()
    for key, chart in cleaned['charts'].items():
        p = charts[key].get('provenance')
        if not isinstance(p, dict) or set(p) != RECEIPT_FIELDS:
            raise ValueError('explicit OST receipt required')
        if (p['provider'], p['origin_symbol'], p['purpose']) != ('OST', registry[key]['ost_code'], 'JSE_DAILY_RESEARCH'):
            raise ValueError('OST identity mismatch')
        if any(p[k] != 'UNVERIFIED' for k in ('price_basis', 'volume_basis', 'historical_availability')):
            raise ValueError('provider semantics remain unverified')
        import re
        if not isinstance(p['source_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', p['source_sha256']):
            raise ValueError('raw export hash required')
        acquired = timestamp(p['acquired_at'])
        if acquired > observed or observed - acquired > timedelta(days=4):
            raise ValueError('fresh genuine acquisition required')
        for bar in chart['bars']:
            close_at = datetime.fromisoformat(bar['timestamp']).replace(tzinfo=timezone.utc) + timedelta(hours=15)
            if close_at > acquired:
                raise ValueError('capture predates the completed session')
            if any(bar[k] is None or bar[k] <= 0 for k in ('high', 'low', 'close')) or bar['volume'] is None:
                raise ValueError('observed HLCV required')
        chart.update(provenance={**p, 'acquired_at': acquired.isoformat()},
                     research_only=True, historical_evaluation_allowed=False)
    cleaned.update(schema=SCHEMA, source='STANDARD_BANK_OST_DAILY_EXPORT', source_policy=POLICY)
    if 'research_charts' in payload:
        # A complete alternative chart is a separate numerical shadow input.
        # It never replaces or supplies individual fields to the OST chart.
        research = payload['research_charts']
        cash = {key for key, item in registry.items() if item['asset_class'] == 'equity'}
        if not isinstance(research, dict) or not research or set(research)-cash:
            raise ValueError('registered cash-share IRESS research charts required')
        from .supplemental_data import validate_receipt
        normalized = validate_dataset({'schema': 'local-swing-dataset-v1',
            'observed_at': payload['observed_at'], 'charts': research}, now)['charts']
        for key, chart in normalized.items():
            chart['provenance'] = validate_receipt(key,
                {**chart, 'provenance': research[key]['provenance']}, observed)
            chart.update(research_only=True, historical_evaluation_allowed=False)
        cleaned['research_charts'] = normalized
    if 'source_transform_receipts' in payload:
        from .source_transforms import validate_receipts
        cleaned['source_transform_receipts'] = validate_receipts(payload['source_transform_receipts'], cleaned.get('research_charts', {}))
    return cleaned


def parse_export(raw, key, acquired_at, now):
    """Strict observed OST cents header contract; never invent an open."""
    registry = catalog()
    if key not in registry or not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('registered instrument and bounded OST export required')
    acquired = timestamp(acquired_at)
    if acquired > now or now - acquired > timedelta(days=4):
        raise ValueError('fresh acquisition timestamp required')
    reader = csv.DictReader(io.StringIO(_history_text(raw)))
    required = {'Date', 'Closing (c)', 'High (c)', 'Low (c)', 'Volume'}
    columns = set(reader.fieldnames or ())
    allowed = required | {'Opening (c)', '# Deals', 'Value (R)', 'Move (%)', 'DY', 'EY', 'PE'}
    if not required <= columns or columns - allowed:
        raise ValueError('OST cents history headers required')
    source_rows, seen = [], set()
    for index, row in enumerate(reader):
        if index >= 10000:
            raise ValueError('maximum 10000 source rows')
        session = datetime.strptime(row['Date'].strip(), '%d %b %Y').date().isoformat()
        if session in seen:
            raise ValueError('duplicate session')
        seen.add(session)
        if _available_at(session) <= now:
            source_rows.append((session, row))
    # Native OST exports often extend decades back. Validate all source identities,
    # but numerical admission applies to the bounded newest 600 completed sessions.
    source_rows.sort(key=lambda item: item[0])
    bars = []
    for session, row in source_rows[-600:]:
        bar = {'timestamp': session, 'open': None}
        for field, column in [('high', 'High (c)'), ('low', 'Low (c)'), ('close', 'Closing (c)'), ('volume', 'Volume')]:
            value = float(row[column].replace(',', '').replace(' ', '').replace('\xa0', ''))
            if not math.isfinite(value) or value < 0 or (field != 'volume' and value <= 0):
                raise ValueError('invalid numeric source value')
            bar[field] = value if field == 'volume' else value / 100
        if 'Opening (c)' in row and row['Opening (c)'].strip():
            value = float(row['Opening (c)'].replace(',', '').replace(' ', '')) / 100
            if not math.isfinite(value) or value <= 0:
                raise ValueError('invalid actual opening price')
            bar['open'] = value
        bars.append(bar)
    if not bars:
        raise ValueError('no completed sessions')
    instrument = registry[key]
    chart = {'symbol': instrument['symbol'], 'currency': 'ZAR', 'interval': '1d', 'bars': bars[-600:],
        'provenance': {'provider': 'OST', 'origin_symbol': instrument['ost_code'],
            'source_sha256': sha256(raw).hexdigest(), 'acquired_at': acquired.isoformat(),
            'purpose': 'JSE_DAILY_RESEARCH', 'price_basis': 'UNVERIFIED',
            'volume_basis': 'UNVERIFIED', 'historical_availability': 'UNVERIFIED'}}
    normalized = normalize({'schema': SCHEMA, 'source_policy': POLICY,
        'observed_at': now.isoformat(), 'charts': {key: chart}}, now)
    return normalized['charts'][key]


def fresh_charts(dataset, now):
    return {key: deepcopy(chart) for key, chart in (dataset or {}).get('charts', {}).items()
            if timedelta(0) <= now - timestamp(chart['provenance']['acquired_at']) <= timedelta(days=4)}


def read_primary(folder=ROOT):
    path = folder / 'ost-primary.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def atomic_json(path, value):
    staged = path.with_suffix('.tmp')
    staged.write_bytes(json.dumps(value, allow_nan=False).encode('utf-8'))
    os.replace(staged, path)


def install_exports(exports, now, folder=ROOT):
    """Validate the entire batch before writes; replace whole instrument series."""
    if not isinstance(exports, list) or not 1 <= len(exports) <= 34:
        raise ValueError('bounded export batch required')
    parsed = {}
    for entry in exports:
        key = entry['instrument_id']
        if key in parsed:
            raise ValueError('one source per instrument per batch')
        parsed[key] = parse_export(entry['raw'], key, entry['acquired_at'], now)
    with LOCK:
        old = read_primary(folder)
        charts = fresh_charts(old, now)
        for key, chart in parsed.items():
            prior = (old or {}).get('charts', {}).get(key)
            if prior and timestamp(chart['provenance']['acquired_at']) < timestamp(prior['provenance']['acquired_at']):
                raise ValueError('older receipt cannot replace newer export')
            # Reuploading the same bytes cannot rejuvenate an acquisition receipt.
            if prior and chart['provenance']['source_sha256'] == prior['provenance']['source_sha256']:
                chart = deepcopy(prior)
            charts[key] = chart
        data = normalize({'schema': SCHEMA, 'source_policy': POLICY,
            'observed_at': now.isoformat(), 'charts': charts}, now)
        folder.mkdir(parents=True, exist_ok=True)
        # Content-addressed archives are bounded, deduplicated source files, never browser data.
        archive = folder / 'ost-exports'; archive.mkdir(exist_ok=True)
        for entry in exports:
            digest = sha256(entry['raw']).hexdigest()
            suffix = '.xls' if entry['raw'].lstrip().lower().startswith((b'<div', b'<table')) else '.csv'
            path = archive / (entry['instrument_id'] + '-' + digest + suffix)
            if not path.exists(): path.write_bytes(entry['raw'])
        from .prospective_prices import record_capture
        for key, chart in parsed.items():
            receipt = chart['provenance']
            record_capture(folder, key, 'OST', chart, receipt['acquired_at'], receipt['source_sha256'])
        latest = folder / 'latest.json'
        if latest.exists() and not old:
            (folder / 'before-ost-primary.json').write_bytes(latest.read_bytes())
        atomic_json(folder / 'ost-primary.json', data)
        atomic_json(latest, data)
    return coverage(data, now)


def coverage(dataset, now):
    active = (dataset or {}).get('source_policy') == POLICY
    fresh = fresh_charts(dataset, now) if active else {}
    result = []
    for key, item in catalog().items():
        chart = (dataset or {}).get('charts', {}).get(key) if active else None
        bars = chart['bars'] if chart else []
        invalid = sum(not b['low'] <= b['close'] <= b['high'] for b in bars)
        missing_open = sum(b.get('open') is None for b in bars)
        full = bool(bars) and all(real_ohlc(b) for b in bars)
        state = 'WAITING_FOR_EXPORT' if not chart else 'EXPIRED' if key not in fresh else 'OHLCV_PRESENT' if full else 'PARTIAL_HLCV'
        p = chart.get('provenance', {}) if chart else {}
        result.append({**item, 'state': state, 'bars': len(bars),
            'last_session': bars[-1]['timestamp'] if bars else None,
            'missing_open_bars': missing_open, 'invalid_hlc_bars': invalid,
            'acquired_at': p.get('acquired_at'), 'source_sha256': p.get('source_sha256'),
            'expires_at': (timestamp(p['acquired_at']) + timedelta(days=4)).isoformat() if p else None,
            'historical_evaluation_allowed': False, 'real_data_admitted': False})
    return {'schema': 'ost-onboarding-status-v1', 'source_policy': POLICY,
        'primary_active': active, 'checked_at': now.isoformat(), 'instruments': result,
        'context_pending': [{'instrument_id': 'CFD_REF_GOLD', 'state': 'SOURCE_CONTRACT_REQUIRED', 'reason': 'Gold futures, spot and CFD are different products.'},
                            {'instrument_id': 'CFD_REF_USDZAR', 'state': 'SOURCE_CONTRACT_REQUIRED', 'reason': 'USD/ZAR history and quotation units require a verified export contract.'}],
        'credentials_stored': False, 'automatic_download': False,
        'live_execution': False, 'real_data_admitted': False}


class LocalOSTFetcher:
    """On-demand research consumes the same primary exports, without network."""
    def __init__(self, dataset, now):
        self.charts = fresh_charts(dataset, now)

    def get_chart(self, symbol, period):
        for chart in self.charts.values():
            if chart['symbol'] == symbol:
                result = deepcopy(chart)
                for bar in result['bars']: bar['timestamp'] += 'T00:00:00+02:00'
                return result
        raise ValueError('fresh OST export unavailable; Yahoo fallback disabled')
