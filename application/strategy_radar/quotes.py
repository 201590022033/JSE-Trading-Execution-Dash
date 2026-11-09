"""Read-only quote candidates and availability-first field selection.

A received observation is not assumed live. Selection is per field; differing
fields can come from different providers, with the original candidates retained.
No price, spread, midpoint or quote is synthesized from bars or missing data.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
import re


class QuoteKind(str, Enum):
    LIVE = 'LIVE'
    DELAYED = 'DELAYED'
    MANUAL = 'MANUAL'
    HISTORICAL = 'HISTORICAL'
    UNKNOWN = 'UNKNOWN'
    STALE = 'STALE'


def _aware(value, name):
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f'{name} must be timezone-aware')


@dataclass(frozen=True)
class QuoteCandidate:
    instrument: str
    provider: str
    source_time: datetime | None
    received_at: datetime
    kind: QuoteKind
    unit: str
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    delay_seconds: int | None = None
    source_ref: str | None = None
    revision: str | None = None

    def __post_init__(self):
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,79}', self.instrument):
            raise ValueError('canonical instrument required')
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError('provider required')
        if not isinstance(self.kind, QuoteKind) or self.kind == QuoteKind.STALE:
            raise ValueError('kind must describe the original observation')
        if self.unit not in ('ZAR', 'ZAR_CENTS'):
            raise ValueError('unsupported quote unit')
        _aware(self.source_time, 'source_time')
        _aware(self.received_at, 'received_at')
        if self.received_at is None:
            raise ValueError('receipt time required')
        if self.source_time and self.source_time > self.received_at:
            raise ValueError('source time after receipt time')
        if self.delay_seconds is not None and (type(self.delay_seconds) is not int or self.delay_seconds < 0):
            raise ValueError('invalid delay')
        values = (self.bid, self.ask, self.last)
        if not any(v is not None for v in values):
            raise ValueError('at least one quote field required')
        if any(v is not None and (not isinstance(v, Decimal) or not v.is_finite() or v <= 0) for v in values):
            raise ValueError('quote fields must be positive finite Decimals')
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError('crossed bid/ask in one observation')


def _classification(candidate, now, max_age_seconds):
    _aware(now, 'now')
    if now is None:
        raise ValueError('now required')
    if candidate.received_at > now:
        raise ValueError('receipt time is in the future')
    source_age = (now - candidate.source_time).total_seconds() if candidate.source_time else None
    receipt_age = (now - candidate.received_at).total_seconds()
    if candidate.kind == QuoteKind.HISTORICAL:
        kind = QuoteKind.HISTORICAL
    elif candidate.kind == QuoteKind.MANUAL:
        kind = QuoteKind.STALE if source_age is not None and source_age > max_age_seconds else QuoteKind.MANUAL
    elif source_age is not None and source_age > max_age_seconds:
        kind = QuoteKind.STALE
    elif candidate.source_time is None or candidate.delay_seconds is None:
        kind = QuoteKind.UNKNOWN
    elif candidate.kind == QuoteKind.UNKNOWN:
        kind = QuoteKind.UNKNOWN
    elif candidate.kind == QuoteKind.DELAYED or candidate.delay_seconds > 0:
        kind = QuoteKind.DELAYED
    else:
        kind = QuoteKind.LIVE
    return kind, source_age, receipt_age


def select_quote(instrument, candidates, now, max_age_seconds=300):
    """Select each bid/ask/last independently while preserving conflicts.

    Returns a JSON-compatible dictionary. Candidates must all identify the same
    exact canonical instrument; providers decide their own mappings upstream. A
    missing source clock or unknown delay cannot become a LIVE/DELAYED claim.
    Historic prices remain historical regardless of age or receipt time. Manual
    observations remain explicitly manual when their age cannot be established.
    Selection preference: live, delayed, manual, unknown, stale, historical;
    then source timestamp and receipt timestamp, newest first, then provider.
    """
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,79}', instrument or ''):
        raise ValueError('canonical instrument required')
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError('max_age_seconds must be nonnegative')
    _aware(now, 'now')
    if now is None:
        raise ValueError('now required')
    priority = {QuoteKind.LIVE: 0, QuoteKind.DELAYED: 1, QuoteKind.MANUAL: 2,
                QuoteKind.UNKNOWN: 3, QuoteKind.STALE: 4, QuoteKind.HISTORICAL: 5}
    fields = {key: [] for key in ('bid', 'ask', 'last')}
    for c in candidates:
        if not isinstance(c, QuoteCandidate) or c.instrument != instrument:
            raise ValueError('candidate instrument mismatch')
        kind, source_age, receipt_age = _classification(c, now, max_age_seconds)
        for field in fields:
            value = getattr(c, field)
            if value is None:
                continue
            normalized = value / Decimal(100) if c.unit == 'ZAR_CENTS' else value
            entry = {'value': str(normalized), 'unit': 'ZAR', 'raw_value': str(value),
                     'raw_unit': c.unit, 'provider': c.provider,
                     'kind': kind.value, 'original_kind': c.kind.value,
                     'source_time': c.source_time.isoformat() if c.source_time else None,
                     'received_at': c.received_at.isoformat(), 'source_age_seconds': source_age,
                     'receipt_age_seconds': receipt_age, 'delay_seconds': c.delay_seconds,
                     'source_ref': c.source_ref, 'revision': c.revision}
            fields[field].append((priority[kind], -(c.source_time.timestamp() if c.source_time else float('-inf')),
                                  -c.received_at.timestamp(), c.provider, c.source_ref or '', c.revision or '', str(normalized), entry))
    result = {}
    for name, entries in fields.items():
        entries.sort(key=lambda x: x[:-1])
        evidence = [entry[-1] for entry in entries]
        same_clock = {}
        for item in evidence:
            if item['source_time'] is not None:
                same_clock.setdefault(datetime.fromisoformat(item['source_time']), set()).add(Decimal(item['value']))
        result[name] = {'selected': evidence[0] if evidence else None,
                        'candidates': evidence,
                        'values_differ': len({Decimal(x['value']) for x in evidence}) > 1,
                        'conflict': any(len(values) > 1 for values in same_clock.values())}
    return {'instrument': instrument, 'as_of': now.isoformat(), 'fields': result}
