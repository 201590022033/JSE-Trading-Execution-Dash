# X4 inactive strategy evaluator

20 October 2026. Software for review; all committed examples are synthetic.
No real research strategy has been accepted or activated. The owner authorized
implementation and a GitHub push, not runtime activation or new broker capability.

## Boundary and invocation

Shared core0.3.0 adds immutable [StrategyRelease v1](../../packages/jse_intelligence_core/STRATEGY_RELEASE.md).
Existing v1 contracts/scoring remain unchanged. The execution adapter is explicit
and stateless; import does not start a worker, open an account database or register
a strategy in the running dashboard. It calls the existing Swing policy unchanged.

```python
from application.strategy_releases import StrategyEvaluator

evaluator = StrategyEvaluator(
    scope=consumer_reviewed_scope,
    mappings=consumer_reviewed_mappings,
    source_ids=consumer_allowed_sources)
capabilities = evaluator.capabilities()
candidate = evaluator.prepare(package_bytes)  # INACTIVE, no approval/activation
result = evaluator.evaluate(candidate, current_snapshot, current_admission,
                            as_of=explicit_decision_clock)
```

Scope, mappings and source_ids are independently supplied consumer configuration,
never copied from an unreviewed package. Scope equality includes dated universe
and exposure references; manifest mappings are an explicit subset of the reviewed
mapping list. Mapping binds research ID, listing identity, product, execution ID,
source symbol and reviewed_exact status. The consumer must establish truthful
identities; the adapter cannot certify a broker mapping from a string.

`allow_test_releases=True` is required for synthetic packages, including evaluating
a candidate prepared by a different test-enabled evaluator. There is no installed
production profile/catalog, accepted strategy, or active strategy selection.
Consumer configuration can independently set `test_only=True`; the effective
label is consumer-test OR manifest-test and is retained on the prepared candidate.
Changing a producer's flag to false cannot remove a consumer-owned test label.

## Package, compatibility and parity

Closed `inactive-strategy-package/1` fields: schema_version, manifest,
expected_manifest_id, artifacts. Manifest is StrategyRelease v1. Artifacts are
`{reference_id,raw_json}` objects: raw_json is the exact UTF-8 string whose SHA256
the corresponding reference requires, including any newline. Each string wraps
`{schema_version:'strategy-inert-data/1',data:...}`. No Python/pickle/joblib/model
loader is supported. Missing, duplicate, unreferenced or changed artifacts reject.
The package resolves component/code/config/outcome/parity/evidence references and
universe/exposure/context references. Supersedes references external prior release
identity for later lineage resolution; it neither resolves nor activates it here.

Total serialized package is bounded at256KiB/depth16/10,000 nodes; ≤64 artifacts.
Manifest IDs hash shared canonical JSON; package IDs hash the complete canonical
package. Both remain stable across reordered JSON object keys; artifact strings
retain their byte identity. Prepared candidate fields are immutable and rechecked
on every evaluation. Caller owns persistence; no durable import acknowledgement or
strategy lifecycle is claimed by this pure boundary. X2's radar inbox is unchanged.

Only strategy `jse_swing_3_5d` version1.2.0, evaluator
`inactive-swing-evaluator/1`, feature schema `frozen-swing-policy-input/1`, frequency
1d, horizons sessions_3/4/5, missing policy BLOCK_NEW_INTENT, reviewed_exact cash
shares are supported. Feature projection pins Swing1.1.0/`swing-ohlcv-wilder-v1`.
ETF/SSF/CFD/metal/FX, shorting, opening-minute rules, mutable membership or arbitrary
versions require separately reviewed adapters; no fallback/simplification occurs.

Exactly six roles are required: entry, exit, stop, timeline, volume, risk. Every
component ID is `swing-<role>` at `swing-daily-shadow-policy-v1`; inert parameters
must equal `capabilities()['component_parameters']` exactly, including JSON types.
Code evidence must match the installed policy version and complete frozen rules.
Configuration must be `{horizon:<manifest horizon>,currency:'ZAR',mode:'INACTIVE'}`.
Outcome/evidence bytes are bound and inspectable, not performance acceptance.

