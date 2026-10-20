# ADR0075: StrategyRelease and inactive frozen-policy evaluation

20 October 2026. Status: implemented software for review.

## Context

The owner authorized X4 and a GitHub push. The planning card requires exact
component/sector/vehicle compatibility, current-as-of parity and refusal of
unsupported products/timelines. No real reviewed StrategyRelease was supplied.
R12 remains the sole ACTIVE/PARTIAL milestone. X3 real-artifact acceptance and
production adoption remain pending; X4 does not bypass that research evidence.

## Decision

Add immutable StrategyRelease/StrategyMapping/StrategyComponent v1 to the
standalone core as additive version0.3.0. Preserve old schemas, identities and
legacy news scoring. Reference separate exact entry/exit/stop/timeline/volume/risk
parameter bytes and freeze code/configuration/outcome/parity/evidence identity.

Reuse `domain.policy.swing_shadow.build_policy` unchanged for the first supported
adapter: exact Swing1.2.0 policy with Swing1.1.0 frozen feature input, daily cash
shares and 3/4/5-session declared intent. Do not port a second setup/stop engine,
extend fills, fit parameters or pretend all strategies are compatible. Consumer
configuration supplies exact scope/listing/source/execution mappings and sources.

Preparation is a pure bounded single-object package operation producing an
immutable INACTIVE candidate. Every artifact is a retained hash-bound inert JSON
string. Full hand-answer parity precedes preparation; current evaluation rechecks
the candidate, then supplied as-of data/dependencies and fresh consumer admission.
Intent is a risk-review proposal with no quantity, price fill or order authority.

X2 remains a radar-specific durable inbox, X3 a radar-specific review/selection
journal. Do not overload their schemas/state labels with strategy authority.
X4 has no durable strategy registry, selected version or activation lifecycle;
the caller retains packages/receipts. Future operational integration must add its
explicit review/persistence/activation contract before using a real release.

Pure JSON limits were ported from X2 into the core, rather than importing X2's
initializer and SQLite store into this stateless boundary. This small duplication
is justified by independent package ownership and side-effect isolation; matching
parser acceptance/rejection is tested. Existing X2 code remains unchanged.

## Consequences

One bounded inactive strategy can be qualified against independent synthetic
fixtures now. A real research package, its outcome evidence and independent
engine parity remain pending. Frozen feature calculation and truthful dependency
metadata come from a trusted consumer producer; hash syntax does not prove source
truth. No raw bars or broker assumptions are inferred from these inputs.
Unsupported product/timing/component mappings fail closed. The running dashboard,
registry, strategies, providers, services, sources, accounts and orders are not
rewired. X5 feedback round-trip and P2 operational activation remain separate.
