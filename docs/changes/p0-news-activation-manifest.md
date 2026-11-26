# Retained-news transfer and verification, 26 November 2026

The one-time transfer copied the audited 72 Hermes receipts to the dashboard database. The legacy cluster contained 82 when copied. The transfer used the November 18 review cutoff and left ten later receipts in the source.

## Ownership and backup

The original source was the stopped PostgreSQL 18 cluster for trading_local_20261015 on port 55432. All 1,835 files were hash-checked before startup of an isolated loopback copy. PostgreSQL completed crash recovery on that copy. The destination was trading on port 5433. The running dashboard used this destination for event preparation.

Both custom-format backups were listed and restored into separate scratch databases. Snapshot counts matched for paper_accounts, paper_records and paper_record_archives. The source counts were 10, 9,003 and 0. The target counts were 9, 3,203 and 0. Local backup sizes were 5,127,804 and 1,257,961 bytes respectively. The manifests and restore receipts are under runtime/backups/news-transfer-20261126-093749 and are excluded from Git.

## One-time delivery

The operator invoked transfer_news_page on the read-only copy with a cutoff of 2026-11-18T12:53:33Z. The target repository owned the transaction. Each capture retained its original account, kind, ID, availability clock and payload. All 72 target rows matched the source before commit and on repeat. A second invocation added zero. A preliminary transaction-wrapper error rolled back before the successful transfer.

The existing event-preparation endpoint and News & SENS page displayed the original November 19 SARB decision and all three historical Moneyweb links. The rates, inflation and rand headlines remain keyword candidates requiring review. No model was invoked by the transfer.

## Repeating an explicitly requested bridge delivery

The existing scheduled path retains its SENS-only input. For a separate news-enabled invocation, the script accepts --bridge-only --include-news. This requires the expected local source and target to be available. A new invocation uses the current clock and can include later receipts than the historical transfer.

The integrated runner retains the current dashboard's bounded paging and checkpoint contract. Each invocation commits its target changes together. It then atomically replaces its local cursor file. SENS-only and news-enabled invocations have separate files and share the existing process lock. Pending cursors produce a partial receipt and exit code 3. A subsequent invocation checks the head again and resumes the older page. A conflict aborts the transaction. A failure after commit but before cursor persistence can replay the same page safely using immutable identities.

For any further transfer, verify both database identities, take and scratch-restore fresh backups, and compare the exact IDs, clocks and payloads before and after delivery. Retain the receipt and repeat to check for duplicates. Investigate identity conflicts before retrying. If downstream delivery fails, preserve imported receipts and inspect the read path. A production restore requires separate approval and reconciliation of intervening writes.
