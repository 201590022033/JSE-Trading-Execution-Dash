# ADR0087 — Keep assistant source reviews separate from outcome assertions

28 October 2026. The first prospective watch review exposed two timing gaps:
an election headline combined an already-ended vote with a future vote beyond
the watch's expiry, and a related Fed report was published after the watch
while the decision itself remained pending. Existing automatic source links
and human outcome reviews cannot express these distinctions on their own.

Append a source-cited assistant review to the existing radar ledger rather than
rewriting a watch, model answer or human review. Each citation must refer to
the immutable original watch packet or a hash-checked, explicitly imported
source and an exact excerpt. Keep publication, capture and first local receipt
as separate clocks; a source recorded later may have been captured or
published earlier. The UI labels assistant-reviewed semantic links separately
from exact-phrase and shared-word matches. An original retained packet remains
reviewable after the seven-day fresh-feed window.

Assistant assessments are review evidence, not independent human labels or
automatic occurrence outcomes. A source saying an event is scheduled is not
the event's outcome. The current review uses previously examined examples;
its 2/4 agreement is descriptive, not a forecast-accuracy or promotion claim.
The initial receipts created during this implementation remain readable and
linkable after capture-clock fields were added. Repeat reviews are idempotent.
No source, model or execution budget is reset; no model call, numerical fit,
human verdict, order or learned-weight update is implied.

See [the first review](../changes/2026-10-28-prospective-radar-review.md) and
[its evidence](../evidence/prospective-radar-review-2026-10-28.json). R12
remains ACTIVE/PARTIAL; P1 remains open.
