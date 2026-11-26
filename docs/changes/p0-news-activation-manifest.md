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
remains SENS-only by default; news delivery requires `include_news=True`.

Copy each original `capture_id`, exact payload and original `received_at` as
the record's availability clock. Publication timestamps, URLs and article
evidence IDs remain inside the unchanged payload. Headline-only summaries remain
headline-only; keyword associations are candidate links requiring review.
Existing identical identities are skipped; conflicting immutable identities
abort the current page transaction. No source records are updated or deleted.

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
read-only source and the explicitly verified target. Process bounded pages
until the result is `COMPLETE`. A `PARTIAL_DELIVERY` response has no completion
receipt and requires another invocation with the same delivery mode. The
target locks a dedicated checkpoint account and commits each page's evidence
and cursor together. SENS-only and news-enabled sweeps have separate cursors.
The final receipt retains the existing kind and state, with a versioned
identity based on the ordered sweep digest. Earlier receipts remain intact.
Each sweep has a fixed receipt-clock cutoff. A row inserted ahead of a cursor
already traversed is reconciled on the next complete sweep.

Record the bridge receipt ID, source count, new count and existing count. Re-read each
target payload by original ID and compare exact payload, account, kind and
availability time to source; check publication and receipt clocks. Check that
the three SARB article receipts and existing calendar event are present and
that headline-only candidates are labelled unverified. Re-run the bridge and
require zero new records. Independently compare before/after counts and hashes.

## Failure recovery and rollback

If a page fails, retain the error. Confirm the failed page committed no rows
and the cursor still points to that page. Previously committed pages remain as
immutable evidence. Compare them against the preflight manifest and resume
only after resolving the conflict. If the sweep completes
but downstream verification fails, keep the immutable imported evidence and
disable only the explicit future news-delivery option; do not delete receipts,
reset archives, or overwrite the production database. A full restore is a
separate owner-approved recovery action after a tested scratch restore and
assessment of intervening writes. Preserve backups and the verification log.

## Remaining blockers

The historic dashboard connection to port 55432 was observed on 18 November.
On 25 November, the current Flask process was observed connected to port 5433,
and the separate local SQL check identified that port as `trading`. There was
no 55432 listener in the sampled state. Re-establish endpoint routing and
source availability before any activation. The repair branch is not the live
dashboard, and the historical 72-item transfer count is no longer a live
manifest. The bridge now bounds and resumes delivery. Active Radar source
views still deliberately bound their scans and expose truncation. Event
preparation's other retained record families still have capacity guards and
need separate review before claiming readiness at arbitrary history sizes.
