# P0 retained-news activation manifest — review only

This is a proposed procedure, not authorization or evidence of production writes.
Do not execute until the owner authorizes activation and the remaining readiness
items are resolved.

## Ownership and scope

The source is PostgreSQL `localhost:55432/trading_local_20261015`, account
`hermes-local-research-v1`, kind `hermes-news-input`. The target is PostgreSQL
`localhost:5433/trading`, the same account and kind. The 18 November read-only
preflight found 72 source captures, zero matching target IDs and zero conflicts;
repeat this check at activation because counts can change. The SENS bridge
remains unchanged by default; news delivery requires `include_news=True`.

Copy each original `capture_id`, exact payload and original `received_at` as
the record's availability clock. Publication timestamps, URLs and article
evidence IDs remain inside the unchanged payload. Headline-only summaries remain
headline-only; keyword associations are candidate links requiring review.
Existing identical identities are skipped; conflicting immutable identities
abort the transaction. No source records are updated or deleted.

## Required preflight and backup

1. Resolve both effective connection identities without printing credentials.
   Verify database, host and port using a read-only SQL session.
2. Take fresh `pg_dump` custom-format backups of both named databases, record
   paths and byte sizes, verify each using `pg_restore --list`, and perform a
   row-count restore check in a separately named scratch database. Never restore
   into either live database during this check.
3. Capture source/target counts by account and kind, IDs, payload hashes and
   receipt clocks. Check all target identity conflicts before any write. Ensure
   the dashboard's intended database ownership and activation route are agreed.
4. Confirm collection and model workers will not be restarted or rescheduled.
   Obtain explicit owner approval for the exact migration and activation steps.

## Transaction and verification

Invoke the existing bridge explicitly once with `include_news=True`, against a
read-only source and the explicitly verified target. The target bridge uses one
transaction; any identity conflict or exception rolls back its writes. Record
the bridge receipt ID, source count, new count and existing count. Re-read each
target payload by original ID and compare exact payload, account, kind and
availability time to source; check publication and receipt clocks. Check that
the three SARB article receipts and existing calendar event are present and
that headline-only candidates are labelled unverified. Re-run the bridge and
require zero new records. Independently compare before/after counts and hashes.

## Failure recovery and rollback

If the transaction fails, retain the error and verify that target counts and
identities match the preflight snapshot before any retry. An idempotent rerun is
appropriate only after resolving any immutable-identity conflict. If it commits
but downstream verification fails, keep the immutable imported evidence and
disable only the explicit future news-delivery option; do not delete receipts,
reset archives, or overwrite the production database. A full restore is a
separate owner-approved recovery action after a tested scratch restore and
assessment of intervening writes. Preserve backups and the verification log.

## Remaining blockers

The current live dashboard uses the legacy PostgreSQL endpoint. The target
macro records live in `trading`, so copying news alone does not establish a
single live event-preparation path. The runtime database ownership/activation
decision and deployment must be explicitly resolved. No live dashboard result
is claimed. The bridge's existing 5,000-record fail-closed transfer ceiling and
the source reader's bounded scan window need further design/validation before
an unqualified long-term operational claim.
