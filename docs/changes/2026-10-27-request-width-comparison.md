# Request wording and packet size comparison

The owner-approved four-call Qwen comparison is complete. Broad request: 2/2
expected selections at two candidates, 0/8 at eight. Explicit Sasol AGM request:
the correct selection at both widths, including seven rejections at full width.
All four responses completed. The broad small case contains only positive expected
answers; the explicit cases contain both positive and negative controls. Source
assessments were frozen assistant review, not independent human labels.

The comparison runner reuses the owned model, existing prompt/schema and radar
persistence, and freezes all source and prompt inputs before the first call.
Four reservations were spent; a replay makes no new calls. Raw hashes and the
original 0/8 response remain intact. The old broad-request hold remains active;
no model watch is produced by this experiment. The next fix plan introduces
source-specific tasks in small batches and a merged eight-item validation path,
with retained source leads available even when individual model calls fail.

Verification: 1,544 offline tests, 85 focused tests and 54 protected checks
passed; all four new archives and the earlier real-screen archive match their
hashes. The Sasol paired definition remains intact.

The local comparison is not evidence of forecasting, trained model weights,
or strategy acceptance. R12 stays active/partial and P1 remains open. See
[ADR0082](../adr/0082-request-width-diagnosis.md),
[results](../evidence/request-width-comparison.json), and
[next fix plan](../research/REAL_SCREEN_BATCH_FIX_PLAN.md).
