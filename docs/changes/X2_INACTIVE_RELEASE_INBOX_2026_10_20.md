# X2 checkpoint — bounded inactive release importer

20 October 2026. DELIVERED_FOR_OWNER_REVIEW. Owner assigned the prepared
X2_IMPLEMENTATION_HANDOFF.md. R12 remains the sole ACTIVE/PARTIAL milestone.
X3 and all other subsequent implementation remain unstarted.

## Source and deliverable

Canonical source: `C:/Users/Deon/Documents/GitHub/JSE-Trading-Execution-Dash`,
branch `master`, initial HEAD `528b46a20b7b0ed4cfff36bb4ce2140341d0af60` and clean
working tree. The task output receipt records the resulting local commit/final
state. No push, deployment, service restart or runtime installation.

Added `application.release_inbox` and explicit one-package command
`scripts/import_radar_release.py`. Versioned transport/completion/profile/ack
schemas stay outside unchanged shared-core 0.2.0/v1 contracts. Producer completion
semantics were specified before implementation. The importer validates bounded
JSON snapshots, actual raw-byte/canonical hashes, consumer-owned dated support
profiles and referenced scope/evidence/correction relationships. Unsupported
formats/profiles/versions, scope/product/context misuse, path/link escapes,
incomplete/altered objects and inconsistent evidence reject or remain pending.

The explicit separate local SQLite store atomically retains complete bytes,
immutable INACTIVE metadata/support snapshot and acknowledgement. Logical
release/version reuse conflicts; same package repeats idempotently. Transactions
serialize concurrent attempts and recover from process interruption without
partial packages or successful acknowledgements. No active-release API exists.
There is no app startup import, watcher, route, model/scorer execution or order
path. Synthetic support profiles require explicit opt-in and remain test_only.

See [protocol/service/command](../research/X2_INACTIVE_RELEASE_INBOX.md) and
[ADR0073](../adr/0073-inactive-radar-package-inbox.md) for semantics and reuse.

## Exact verification

- **25 new tests passed in 4.748s** in the final isolated new-test run. Independent
  synthetic fixture specifies 11 source files, expected package/manifest identity,
  retained raw hashes and acknowledgement outcomes. Tests check exact ack fields,
  real invocation-time bounds, durable reopen/repeat, missing marker/bytes,
  tampering/duplicate keys/versions, supported dated scope/horizon/role/model,
  context/product rejection, evidence/correction clocks/links, JSON/file/total
  limits, and inert Backtrader/VectorBT provenance.
- Hardlink and real Windows directory-junction escape tests passed, with no
  skipped link checks. Immutable SQL rows, wrong database identity, changed
  completion marker, conflicting version reuse and original bytes were checked.
- An injected mid-write failure rolls back all package/files/acks. A child
  process exits abruptly with code 19 before commit; reopen recovers with zero
  partial rows and a subsequent valid import succeeds. Eight concurrent identical
  attempts produce exactly one import, seven already-imported acks and one
  retained package.
- Fresh `-I -S -B` process blocks app/runtime/provider/engine imports, sockets,
  subprocesses, external databases and writes outside the temporary store while
  completing inactive ingestion. No Backtrader/VectorBT dependency or execution.
- Before/after checks preserve shared scorer output, canonical Swing 1.0.1,
  configured saved research-summary behavior and inactive state. Existing source
  remains unchanged apart from documentation and new importer/test files.
- **83 focused safe regression tests passed in 4.927s**: inbox, shared contracts,
  legacy scorer, local backtest reports, strategy profiles, execution safety,
  legacy scoring and provider routing.
- `scripts/run_tests.py`: **1400 safe tests passed in 103.459s**; dotenv and
  external sockets disabled by the existing runner, manual probes excluded.
- `scripts/verify_protected_artifacts.py`: **54 checked, zero failures**; 15
  existing worktree line endings normalized by its established verifier.
- `scripts/check_dev_environment.py --compile-only`: **297 files passed**.
  Full diagnostic was not invoked because it includes app startup/import-health.
- Final diff/whitespace, new documentation links, scoped staging/secret-pattern
  review and preservation checks are recorded in the task receipt. Shared-core,
  canonical strategy/risk/policy, existing opportunity/radar/research source,
  private configs, schedules and runtime settings are untouched. SSF/UI/rename
  backlog sections are preserved; only its X2 status advances to delivered.
- A scoped .gitattributes rule preserves hash-bound transport fixture bytes,
  including on Windows fresh checkouts. A Git index export verifies every
  package file against the independent raw-byte hashes; no other normalization
  rule changes. Targeted checks are repeated after this metadata-only addition.

The initial targeted run exposed Windows temporary-store cleanup errors in the
test harness: its SQLite inspection connections needed explicit close rather
than transaction context managers alone. The harness was corrected; final new,
focused and full suites pass. No unresolved verification failures.

## Limits and stop

All imported packages in verification are synthetic temporary fixtures. No real
release is installed into an operational store. Inactive support profiles and
matching hashes do not authenticate source truth, qualify market data, approve
research or grant trading authority. Embedded data references are not fetched or
semantically interpreted. Store/producer filesystem ownership is trusted; this
is not a signed vault. Per-package limits do not provide global disk retention
policy. No production support profiles are supplied.

Unsupported binary/model formats reject; JSON is retained as inert data. Future
evaluators need their own model/feature semantics, source-quality/authority,
parity and acceptance gates. No schema expansion for speculative engine/SSF
execution capabilities was made. No providers/models/brokers, downloads, orders,
account database access, service restart, deployment or push occurred. No measured
token/cost amounts are asserted.

Stop for owner review. **Next proposed execution card: X3 accepted radar
evaluation/adoption**, with explicit capabilities/parity/acceptance and effective
version/rollback semantics; not started here. Strategy import/evaluation, SSF
execution, feedback and UI remain separately scoped later work. Research
R0-ENGINE qualification is independent and not a prerequisite installed by X2.
