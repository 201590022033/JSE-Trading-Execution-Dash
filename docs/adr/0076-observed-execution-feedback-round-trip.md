# ADR0076: observed execution feedback with an append-only round trip

20 October 2026. Status: implemented software for review.

## Context

The owner authorized X5. The planning card requires denominator-complete feedback,
idempotent exchange, distinct paper/manual/broker provenance, appended corrections
and no future-outcome leakage. Existing paper/account stores model application
execution, while X2 and X3 model radar transport/adoption. None is an appropriate
authority to turn supplied feedback into new orders, training or active strategies.
R12 remains the sole ACTIVE/PARTIAL roadmap milestone. Real X3/X4 releases and
operational adoption remain pending.

## Decision

Add immutable ExecutionFeedback v1 to shared-core0.4.0, reusing v1 clocks, exact
mapping/reference/identity contracts and bounded inert JSON. Add an explicitly
invoked `application.execution_feedback` journal usable as either local outbox or
research-side receiver, with a dedicated SQLite file/application ID/schema.
It is separate from account/paper/radar storage and never imported by app startup.

Reuse X2 safe path validation and explicit full-sync transactional SQLite patterns.
A separate schema is justified because feedback needs pending causal references,
per-producer uniqueness, correction lineage, cursor-position receipts and sender
delivery checkpoints; radar import/selection must not gain execution authority.
Producer profiles are consumer-owned and frozen per journal. Releases are explicitly
registered exact lineage, not approved/activated strategies. Test provenance is the
OR of producer event, consumer profile, registered release and forwarded receipt;
retries/reopen cannot remove it.

Every observation has an immutable identity and actual local receipt. Duplicate
events/sequence/root/correction conflicts do not overwrite facts. Unresolved or
invalid references remain visible audit evidence, not successful execution. As-of
views admit only observed, recorded and locally received facts, resolve exact
parent/revision hashes and hide a predecessor only when a valid correction is
available. Decision context includes DECISION payloads only; fills, exits and costs
stay in the explicit outcome view. Neither view invokes learning or activation.

Bounded hashed batches preserve source positions; atomic receiver acknowledgements
and contiguous checkpoints tolerate retries/out-of-order pages. Sender acknowledgement
validation persists destination-specific delivery checkpoints without sending data.
Append-only triggers cover all facts/receipts/profiles. This is local audit storage,
not cryptographic tamper protection or authentication against its file owner.

## Consequences

X4 inactive decisions and supplied existing PaperFill records have explicit pure
projections. Paper source stays PAPER_SIMULATED, with hypothetical cost basis and
explicit currency context. Generic manual/broker observations require a trusted
configured producer and source evidence; no actual broker/feed adapter is added.
All qualification examples, including broker examples, are synthetic.

The round trip can be reviewed now without orders, account reads or a research app
running. Real operational capture, approved releases, source/clock qualifications,
accounting/reconciliation and P2 shakedown remain separate. X5 does not train,
promote, deploy, activate, change strategies or start a new numbered X card.
