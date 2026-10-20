# X5 observed execution feedback and round trip

20 October 2026. Software for review; no live operational integration. Shared-core
0.4.0 adds [ExecutionFeedback v1](../../packages/jse_intelligence_core/EXECUTION_FEEDBACK.md).
All committed fixtures are synthetic; broker provenance examples are not actual
broker confirmations. R12 remains the sole ACTIVE/PARTIAL milestone.

## Explicit invocation and ownership

```python
from application.execution_feedback import FeedbackJournal

outbox = FeedbackJournal(outbox_directory, producer_profiles=consumer_profiles)
receiver = FeedbackJournal(receiver_directory, producer_profiles=research_profiles)
for journal in (outbox, receiver):
    journal.register_release(manifest, package_id=exact_package_id)

receipt = outbox.append(observed_event)
batch = outbox.export_batch(after_cursor=outbox.delivery_checkpoint('research:local'))
# Caller transfers the inert JSON. The journal never opens a connection or sends.
ack = receiver.import_batch(batch)
delivery = outbox.acknowledge('research:local', batch, ack)
context = receiver.read_as_of(cutoff, purpose='decision')
outcomes = receiver.read_as_of(cutoff, purpose='outcome')
```

Each directory uses its own `execution-feedback.sqlite3` with application ID/schema
checks, safe plain paths and no-update/no-delete triggers. Do not point it at an
account database. Existing paper/account/radar stores and runtime remain unchanged.
Constructor/import/register/append/acknowledge are explicit local writes; export,
checkpoint/audit/as-of are reads. No watcher, route, scheduler, client, model or
order interface is installed. Receipt timestamps come from actual UTC invocation,
not producer claims. Tests patch the clock only in temporary journals.

Consumer profiles map producer_id to exactly `{provenances:[...],test_only:bool}`.
IDs/modes must be explicit; ≤32 producers and1–3 distinct provenance modes each.
Profiles are detached, validated and frozen in the journal; reopening with changed
permissions/classification rejects. A changed policy needs an explicit migration
or separately reviewed journal, not a quiet config downgrade.

Release registration retains the exact StrategyRelease and package SHA256. It
establishes known lineage only: no financial evidence review, strategy acceptance,
package execution, or approval to trade. The operator obtains these identities from
the retained reviewed source/package; registration itself does not resolve/validate
all strategy artifact bytes. Registration is idempotent and cannot remove a retained
test label. Different release/package pairs stay distinct; open positions are never
queried or migrated.

The effective test label is event OR registered release OR consumer profile OR
forwarded test label. Default journals reject test feedback on write/read/export;
`allow_test_feedback=True` explicitly enables isolated qualification. Reopening,
duplicate event delivery or a false producer flag cannot strip retained test status.
Adding a stricter label to a previously non-test receipt conflicts explicitly;
old observations are not silently rewritten or relabeled.

## Event storage and causal lineage

`append` accepts a closed ExecutionFeedback object/dictionary. Kind-specific
payloads keep DECISION/no-setup/unavailable, RISK rejection, unfilled/expired ORDER,
FILL, COST and EXIT denominators. Monetary values are bounded decimal strings;
unknown costs remain null. Raw account numbers, credentials, account balances and
position sizing authority are not part of this format. Source references point to
externally retained evidence bytes; hashes/provenance strings do not authenticate
their truth. Local trusted producer authority and truthful clocks remain required.

Producer ID/provenance, registered release/package, exact mapping and horizon are
checked before storage. Source observation/recording cannot be in the receiving
future; scope as-of/release creation cannot follow observation. Exact DECISION
occurrence cannot predate release creation. Unknown/date occurrence stays uncertain.
Observed facts from an unsupported profile or unknown release reject; none is
invented. Event IDs and per-producer sequence numbers are unique. Repeating the same
canonical event returns its first actual receipt; reusing an ID/sequence for changed
facts fails. One original DECISION root per producer/decision is allowed.

Nondecision events have exact parent ID/hash. Parent types are RISK→DECISION,
ORDER→RISK, FILL→ORDER, COST→FILL/EXIT, EXIT→FILL. Reference resolution requires
same producer, release/package, mapping/horizon, decision and provenance; lower
producer sequence; no future parent observation/known exact occurrence. No-setup
cannot parent execution, rejected risk cannot parent an order, cancelled/unfilled
orders cannot parent a fill. Order/fill external IDs and monetary currencies must
match. Each exit quantity cannot exceed its referenced fill. This is an observation
graph, not cumulative partial-exit reconciliation, an account ledger or new risk
approval; aggregate overfills/account truth still require operational reconciliation.

