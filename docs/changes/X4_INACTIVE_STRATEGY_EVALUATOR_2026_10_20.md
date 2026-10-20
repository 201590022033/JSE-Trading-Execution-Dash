# X4 inactive StrategyRelease evaluator — 20 October 2026

Status: SOFTWARE DELIVERED FOR REVIEW; REAL RESEARCH RELEASE ACCEPTANCE PENDING.
Owner authorized X4 and a GitHub push. R12 remains sole ACTIVE/PARTIAL.

## Delivered

Shared-core0.3.0 adds immutable StrategyRelease, StrategyComponent and
StrategyMapping v1 with closed schemas, canonical identities, exact versioned
components, sector/listing/product/source/execution mapping and referenced
code/configuration/outcome/parity/evidence. Old contract identities, v1 modules,
legacy news scoring and fixture bytes remain unchanged.

`application.strategy_releases` prepares a bounded hash-verified INACTIVE package
and evaluates an explicit current-as-of feature snapshot through the unchanged
Swing1.2.0 policy. It supports daily cash shares and3/4/5-session intent only.
Setup/stop math is reused, not reimplemented. Every component parameter version
and JSON value must match the supported declaration. Independent full-result
setup/no-setup/missing-data parity precedes preparation and is rechecked on use.

Consumer-owned exact scope/mappings/source allowlist and fresh current admission
are required. Dependencies must be causal and fresh; actual receipts cannot be
backdated to bar availability. Missing/inconsistent/stale/future inputs cannot
produce an intent. Unsupported products, timelines, strategy versions, component
versions or mappings reject. Returned intent requires risk review and has no
quantity/fill/order authority. Preparation and evaluation do not select or activate.

## Verification

- **27 new X4 tests pass**, with hand-answer full policy/intent parity and direct
  legacy comparison; closed/immutable schemas, byte tampering and resealed bad
  parameters/parity, scope/listing/product/source mapping, future/late-received
  dependencies, stale admission, missing features and test-only reuse rejection.
- **1452 full offline tests pass in113.525s** (1425 previous +27 X4). Five manual
  provider probes remain excluded by the established safe runner.
- **54 protected-artifact checks pass**; compile-only passes299 root/script files;
  focused tests compile/import the new modules.
- Isolated subprocess exercises the complete preparation/current-evaluation path
  with database/provider/model/engine imports, socket/subprocess activity, private
  environment/database reads and file writes denied.
- Offline wheel build and isolated install pass for shared-core0.3.0, retaining
  all prior fixed canonical oracles plus the new StrategyRelease identity. App
  venv lacks build tools; existing bundled tools built a temporary source copy.
  No build tool or core package was installed into the running app environment.

See [protocol](../research/X4_INACTIVE_STRATEGY_EVALUATOR.md),
[shared schema](../../packages/jse_intelligence_core/STRATEGY_RELEASE.md), and
[ADR0075](../adr/0075-inactive-strategy-release-boundary.md). The owner output
receipt records the exact local commit, preservation checks and GitHub push result.

## Limits and next work

All release/parity/current examples are synthetic, not actual financial evidence.
Feature arithmetic and truthful dependency/source metadata remain the trusted
consumer producer's responsibility; reference hashes do not independently prove
source truth. No real research strategy, validated profitability, qualified new
engine, broker mapping or actual account feasibility is claimed.

X4 is stateless and inactive; caller retains packages/receipts. X2 remains a
radar-specific durable inbox; X3 remains a separate radar review/selection journal.
No durable strategy registry, active-version selection, position migration or
production current-feed wiring was added. Real research package/evidence/parity
review and operational activation remain pending, including prior X3 adoption.

The existing policy/strategy registry, app/source settings, providers/models,
account stores, scheduled tasks and services are unchanged. No restart, manual
deployment or order was performed. Push is authorized; linked repository hosting
may independently react to it. No X5 implementation started.

**X5** (execution outcome feedback and round-trip fixture) is the sole remaining
numbered X card. P1 real campaign, P2 operational shakedown, U1 view-only reports,
research R cards and extensions remain separate. SSF/UI/rename backlog sections
are preserved. Stop after the authorized GitHub push.
