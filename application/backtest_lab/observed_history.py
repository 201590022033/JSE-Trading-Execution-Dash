"""Explicit retrospective replay input; provider sessions are not an exchange calendar."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import re
import hashlib
import json
from domain.backtest.data import Bar, Session, number
from domain.evaluation.experiment import configuration_hash, utc


def research_intake_history(key, root):
    """Find exact, hash-bound retained IRESS research history for one share."""
    root = Path(root)
    selected = None
    for path in sorted((root/'normalized').glob('*.json')):
        raw = path.read_bytes()
        if len(raw) > 4_000_000 or hashlib.sha256(raw).hexdigest() != path.stem:
            continue
        try:
            item = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        if (item.get('instrument_id') != key or item.get('source_id') != 'iress'
                or item.get('symbol') != key+'.JSE' or item.get('product') != 'cash_equity'
                or item.get('currency') != 'ZAR' or item.get('inconsistent_sessions') or item.get('missing_opens')):
            continue
        source = item.get('raw_hash', '').removeprefix('sha256:')
        if not re.fullmatch('[0-9a-f]{64}', source):
            continue
        try:
            if hashlib.sha256((root/'raw'/(source+'.bin')).read_bytes()).hexdigest() != source:
                continue
        except OSError:
            continue
        if selected is None or item['acquired_at'] > selected['acquired_at']:
            selected = item
    return selected


def verify_ost_benchmark(chart, folder):
    """Reproduce the benchmark from its retained raw bytes at acquisition time."""
    from application.opportunities.ost_data import parse_export
    provenance = chart['provenance']
    if (provenance['provider'] != 'OST' or provenance['origin_symbol'] != 'STX40'
            or not re.fullmatch(r'[0-9a-f]{64}', provenance['source_sha256'])):
        raise ValueError('OST STX40 benchmark required')
    candidates = list((Path(folder) / 'ost-exports').glob('ETF_STX40-' + provenance['source_sha256'] + '.*'))
    if len(candidates) != 1:
        raise ValueError('one archived benchmark source required')
    acquired = datetime.fromisoformat(provenance['acquired_at'].replace('Z', '+00:00'))
    restored = parse_export(candidates[0].read_bytes(), 'ETF_STX40', provenance['acquired_at'], acquired)
    if restored['bars'] != chart['bars'] or restored['provenance'] != provenance:
        raise ValueError('benchmark differs from archived source')
    return chart


@dataclass(frozen=True)
class ObservedHistory:
    instrument: str
    provider: str
    source_sha256: str
    acquired_at: str
    sessions: tuple
    bars: tuple
    product: str = 'EQUITY'
    currency: str = 'ZAR'
    grade: str = 'RECONSTRUCTED'
    action_basis: str = 'UNVERIFIED_NO_ACTION_ADJUSTMENTS'
    calendar_basis: str = 'OBSERVED_PROVIDER_SESSIONS_NOT_VERIFIED'
    availability_basis: str = 'ASSUMED_NEXT_UTC_DAY_NOT_HISTORICAL_RECEIPT'
    price_basis: str = 'UNVERIFIED'
    supplemental_sources: tuple = ()

    @property
    def sha256(self):
        return configuration_hash(asdict(self))

    def admit(self, start, end, as_of, *, activity_required=False):
        now = utc(as_of, 'as_of')
        if not self.sessions or start != self.sessions[0].key or end != self.sessions[-1].key:
            raise ValueError('complete observed window required')
        if len(self.sessions) != len(self.bars):
            raise ValueError('session and bar count mismatch')
        previous = None
        previous_available = None
        for session, bar in zip(self.sessions, self.bars):
            if previous is not None and session.open_at <= previous:
                raise ValueError('ordered unique observations required')
            if bar.session != session.key or bar.available_at < session.close_at or bar.available_at > now or bar.estimated:
                raise ValueError('completed observation required')
            if previous_available is not None and bar.available_at <= previous_available:
                raise ValueError('ordered availability required')
            o, h, l, c = (number(getattr(bar, field)) for field in ('open', 'high', 'low', 'close'))
            if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c):
                raise ValueError('invalid OHLC')
            if bar.activity is not None and number(bar.activity) < 0:
                raise ValueError('negative activity')
            if activity_required and bar.activity is None:
                raise ValueError('activity unavailable')
            previous = session.close_at
            previous_available = bar.available_at
        return self.bars


def from_chart(instrument, chart):
    sessions, bars = [], []
    for row in chart['bars']:
        day = datetime.fromisoformat(row['timestamp'][:10]).replace(tzinfo=timezone.utc)
        session = Session(day.date().isoformat(), day + timedelta(hours=7), day + timedelta(hours=15))
        sessions.append(session)
        bars.append(Bar(session.key, day + timedelta(days=1),
                        *(Decimal(str(row[field])) for field in ('open', 'high', 'low', 'close')),
                        Decimal(str(row['volume'])) if row.get('volume') is not None else None))
    provenance = chart['provenance']
    return ObservedHistory(instrument, provenance['provider'], provenance['source_sha256'],
                           provenance['acquired_at'], tuple(sessions), tuple(bars),
                           supplemental_sources=tuple(provenance.get('supplemental_sources', ())))
