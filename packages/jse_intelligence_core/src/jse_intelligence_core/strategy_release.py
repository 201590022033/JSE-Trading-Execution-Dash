"""Immutable strategy interchange only; no strategy loader or activation."""
from dataclasses import dataclass
import re

from .contracts import (ArtifactReference, ContractError, InstrumentPermission,
                        SectorScope, _Contract, _choice, _id, _instant, _tuple, _version)

COMPONENT_ROLES = ('entry', 'exit', 'stop', 'timeline', 'volume', 'risk')


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyMapping(_Contract):
    research_instrument_id: str
    listing_id: str
    product_type: str
    execution_instrument_id: str
    source_symbol: str
    mapping_state: str

    def __post_init__(self):
        for name in ('research_instrument_id', 'listing_id', 'execution_instrument_id', 'source_symbol'):
            _id(getattr(self, name), name)
        InstrumentPermission(instrument_id=self.research_instrument_id, product_type=self.product_type)
        _choice(self.mapping_state, ('reviewed_exact', 'unresolved'), 'mapping_state')


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyComponent(_Contract):
    role: str
    component_id: str
    component_version: str
    parameters: ArtifactReference

    _nested = {'parameters': ArtifactReference}

    def __post_init__(self):
        _choice(self.role, COMPONENT_ROLES, 'role')
        _id(self.component_id, 'component_id')
        _id(self.component_version, 'component_version')
        if type(self.parameters) is not ArtifactReference:
            raise ContractError('component parameter artifact required')


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyRelease(_Contract):
    strategy_id: str
    strategy_version: str
    scope: SectorScope
    mappings: tuple[StrategyMapping, ...]
    components: tuple[StrategyComponent, ...]
    horizon: str
    feature_schema_version: str
    evaluator_version: str
    data_frequency: str
    missing_data_policy: str
    created_at: str
    supersedes: ArtifactReference | None
    code_reference: ArtifactReference
    configuration_reference: ArtifactReference
    outcome_reference: ArtifactReference
    parity_reference: ArtifactReference
    evidence_references: tuple[ArtifactReference, ...]
    test_only: bool
    schema_version: str = 'strategy-release/1'

    _nested = {'scope': SectorScope, 'code_reference': ArtifactReference,
               'configuration_reference': ArtifactReference, 'outcome_reference': ArtifactReference,
               'parity_reference': ArtifactReference}
    _arrays = {'mappings': StrategyMapping, 'components': StrategyComponent,
               'evidence_references': ArtifactReference}

    @classmethod
    def from_dict(cls, value, *, expected_id=None):
        if type(value) is dict and value.get('supersedes') is not None:
            value = dict(value)
            value['supersedes'] = ArtifactReference.from_dict(value['supersedes'])
        return super(StrategyRelease, cls).from_dict(value, expected_id=expected_id)

    def __post_init__(self):
        _version(self.schema_version, 'strategy-release/1')
        _id(self.strategy_id, 'strategy_id')
        if type(self.strategy_version) is not str or not re.fullmatch(r'\d+\.\d+\.\d+', self.strategy_version):
            raise ContractError('semantic strategy version required')
        for name in ('feature_schema_version', 'evaluator_version', 'data_frequency', 'missing_data_policy'):
            _id(getattr(self, name), name)
        from .contracts import HORIZONS
        _choice(self.horizon, HORIZONS, 'horizon')
        if type(self.scope) is not SectorScope or type(self.test_only) is not bool:
            raise ContractError('explicit scope and boolean test provenance required')
        _tuple(self.mappings, StrategyMapping, 'mappings')
        if len({m.research_instrument_id for m in self.mappings}) != len(self.mappings):
            raise ContractError('one exact mapping per research instrument required')
        if len({m.execution_instrument_id for m in self.mappings}) != len(self.mappings):
            raise ContractError('ambiguous execution mapping')
        if len({m.source_symbol for m in self.mappings}) != len(self.mappings):
            raise ContractError('ambiguous source mapping')
        if any(not self.scope.permits(m.research_instrument_id, m.product_type) for m in self.mappings):
            raise ContractError('mapping outside permitted scope')
        _tuple(self.components, StrategyComponent, 'components')
        if len(self.components) != len(COMPONENT_ROLES) or {c.role for c in self.components} != set(COMPONENT_ROLES):
            raise ContractError('each component role required exactly once')
        _tuple(self.evidence_references, ArtifactReference, 'evidence_references')
        for name in ('code_reference', 'configuration_reference', 'outcome_reference', 'parity_reference'):
            if type(getattr(self, name)) is not ArtifactReference:
                raise ContractError('explicit artifact references required')
        if self.supersedes is not None and type(self.supersedes) is not ArtifactReference:
            raise ContractError('supersedes must reference an exact prior release')
        refs = (*self.evidence_references, self.code_reference, self.configuration_reference,
                self.outcome_reference, self.parity_reference, *(c.parameters for c in self.components))
        if len({r.reference_id for r in refs}) != len(refs):
            raise ContractError('distinct artifact reference identities required')
        object.__setattr__(self, 'created_at', _instant(self.created_at))
