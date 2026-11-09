"""Strategy Radar M1 boundary contracts; no data acquisition or execution.

A field carries its own provenance so partial, mixed-source bars stay usable.
Times are source and receipt clocks, not an inferred historical availability.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Availability(str, Enum):
    MISSING = 'MISSING'
    LIVE = 'LIVE'
    DELAYED = 'DELAYED'
    MANUAL = 'MANUAL'
    STALE = 'STALE'
    HISTORICAL = 'HISTORICAL'


class RuleState(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNKNOWN = 'UNKNOWN'


def _clock(value):
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None):
        raise ValueError('timestamps must be timezone-aware')


@dataclass(frozen=True)
class FieldObservation:
    value: Decimal | None
    unit: str | None
    availability: Availability
    source: str | None = None
    source_time: datetime | None = None
    received_at: datetime | None = None
    delay_seconds: int | None = None

    def __post_init__(self):
        if not isinstance(self.availability, Availability):
            raise ValueError('explicit availability required')
        _clock(self.source_time)
        _clock(self.received_at)
        if self.delay_seconds is not None and (type(self.delay_seconds) is not int or self.delay_seconds < 0):
            raise ValueError('delay must be a nonnegative number of seconds')
        if self.availability == Availability.MISSING:
            if any(x is not None for x in (self.value, self.unit, self.source, self.source_time, self.received_at, self.delay_seconds)):
                raise ValueError('missing observations cannot claim a value or provenance')
        else:
            if not isinstance(self.value, Decimal) or not self.value.is_finite() or not self.unit or not self.source or self.received_at is None:
                raise ValueError('observed fields require decimal value, unit, source and receipt time')


@dataclass(frozen=True)
class StrategyVersion:
    strategy_id: str
    version: str
    timeframe: str


@dataclass(frozen=True)
class Watch:
    instrument: str
    strategy: StrategyVersion
    pinned: bool
    origin: str
    created_at: datetime
    sector: str | None = None
    benchmark: str | None = None

    def __post_init__(self):
        _clock(self.created_at)
        if self.created_at is None:
            raise ValueError('watch creation time required')


@dataclass(frozen=True)
class Quote:
    instrument: str
    bid: FieldObservation
    ask: FieldObservation
    last: FieldObservation


@dataclass(frozen=True)
class Bar:
    instrument: str
    interval: str
    start: datetime
    end: datetime
    open: FieldObservation
    high: FieldObservation
    low: FieldObservation
    close: FieldObservation
    volume: FieldObservation

    def __post_init__(self):
        _clock(self.start)
        _clock(self.end)
        if self.start is None or self.end is None or self.start >= self.end:
            raise ValueError('bar requires an ordered interval')


@dataclass(frozen=True)
class RuleTrace:
    rule_id: str
    state: RuleState
    mandatory: bool
    evidence: tuple[FieldObservation, ...] = ()
    explanation: str | None = None

    def __post_init__(self):
        if not isinstance(self.state, RuleState):
            raise ValueError('explicit rule state required')


@dataclass(frozen=True)
class ProductValue:
    value: Decimal | None
    unit: str | None
    mapping_verified: bool = False
    provenance: str | None = None

    def __post_init__(self):
        if self.value is not None and (not isinstance(self.value, Decimal) or not self.value.is_finite() or not self.unit):
            raise ValueError('product value requires finite decimal and unit')
        if self.mapping_verified and (self.value is None or not self.unit or not self.provenance):
            raise ValueError('verified mapping requires value, unit and evidence')


@dataclass(frozen=True)
class TradePlan:
    instrument: str
    product: str
    strategy: StrategyVersion
    entry: ProductValue
    quantity: ProductValue
    stop_trigger: ProductValue
    stop_limit: ProductValue
    target: ProductValue
    costs: tuple[ProductValue, ...] = ()
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Alert:
    alert_id: str
    instrument: str
    strategy: StrategyVersion
    transition: str
    occurred_at: datetime
    trace: tuple[RuleTrace, ...]

    def __post_init__(self):
        _clock(self.occurred_at)
        if self.occurred_at is None:
            raise ValueError('alert time required')
