# X1a checkpoint — shared intelligence contracts

20 October 2026. DELIVERED_FOR_OWNER_REVIEW. R12 remains the sole ACTIVE/PARTIAL
milestone. X1a does not close R12 or deliver the complete shared research/execution
platform. X1b has not started.

## Source and scope

Authorized checkout: `C:/Users/Deon/Documents/GitHub/trading-system-complete`,
branch `master`, initial HEAD `912b4f240a674b636e932749eba09a6f073ebced`.
Initial working tree clean; no unrelated changes found. This checkpoint is a
local milestone-sized commit; no push/deploy or running app environment install.
The task output receipt records its resulting commit and final source status.

Added `packages/jse_intelligence_core`, distribution 0.1.0, Python >=3.12, zero
runtime dependencies. Immutable v1 SectorScope, EvidenceReference and
RadarReleaseManifest provide strict closed serialization, canonical SHA256
identities, actual receipt/acquisition and uncertain publication clocks,
correction/provenance references, explicit product/context isolation and exact
consumer compatibility checks. All release roles are inactive descriptions.
Five fixed accepted synthetic examples and eleven rejected examples accompany
the documented schema. Accepted means schema-valid only.

[ADR0071](../adr/0071-shared-intelligence-contract-boundary.md) records inspected
legacy reuse/import boundaries and implemented-versus-gated-path distinctions.
[Package README](../../packages/jse_intelligence_core/README.md) contains field
semantics, canonical encoding, install/test commands and future interface notes.
Scoring logic and application-owned state were not extracted or changed.

## Verification

- New contract suite: 11 tests passed (0.156s initial run), including fixed
  serialization/hash answers, rejected fixtures, input mutations, closed schemas,
  naive/ambiguous/false-exact clocks, chronology, hashes, scope/product widening,
  nested immutability, correction links, release roles and compatibility.
- Focused new plus legacy regression: 54 tests passed (0.772s) using the existing
  safe runner with explicit module selection: test_jse_intelligence_core,
  test_sentiment_providers, test_adaptive_fusion, test_legacy_scoring,
  test_canonical_source_registry, test_domain_contracts, test_hermes_cycles.
- `python -B scripts/run_tests.py`: **1366 tests passed in 102.812s**, with dotenv
  and external sockets disabled by the repository runner. Manual provider/LLM
  probes excluded. Development worker JSON in its output is test behavior, not a
  newly launched operational worker.
- `python -B scripts/verify_protected_artifacts.py`: **54 checked, zero failures**;
  15 worktree line endings normalized by the existing verifier.
- `python -B scripts/check_dev_environment.py --compile-only`: 294 files passed.
  The complete environment diagnostic was deliberately not invoked because its
  import-health step initializes the application; no service startup is needed.
- Offline wheel build and isolated target install passed using `--no-index
  --no-deps --no-build-isolation`. App venv has no setuptools/wheel, so existing
  bundled local build tools (setuptools 84.0.0/wheel 0.48.0) built a temporary
  package copy. The Python 3.12 app interpreter installed into a temporary target,
  not the application environment. Installed wheel passed all five accepted fixed
  fixture identities/serialization answers with `-I -S -B`.
- Fresh isolated source-package import/validation forbids runtime/provider/db
  imports, socket/subprocess/database activity, private file reads and writes.
  A separate .NET SHA256 calculation independently matched all five fixed IDs.
- Git diff/whitespace and scoped-file review passed; existing tracked changes
  are documentation only. Private config/strategy/scorer preservation is checked
  separately in the final task receipt. Protected baseline manifest is unchanged.

Full suite and focused logs are retained with the task receipt. There were no
verification failures. No package/provider/model downloads, inference, broker
sessions/orders, operational worker runs, runtime settings, schedules or UI
changes. No costs/token measurements were available; no amounts are asserted.

## Limits and exact continuation

Schema checks cannot authenticate source assertions or prove a supplied actual
receipt time. Reference hashes require later external byte/chain resolution;
opaque scope IDs require an app-owned approved registry. Compatibility equality
does not execute or validate model semantics. No real financial evidence,
learned model, signer/activation authority, transport/importer, strategy feedback
implementation or profitability is supplied. Approximate publication times stay
unknown with source-clock references; a later version may define time intervals.

Owner review is next. Proposed X1b: characterize legacy scoring/normalization,
then extract a minimal pure scorer with provenance and independently pinned
positive/negative/neutral/missing old/new parity fixtures, without score/default
drift. Read this checkpoint, ADR0071 and the planning handoff before assigning
that card. Do not proceed automatically to X1b, runtime wiring or UI.
