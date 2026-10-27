# Simplify source screening after observed errors

The small model now answers only per-item relevance booleans; the host displays
the source kind from retained calendar or news metadata. The response still
allows true and false at every candidate, supports partial failures and never
removes the underlying source lead. The previous nested type-plus-relevance
protocol and every earlier response remain valid and unmodified.

The repeated eight-source development packet improved from 5/8 to 7/8 against
the frozen assistant assessment. A different eight-source held-out packet
matched 6/8. The new test contains one false positive and two false negatives
in total. These are small, non-independent assistant assessments; model relevance
and forecasting are not established. The prompt and output shape changed
together, so the cause of the gain is not isolated.

The owner requested working on errors now, so eight separate local idle calls
were used; the daily reservation was not reset. The new protocol is selected
only for experimental source annotations under the same four-call daily limit.
Another separately registered four-call review of today's eight host-linked
items returned four matches and four misses. This all-positive review has no
negative controls. The dashboard now retains and highlights the four conflicts
between a false Qwen answer and a verified host source/calendar link; original
model decisions stay unchanged. Reviewed sources are prioritized in the visible
list. The normal daily reservation remains spent. P1 remains open; review the
first ordinary daily output at the next eligible slot.
Verification passed 1,566 full offline tests, 107 focused tests and 54
protected checks; all 39 retained model response archives matched their hashes.
See [ADR0084](../adr/0084-boolean-only-source-screening.md) and
[evidence](../evidence/boolean-source-screening-v2.json).
