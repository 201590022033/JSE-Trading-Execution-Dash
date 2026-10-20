# StrategyRelease v1 — additive package 0.3.0

X4 adds three frozen, keyword-only contracts exported from `jse_intelligence_core`.
They use the same exact-field JSON, immutable tuples, canonical JSON and SHA256
identity conventions as the X1a contracts. No runtime/application imports, files,
database connections, providers or activation occur in the contract package.

| Contract | Exact fields |
|---|---|
| StrategyMapping | research_instrument_id, listing_id, product_type, execution_instrument_id, source_symbol, mapping_state |
| StrategyComponent | role, component_id, component_version, parameters (ArtifactReference) |
| StrategyRelease | schema_version, strategy_id, strategy_version, scope, mappings, components, horizon, feature_schema_version, evaluator_version, data_frequency, missing_data_policy, created_at, supersedes, code_reference, configuration_reference, outcome_reference, parity_reference, evidence_references, test_only |

`mapping_state` is reviewed_exact or unresolved, a declaration rather than proof
of listing/broker identity. Product types use InstrumentPermission's existing
categories. There is exactly one mapping per research instrument, execution
instrument and source symbol. Each mapping must be permitted by the SectorScope;
context-only instruments cannot be substituted. Listing identity is explicit.
Consumers must compare these mappings with independent reviewed configuration.

There is exactly one component for each role: entry, exit, stop, timeline, volume,
risk. Each references exact versioned parameter bytes; contracts never execute
them. The manifest uses `schema_version='strategy-release/1'`, semantic
strategy_version, an existing horizon ID, explicit capability identifiers, an
offset-aware created_at and boolean test_only. Its scope freezes dated membership
and exposure references. New versions cannot widen scope implicitly.

Code/configuration/outcome/parity are ArtifactReferences; evidence_references is
a nonempty immutable tuple. All these and component parameter reference IDs are
distinct. `supersedes` is null or an exact ArtifactReference to an earlier release;
it records lineage, never replaces it, migrates positions or selects a version.
Resolution of earlier releases and research evidence review remain consumer duties.

`StrategyRelease.from_dict(value, expected_id=trusted_id)` and `from_json(...)`
validate exact fields and canonical identity. JSON field order is irrelevant;
array order is retained. `to_dict()` returns a detached value. Direct constructor
validation is the same as deserialization. Structural validity does not establish
performance evidence, capability support, approval or permission to trade.

The execution-side `application.strategy_releases` adapter supports only a strict
subset of these descriptions: the unchanged Swing1.2.0 policy, cash shares,
daily frozen feature input, 3/4/5 observed-session horizon and inactive intent.
SSF/CFD, arbitrary code, opening-minute timing and unreviewed mappings reject.
The schema can describe an unsupported proposal without conferring capability.

`json_boundary` contains pure bounded JSON helpers ported from X2 (256KiB,
depth16, 10,000 nodes, finite numbers, duplicate keys rejected). This avoids the
X2 package initializer's SQLite import. Compatibility tests compare both parsers;
the X2 parser/store and existing v1 core modules are unchanged.

Fixed synthetic examples and hand-answer parity are in
`tests/fixtures/strategy_release`; execution invocation/limits are documented in
`docs/research/X4_INACTIVE_STRATEGY_EVALUATOR.md`. These are software fixtures,
not a reviewed research strategy or a fitted model.
