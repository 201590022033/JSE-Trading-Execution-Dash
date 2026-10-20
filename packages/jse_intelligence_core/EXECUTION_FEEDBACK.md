# ExecutionFeedback v1 — additive core0.4.0

An immutable, keyword-only contract exported from `jse_intelligence_core`.
Existing X1a/X1b/X4 schemas, identities and arithmetic remain unchanged. The pure
contract has no application/database/provider dependency, receipt clock or sending
side effect. Schema-valid observations confer no authority to trade or retrain.

## Exact fields

| Fields | Meaning |
|---|---|
| schema_version | execution-feedback/1 |
| event_id, producer_id, producer_sequence | Stable source event ID, configured producer ID and positive integer sequence ≤2^53−1 |
| release_id, package_id | SHA256 canonical StrategyRelease identity and exact package identity |
| mapping, horizon, decision_id | Exact StrategyMapping, existing horizon ID, common decision/lifecycle reference |
| kind | DECISION, RISK, ORDER, FILL, COST, EXIT |
| provenance | PAPER_SIMULATED, MANUAL_REPORTED, BROKER_CONFIRMED |
| occurrence, clock_source | PublicationClock (exact/date/unknown, retaining its basis/timezone), explicit clock-source ID |
| observed_at, recorded_at | Actual source observation and producer recording instants; offsets required, normalize UTC |
| source_reference | ArtifactReference to externally retained source bytes; declaration, not authentication |
| parent | Null only for DECISION; otherwise exact prior event ID/hash |
| correction_of | Null or exact previous revision ID/hash; correction keeps the same kind/lineage |
| data_json | Bounded inert JSON string with the kind-specific closed payload below |
| test_only | Explicit boolean producer declaration; consumer/transport labels can add stricter test classification |

Direct constructors and exact-field `from_dict`/`from_json` validate. Nullable
references must be explicit. Exact occurrence<=observation<=recording; a date-only
occurrence cannot be after observation's UTC date. Unknown occurrence stays null;
no guessed midnight or substitution with receipt. Receipt is stamped separately by
each receiving application, so an old occurrence does not establish old knowledge.
External clock/source truth and authority remain the trusted producer's duty.

IDs are explicit ASCII identifiers ≤256 characters where defined by the feedback
contract; nested core mappings/references retain their existing contracts. Event
canonical JSON is capped at64KiB, and data_json at16KiB. Payload parsing reuses the
core finite/depth/node JSON limits. Duplicate keys and extra/outcome fields reject.
Payload JSON is normalized into an immutable canonical string; `data` returns a
detached parsed value. Canonical identities follow the existing core conventions.

## Closed payloads

| Kind | Fields and constraints |
|---|---|
| DECISION | status=INTENT/NO_SETUP/UNAVAILABLE, reason_code, snapshot_id, admission_id (SHA256s) |
| RISK | status=APPROVED/REDUCED/REJECTED, reason_code |
| ORDER | status=PENDING/FILLED/REJECTED/CANCELLED/EXPIRED/UNFILLED, order_id, reason_code |
| FILL | fill_id, order_id, side=BUY/SELL, quantity, price, currency |
| COST | cost_id, currency, commission, slippage, other, basis |
| EXIT | exit_id, quantity, price, currency, reason_code |

Reason codes/external IDs are bounded identifiers. Currency is an explicit
three-letter uppercase code; no conversion is inferred. Quantity/price are positive
ASCII decimal strings with at most12 integer and8 fractional digits, no exponent,
negative, NaN, infinity or float/bool substitute. Cost amounts are nonnegative
strings with the same bounds or null for unknown. Unknown is not zero. Negative
rebates and higher precision need a future version; consumers must not silently round.

Cost basis must match provenance: PAPER_SIMULATED→HYPOTHETICAL,
MANUAL_REPORTED→MANUAL_REPORTED, BROKER_CONFIRMED→BROKER_CONFIRMED. Slippage is the
declared total source amount; it may already be represented in fill price. This
contract never computes totals, P&L or Sharpe, so consumers must not double-charge.
Partial/cumulative fill reconciliation and position accounting remain outside this
observation contract; no account balance or order authorization is present.

Parent/correction resolution, supported producer/release mapping, actual receiving
time, durable duplicate handling and historical projections belong to
`application.execution_feedback`. See `docs/research/X5_EXECUTION_FEEDBACK.md`.
The fixed hand-built wire examples under `tests/fixtures/execution_feedback` are
synthetic, including broker/manual provenance examples; they are not real fills.
