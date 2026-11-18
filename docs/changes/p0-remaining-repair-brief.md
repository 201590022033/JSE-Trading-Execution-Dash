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
