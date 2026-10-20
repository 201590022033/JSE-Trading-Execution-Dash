# X5 observed execution feedback — 20 October 2026

Status: SOFTWARE DELIVERED FOR REVIEW; OPERATIONAL CAPTURE/ACCEPTANCE PENDING.
Owner requested X5. R12 remains the sole ACTIVE/PARTIAL roadmap milestone.

## Delivered

Shared-core0.4.0 adds immutable ExecutionFeedback v1 with exact release/package,
instrument/strategy lineage, kind-specific closed payloads, distinct paper/manual/
broker provenance, source clock precision, observation/recording clocks and exact
source/parent/correction references. Earlier schemas/identities and scoring remain
unchanged. Costs use bounded decimal strings and preserve unknown values as null.

`application.execution_feedback` adds an explicit dedicated append-only SQLite
outbox/receiver with frozen consumer producer profiles, known release registration,
idempotent actual receipts, unique producer sequences/decision roots, pending/invalid
reference states and appended corrections. Bounded hashed batches import atomically;
contiguous cursor checkpoints tolerate out-of-order pages. Receiver acknowledgements
return to durable destination-specific sender delivery checkpoints without sending
messages, invoking a worker or opening a network connection.

As-of views require observation, recording and actual local receipt before cutoff.
A correction cannot rewrite a prior view. Decision context contains DECISION facts
only; fill/exit/cost data remains in the explicit outcome view. Neither projection
trains, promotes, activates or changes a strategy. Effective test classification
cannot be removed by producer flags, retries, forwarded receipts or reopening.

Explicit adapters project supplied X4 inactive evaluations and existing PaperFill
records. They preserve INACTIVE/PAPER_SIMULATED status and hypothetical cost basis,
with explicit supplied paper currency. No order submission or account lookup occurs.

## Verification

- **32 focused X5 tests pass**: independent fixed identities, immutable/closed
  contracts, chronology/unknown clocks, exact decimal/cost provenance, duplicate/
  sequence/root/fork collisions, atomic rollback/crash, concurrent retries, pending
  parents, invalid lineage, late corrections, sender ack/checkpoint validation,
  test-label retention, X4/source-paper projections and no future receipt leakage.
- **1484 full offline tests pass in133.644s** (1452 prior +32 X5); five manual
  provider probes remain excluded by the established safe runner.
- **54 protected-artifact checks pass**; compile-only passes300 root/script files;
  new modules compile/import through focused tests.
- Core0.4.0 wheel built offline and installed only in a task-specific isolated
  target. Installed code matches final source; all old fixed identities and26
  new wire identities pass. Existing bundled build tools operate on a source copy;
  no dependency/core installation is made into the running app environment.
- Independent fixture:26 synthetic observations across paper/manual/broker modes,
  seven decision denominators,25 effective facts after one cost correction. Full
  outbox→receiver→ack→sender checkpoint round trip retains identities/provenance;
  earlier reads remain unchanged after later correction receipt.
- Isolated round trip denies model/provider/broker/runtime startup imports,
  network/subprocess calls, private environment/account-database access and writes
  outside temporary feedback storage. Only supplied observations are exercised.

See [wire/invocation protocol](../research/X5_EXECUTION_FEEDBACK.md),
[shared contract](../../packages/jse_intelligence_core/EXECUTION_FEEDBACK.md),
[ADR0076](../adr/0076-observed-execution-feedback-round-trip.md). The owner output
receipt records exact local commit and preservation verification.

## Limits and remaining acceptance

All examples, including broker confirmations, are synthetic. Producer profiles,
source references and clock declarations are trusted local assertions, not signed
authentication or independently verified broker/account facts. No actual source
collector, broker read adapter, real manual fill or runtime event hook is installed.
Release registration establishes lineage only, not strategy approval or activation.
No position accounting, cumulative fill/exit reconciliation, currency conversion,
P&L/Sharpe calculation, feedback-driven learning or automatic strategy change is
claimed. Reads explicitly cap at10,000 facts; larger archives need a reviewed
pagination/projection extension. Unknown references remain visible blockers.

Existing runtime/policy/strategy registries, X2/X3/X4 implementation, source pause,
providers/models, account/paper stores, services, tasks and defaults are unchanged.
No orders, account actions, service restart, deployment or source/model calls occur.
SSF/UI/rename backlog sections remain preserved. Stop for owner review.

All numbered **X1a/X1b/X2/X3/X4/X5 software slices** are delivered for review.
Real X3/X4 research-release evidence/acceptance/adoption, research R/P1, P2
operational shakedown, U1 reporting and extensions remain separate and incomplete.
This is not completion of R12, the two-app operational system, or a performance
claim. No next card is started by this checkpoint.
