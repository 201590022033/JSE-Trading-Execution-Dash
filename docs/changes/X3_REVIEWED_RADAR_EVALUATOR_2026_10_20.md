# X3 reviewed radar evaluator — 20 October 2026

Status: SOFTWARE DELIVERED FOR REVIEW / REAL ARTIFACT ACCEPTANCE PENDING.
Owner requested X3 after X2. R12 remains the sole ACTIVE/PARTIAL milestone.

## Delivered

`application/radar_releases` adds a bounded inert-JSON evaluator and explicit
current-radar adapter, reusing shared-core 0.2.0 and immutable X2 release bytes.
Manifest/model/API capability and complete parity checks precede acceptance.
An independent append-only journal records idempotent operator reviews, exact
effective-time selections, prospective rollback and attributed snapshot feedback.
Compare-and-swap prevents concurrent selections overwriting one another; selected
review identity is frozen even if a later review changes a source allowlist.

Attention and directional lanes have distinct review criteria. Attention never
implies trade direction. Directional requires exact source-asserted publication
time. Policy and unsupported products fail closed. Current source pause/admission,
policy freshness, evidence byte binding, exact scope/vehicle/horizon, original
observed provenance and direct full issuer name are required. Old publication or
acquisition cannot be rejuvenated by a new receipt. Feedback retains alert,
no-alert, no-release and unavailable observations without altering old decisions.

See [protocol and invocation](../research/X3_REVIEWED_RADAR_EVALUATOR.md) and
[ADR0074](../adr/0074-reviewed-radar-release-evaluation.md).

## Verification

- 24 focused X3 tests pass, including literal independent full-result parity,
  resealed X2-valid packages with bad parity/model formats, review identity,
  effective-time boundary, version switch/rollback/reopen, pinned review,
  concurrent selectors, transactional crash rollback and journal immutability.
- Full offline suite: **1425 passed** (1401 existing + 24 X3), 112.265 seconds on
  the first full run. Final verification is recorded in the owner output receipt.
- All **54 protected-artifact checks pass**; compile-only check passes for
  298 root/script files; focused tests compile/import the new package.
- An isolated subprocess denies dashboard, provider/model/engine/database-driver
  imports and network calls while exercising import → acceptance → selection →
  current adapter scoring entirely in temporary X2/journal databases.
- Synthetic attention versions 0.1.0/0.2.0 give 0.7/0.6 on the same positive
  packet; rollback returns 0.7 without rewriting prior observations. All fixture
  releases/profiles are explicitly test-only; default service rejects them.

## Acceptance boundary and next cards

No compatible **real reviewed research artifact** was supplied. The code and
synthetic qualification path are delivered; genuine artifact acceptance,
role-specific research evidence and production integration remain pending. No
research improvement, learned fit quality, empirical directional accuracy or
profitability is claimed. Review/source policy declarations are trusted local
operator inputs, not signatures or independently validated truth. Source-policy
projection must use existing R12 state when real runtime integration is reviewed.

The running dashboard, providers/models, source pause, shared-core and X2 code,
strategies/defaults, paper/account stores, services and scheduled tasks are
unchanged. No real package/review/selection was installed, no worker or dashboard
restart, push, deployment or order occurred. X2 still records every import INACTIVE.

Only **X4** (StrategyRelease schema/compatibility and inactive evaluator adapter)
and **X5** (execution outcome feedback and round-trip fixture) remain numbered X
cards after X3. Their prerequisites still apply. Research R cards/P1 real campaign,
P2 operational shakedown, U1 view-only reporting and extensions are separate work.
The existing SSF/UI/rename backlog sections are preserved. Stop here for owner review.
