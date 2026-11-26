# P0 remaining repair — implementation brief

Objective: make the existing retained-news bridge and radar source reads safe
as history grows, while preserving both databases and all existing feeds.

Work on `repair/p0-market-intelligence`. Do not merge, push, migrate production
data, restart processes, change scheduling, ViewPoint or model settings, or
begin Phase C/D or AI4/AI5 without a new explicit instruction.

1. Replace the bridge's all-history ceiling with bounded, resumable keyset
   batches. Preserve the immutable source account, IDs, payloads and clocks.
   Define deterministic checkpoint/receipt semantics, idempotent retries,
   duplicate and conflict handling, and an explicit partial-delivery state.
   Preserve the existing SENS-only default and its receipt compatibility.
2. Ensure source readers do not silently omit recent evidence, including tied
   timestamps, delayed article receipt and concurrent insertions. Bound each
   query and expose incomplete coverage rather than claiming completeness.
3. Prove SQLite and PostgreSQL behaviour with isolated fixtures, including
   above 5,000 records, exact page boundaries, duplicate/conflicting records,
   rollback, resume and concurrent writes. Do not run write tests on either
   production database. Preserve all nine frozen modules.
4. Keep dashboard database ownership explicit. Current Flask requests were
   observed connecting to localhost:55432; the SARB macro event is in
   localhost:5433. Prepare a single coherent activation plan that connects
   existing components without silently switching the whole application.
5. Provide read-only real-record evidence, test results, exact rollback and
   updated migration manifest. Label live activation as pending until actually
   demonstrated. Stop before production activation and report the concrete
   approval needed for the 72-record transfer and dashboard deployment.

## 25 November evening checkpoint

- The isolated repair worktree holds the uncommitted paged `sync` integration.
  The existing SENS-only entry point uses it without a scheduler change.
  Explicit news delivery still requires opt-in. A bounded invocation can
  return partial progress and resume from the target checkpoint. A later
  conflict rolls back the current page while preserving earlier pages.
- 147 focused checks passed across the bridge, Radar, Event Preparation,
  Sasol refinement, weekly brief and repository tests. All nine frozen
  modules match the baseline. A separate temporary PostgreSQL 18 cluster
  verified 500 records in the first bounded invocation, 4,501 on resume,
  a late record plus an opt-in news capture on the next sweep, zero on retry,
  and an explicit immutable-record conflict. The cluster was stopped and
  its temporary files removed.
- The current dashboard's Event Preparation API returned
  `SARB_MPC_2026-11` as `calendar-event-e4699f27a5ca345177c41f2f731d8099103b1984f9dde5e1b5fcf6e3e9fd3853`,
  with automated attribution, 52 keyword candidates counted and zero model
  calls on read. The three historical Moneyweb URLs did not appear in the
  returned candidate list. The 55432 source was not listening when checked,
  so this does not validate the historical transfer manifest.
- Next: verify both endpoint/store assignments after the legacy source is
  available, compare the three source identities against the current
  projection, and review the remaining non-bridge capacity limits. Keep
  the active dashboard on its current code and preserve all production data.

## 26 November morning checkpoint

- Matched the live Flask process's TCP client ports to PostgreSQL sessions
  during both the Radar and Event Preparation requests. Both served HTTP 200
  and connected to `trading` on port 5433. SQL in a read-only transaction
  counted 2,842 Radar SENS source receipts and zero Hermes news captures in
  `trading`. No 55432 listener was present.
- The Event Preparation repair retrieves the newest attempt and up to 50
  packets per event with a timestamp and stable identity sort, and loads
  the matching model result by immutable ID and as-of time. It displays a
  coverage notice when older packets are omitted. The test passed with
  5,001 unrelated attempts, and a separate PostgreSQL 18 instance verified
  the database-specific predicates, clock guard and tie ordering.
- Still blocked for activation: refresh the historical transfer manifest
  when the legacy store is available. The three historical headline links
  are absent from the current live response. Do not infer their provenance
  from its 52 keyword candidates. The repair is based on an older branch.
  Evaluate it against the version selected for deployment before requesting
  activation. Active Radar categories outside the repaired follow-ups and
  bounded source scans still have other capacity guards. The old
  `research_calendar.py` remains frozen.

## Integrated checkpoint, 26 November

The activated 72-receipt transfer and the final integrated paging contract are recorded in p0-news-activation-manifest.md. The earlier isolated checkpoint-account design was superseded by the cursor contract already in master. The original legacy port remains unavailable for scheduled reads while the historical links are served from trading.