Parity artifact is closed `{schema_version:'strategy-parity/1',cases:[...]}`.
Three to32 distinct cases include setup, no_setup and missing. Each has case_id,
features, decision_at, expected. The complete normalized policy/intent, feature
hash, no-setup/block reasons and authority flags must match. The committed fixed
oracles were written without calling either evaluator; tests also compare the
unchanged legacy function directly. A future research producer must supply its
own frozen independent parity and evidence; these synthetic cases do not qualify
Backtrader, VectorBT, account sizing, broker fills or strategy profitability.

## Current snapshot and trusted feature projection

Closed `strategy-current/1`: schema_version, scope_id, mapping, horizon, features,
dependencies. Scope/mapping/horizon must match the prepared release. Release
creation and scope as-of dates cannot be in the future of the explicit decision.

Feature fields are exactly version, strategy_profile_id, strategy_profile_version,
state, evaluated_at, session, available_at, last_close, source_symbol, values,
missing, conditions. This is an explicit projection from a trusted frozen Swing
feature producer, not raw bars and not executable research code. Values contain
only atr14_wilder and prior_low10. Conditions contain only ema_uptrend,
rsi_50_70, volume_above_prior20, outperforming_benchmark20, breakout20,
ema20_reclaim, core_setup. Conditions are booleans or null; missing data cannot
be converted to ready. Unknown fields (including forward returns/labels) reject.
The installed policy computes setup/stop; upstream still owns feature arithmetic
and truthful conditions. This adapter does not independently re-derive indicators
or establish bar-source truth from the supplied packet.

Exactly two dependencies, instrument and benchmark, each contain role, source_id,
content_hash, available_at, acquired_at, received_at. Sources must be allowlisted;
hashes must be valid SHA256 references. Actual dependency bytes are upstream;
their declarations are provenance assertions, not authenticated attestations.
Each satisfies available<=acquired<=received<=decision; receipt must precede
feature evaluation, and dependency availability cannot follow the declared
feature/bar availability. Dependencies and feature availability must be at most
four calendar days old (the existing daily freshness limit, not exchange-calendar
qualification). Session dates cannot follow feature availability; feature
availability<=feature evaluation<=decision. Output input_available_at is the
maximum of feature availability and actual dependency receipts, preserving late
acquisition rather than backdating it to the source bar.

Trusted current admission has exactly enabled, admissible, observed_at, mapping,
scope_id. Both flags must be boolean true, mapping/scope exact, observation age
0–60seconds. The caller obtains this from execution-owned admission/source/risk
state; packages cannot supply it. This flag is not a substitute for account risk
assessment. No capital, costs, live source or portfolio is consulted by X4.

Valid evaluation returns complete package/manifest/strategy/component/mapping,
snapshot/admission identities, as_of, input availability, test-only and INACTIVE
lineage with INTENT, NO_SETUP or UNAVAILABLE. Malformed/mismatched packages or
out-of-scope snapshots raise; current admission/data failures return UNAVAILABLE.
Every result has execution_enabled=false, live_execution=false, order_intent=null.
INTENT contains LONG, source session/close, first-later-observable-close entry,
frozen structural/ATR stop,2R target multiple,3/4/5 horizon and7-calendar-day expiry,
with requires_risk_review=true. No quantity, fill, position migration or actual
order is produced. No old positions are read or modified by a new package.

## Remaining work

Research must deliver a real compatible StrategyRelease, outcome/cost/coverage
evidence and independent engine parity for owner review. Operational selection,
durable strategy lifecycle, paper/manual activation and shakedown require their
explicit authority/data contracts. X5 is the remaining numbered X card: idempotent
execution outcome feedback and round-trip fixture. P1/P2, U1 and extensions remain
separate. See [ADR0075](../adr/0075-inactive-strategy-release-boundary.md).
