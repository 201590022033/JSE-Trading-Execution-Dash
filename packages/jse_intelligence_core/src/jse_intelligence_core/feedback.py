"""Immutable observed execution feedback; observations confer no authority."""
from dataclasses import dataclass
from decimal import Decimal
import re

from .contracts import (ArtifactReference, ContractError, PublicationClock, _Contract,
                        _choice, _hash, _id, _instant, _version)
from .strategy_release import StrategyMapping
from .json_boundary import canonical, exact, parse_json

PROVENANCES = ('PAPER_SIMULATED', 'MANUAL_REPORTED', 'BROKER_CONFIRMED')
KINDS = ('DECISION', 'RISK', 'ORDER', 'FILL', 'COST', 'EXIT')


def identifier(value):
    _id(value, 'identifier')
    if len(value) > 256:
        raise ContractError('identifier too long')


def amount(value, *, positive=False):
    if type(value) is not str or not re.fullmatch(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?', value):
        raise ContractError('bounded nonnegative decimal string required')
    if positive and Decimal(value) <= 0:
        raise ContractError('positive amount required')


def validate_data(kind, data):
    keys = {
        'DECISION': ('status', 'reason_code', 'snapshot_id', 'admission_id'),
        'RISK': ('status', 'reason_code'),
        'ORDER': ('status', 'order_id', 'reason_code'),
        'FILL': ('fill_id', 'order_id', 'side', 'quantity', 'price', 'currency'),
        'COST': ('cost_id', 'currency', 'commission', 'slippage', 'other', 'basis'),
        'EXIT': ('exit_id', 'quantity', 'price', 'currency', 'reason_code'),
    }
    exact(data, keys[kind])
    statuses = {'DECISION': ('INTENT', 'NO_SETUP', 'UNAVAILABLE'),
                'RISK': ('APPROVED', 'REDUCED', 'REJECTED'),
                'ORDER': ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED', 'EXPIRED', 'UNFILLED')}
    if kind in statuses:
        _choice(data['status'], statuses[kind], 'status')
    for name in ('reason_code', 'order_id', 'fill_id', 'cost_id', 'exit_id'):
        if name in data:
            identifier(data[name])
    if kind == 'DECISION':
        _hash(data['snapshot_id']); _hash(data['admission_id'])
    if kind == 'FILL':
        _choice(data['side'], ('BUY', 'SELL'), 'side')
    if kind in ('FILL', 'EXIT'):
        amount(data['quantity'], positive=True); amount(data['price'], positive=True)
    if 'currency' in data and (type(data['currency']) is not str or not re.fullmatch('[A-Z]{3}', data['currency'])):
        raise ContractError('explicit currency required')
    if kind == 'COST':
        _choice(data['basis'], ('HYPOTHETICAL', 'MANUAL_REPORTED', 'BROKER_CONFIRMED'), 'cost basis')
        for name in ('commission', 'slippage', 'other'):
            if data[name] is not None:
                amount(data[name])


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFeedback(_Contract):
    event_id: str
    producer_id: str
    producer_sequence: int
    release_id: str
    package_id: str
    mapping: StrategyMapping
    horizon: str
    decision_id: str
    kind: str
    provenance: str
    occurrence: PublicationClock
    clock_source: str
    observed_at: str
    recorded_at: str
    source_reference: ArtifactReference
    parent: ArtifactReference | None
    correction_of: ArtifactReference | None
    data_json: str
    test_only: bool
    schema_version: str = 'execution-feedback/1'

    _nested = {'mapping': StrategyMapping, 'occurrence': PublicationClock, 'source_reference': ArtifactReference}

    @classmethod
    def from_dict(cls, value, *, expected_id=None):
        if type(value) is dict:
            value = dict(value)
            for field in ('parent', 'correction_of'):
                if value.get(field) is not None:
                    value[field] = ArtifactReference.from_dict(value[field])
        return super(ExecutionFeedback, cls).from_dict(value, expected_id=expected_id)

    def __post_init__(self):
        _version(self.schema_version, 'execution-feedback/1')
        for field in ('event_id', 'producer_id', 'decision_id', 'clock_source'):
            identifier(getattr(self, field))
        if type(self.producer_sequence) is not int or not 1 <= self.producer_sequence <= 2**53-1:
            raise ContractError('positive bounded producer sequence required')
        for value in (self.release_id, self.package_id):
            _hash(value)
        if type(self.mapping) is not StrategyMapping or self.mapping.mapping_state != 'reviewed_exact':
            raise ContractError('exact reviewed mapping required')
        from .contracts import HORIZONS
        _choice(self.horizon, HORIZONS, 'horizon')
        _choice(self.kind, KINDS, 'kind'); _choice(self.provenance, PROVENANCES, 'provenance')
        if type(self.occurrence) is not PublicationClock or type(self.source_reference) is not ArtifactReference:
            raise ContractError('explicit occurrence and source provenance required')
        for field in ('parent', 'correction_of'):
            ref = getattr(self, field)
            if ref is not None and (type(ref) is not ArtifactReference or ref.reference_id == self.event_id):
                raise ContractError('distinct referenced event required')
        if (self.kind == 'DECISION') != (self.parent is None):
            raise ContractError('only decisions are lifecycle roots')
        for field in ('observed_at', 'recorded_at'):
            object.__setattr__(self, field, _instant(getattr(self, field)))
        from datetime import datetime
        observed = datetime.fromisoformat(self.observed_at)
        if observed > datetime.fromisoformat(self.recorded_at):
            raise ContractError('observation must precede recording')
        if self.occurrence.precision == 'exact' and datetime.fromisoformat(self.occurrence.value) > observed:
            raise ContractError('occurrence must precede observation')
        if self.occurrence.precision == 'date' and self.occurrence.value > observed.date().isoformat():
            raise ContractError('occurrence date is in the future')
        if type(self.test_only) is not bool or type(self.data_json) is not str or len(self.data_json.encode()) > 16384:
            raise ContractError('bounded immutable feedback data and boolean test flag required')
        data = parse_json(self.data_json.encode())
        validate_data(self.kind, data)
        if self.kind == 'COST' and data['basis'] != {'PAPER_SIMULATED': 'HYPOTHETICAL',
                'MANUAL_REPORTED': 'MANUAL_REPORTED', 'BROKER_CONFIRMED': 'BROKER_CONFIRMED'}[self.provenance]:
            raise ContractError('cost provenance cannot change execution provenance')
        object.__setattr__(self, 'data_json', canonical(data))
        if len(self.canonical_json().encode()) > 64*1024:
            raise ContractError('feedback event exceeds 64KiB transport limit')

    @property
    def data(self):
        return parse_json(self.data_json.encode())