Out-of-order facts are durably stored without pretending missing references exist.
As-of resolution reports PENDING_REFERENCE or INVALID_REFERENCE and excludes those
facts from usable records. Cycles/depth>64 fail closed. `audit()` retains all facts
and original receipts. A source correction is a new event with correction_of exact
previous ID/hash, unchanged kind/parent/context, later sequence/observation/recording.
Forked corrections reject; valid later revisions supersede only their exact prior
revision in the current view. Children continue to bind the exact historical parent
they referenced. Nothing rewrites old bodies or propagates an unreviewed position
migration. Wrong revisions remain audit errors and cannot hide a valid original.

## Exchange, receipts and retry checkpoints

Batch schema is `execution-feedback-batch/1`, with stream_id (journal UUID),
after_cursor, next_cursor, items and batch_id. Each item has cursor, event, test_only.
Batch ID hashes the canonical other fields; sender local sequence is the transport
cursor, distinct from each producer's own sequence. Items must be contiguous, bounded
at100, and the complete serialized batch at256KiB. Export trims pages to fit;
individual events are at most64KiB. Duplicate keys, unknown schemas/fields, nonfinite
JSON, changed hashes, oversized/gapped pages and stream-position changes reject.

Receiver import is atomic across all event facts, cursor positions and immutable
batch acknowledgement. A failure/crash before commit cannot claim a partial receipt.
Different pages can arrive out of order; `committed_through` advances only over
contiguous stored source positions. Retrying the identical batch returns its exact
original ack, including the historical checkpoint then observed. `checkpoint(stream)`
returns the latest contiguous cursor if a retry ack is old. Semantic reference
resolution is separate: STORED is neither approved evidence nor successful execution.

The sender validates the ack against its exact local batch/event hashes and labels,
timestamps, stream and known cursor range. `acknowledge(destination_id,batch,ack)`
persists an immutable receipt and destination-specific checkpoint. Old acknowledgements
cannot decrease progress; different destinations cannot share delivery progress.
Sender progress is derived from contiguous locally verified per-event receipts,
not the receiver's claimed committed_through value; that claim alone cannot skip
an unsent position, even on an otherwise valid empty-page acknowledgement.
Neither the checkpoint nor an acknowledgement authenticates a remote identity.
Initial transfer is trusted local JSON/file exchange; network authentication/signed
manifests and automated transports remain future work. No files or messages are
sent by these methods.

## As-of availability and learning separation

`read_as_of(cutoff,purpose=...)` considers only facts whose actual local receipt,
producer recording and source observation are all <=cutoff. Thus an old occurrence
received today cannot be visible in yesterday's research context. A late correction
does not change an earlier read. Exact occurrence/parent chronology is also checked;
date-only/unknown occurrence remains disclosed and cannot qualify exact execution
timing. The explicit decision view returns DECISION payloads only and no outcome
reference-error metadata. Fill/exit/cost facts stay in the outcome view, available
only after their own receipt/observation clocks. A later outcome never changes the
closed original decision payload or X4 strategy/evaluator state.

This enforces schema/temporal separation on trusted supplied observations, not
independent source truth or a statistical held-out protocol. Research still owns
label/holdout contamination and any approved later experiment. Both projections
declare retraining=false and activation=false; neither invokes training, promotion,
source acquisition or a strategy change. Reads/audit are capped at10,000 stored
facts and fail explicitly above that window; larger archives need a reviewed
pagination/projection adapter, not silently truncated evidence.

## Explicit adapters and acceptance fixture

`inactive_decision_feedback` projects a supplied X4 result/candidate into a
PAPER_SIMULATED decision with immutable release/package/snapshot/admission/source
identity. INACTIVE intent does not become an order. `paper_fill_feedback` projects
a supplied existing PaperFill into PAPER_SIMULATED fill and hypothetical cost facts;
the caller supplies the source paper currency context. It never calls place_order,
reads an account, converts currency or guesses zero costs. Excess source decimal
precision rejects rather than rounding. Slippage is retained as the supplied total
amount; no P&L/cost arithmetic or performance claim is added.

Fixed independent fixtures contain26 synthetic observations across all three
provenances; current effective view has25 after one cost correction, with seven
decision denominators. The tests exercise outbox→receiver→ack→sender checkpoint,
out-of-order retry/restart, atomic failures, immutable corrections, late-receipt
cutoffs, X4 result parity and an isolated runtime-denial round trip. No actual
manual/broker adapter is connected, no real outcome was captured and no order was
submitted, even through the supplied-paper projection.

All numbered X software cards are now delivered for review. Real research releases,
X3/X4 acceptance/adoption, operational producer/clock qualification, P1 campaign,
P2 shakedown, U1 reports and extensions remain separate. See
[ADR0076](../adr/0076-observed-execution-feedback-round-trip.md).
