# Source-specific radar implementation and limits

## Boolean-only correction — 27 October 2026

The owner requested improving the observed errors immediately. A separate
eight-call local evaluation asked Qwen only for relevance booleans and assigned
source type from retained host metadata. On the same development items, frozen
assistant expectations matched 7/8 versus the previous 5/8. On eight new,
disjoint held-out sources, 6/8 matched; one false positive and two false
negatives remain across both packets. The new and old held-out sets differ.
The prompt wording and output structure both changed, so their individual
effects are not isolated. These assessments are not independent labels or
forecast evidence.

The daily worker now selects this protocol for experimental annotations at the
next eligible daily slot, preserving the same maximum of four two-item calls.
Existing in-progress v1 parents keep their original frozen protocol. A separate
four-call review of today's actual eight host-linked candidates returned four
matches and four misses; its all-positive source assessment has no negative
controls. The four misses are shown as host/model disagreements where the
original host-derived target is independently supported by the current retained
source or confirmed calendar record. The model's false answers are not rewritten.
Reviewed leads are prioritized within the eight-lead display. Source leads,
calendar clocks, the prior broad-request hold and today's spent slot remain.
Review the first ordinary daily output and continue improving the remaining errors.
See [ADR0084](../adr/0084-boolean-only-source-screening.md) and
[the evidence](../evidence/boolean-source-screening-v2.json).

## Earlier two-output protocol

27 October 2026. The dashboard now shows retained headline/SENS detail levels,
source clocks and fully written future dates mentioned in excerpts without
asserting an unconfirmed event date. Confirmed calendar events keep their own
source and warning clocks. Source leads remain present when Qwen is wrong,
uncertain, unavailable or a sibling pair fails.

The experimental worker saves the eight-candidate parent and up to four ordered
two-item tasks before inference. Each has a host-derived question, source quote,
strict two-way match and item-type response. Results, private raw bytes, source
admission findings and partial merges are persisted independently. The dashboard
labels all model annotations experimental and shows their test limitations.
No model output generates a date, issuer link, watch, trade or training label.

Two separate retained-source packets (16 distinct sources) were assessed before
inference by the assistant. The native development check matched 5/8 and the
held-out check 6/8. Across the 16 source-level decisions: eight true positives,
three false positives, three true negatives and two false negatives relative to
those assistant assessments. Examples include a wrong-issuer or wrong-event
match, and a missed confirmed monetary-policy briefing. Model type labels also
included unsupported classifications, which remain visible as unavailable or
requiring review rather than overwriting the underlying source.

These results support an exploratory annotation, not reliable relevance or
prediction. The separate broad-request 0/8 failure and hold remain visible.
The new daily worker has not yet run a new real daily packet because the
27 October daily reservation was already spent; it can run at the next eligible
idle slot. The next work is to review that first daily output and improve the
model's per-item discrimination and category handling using a separately frozen
evaluation, including human review when available. Do not treat these 16
assistant assessments as training data or a representative market sample.

The daily resource budget is one parent per local date, with at most four
two-item generations; failed reservations are not retried. PC session and ten
minutes idle are required. RAM starts at 3.5 GiB free and aborts below 1.5 GiB;
the owned local process uses two CPU threads and no GPU. Read-only dashboard
refresh makes zero model calls. R12 remains active/partial; P1 remains open.
