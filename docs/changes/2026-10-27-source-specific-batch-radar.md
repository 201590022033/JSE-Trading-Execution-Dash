# Source-specific batch radar

Implemented source-specific questions in frozen two-item batches, with four
spent child calls at most under one daily parent. Partial failures affect only
their own model assessments. Retained source leads, confirmed events and clocks
remain available, and the UI distinguishes headline-only detail and source dates
from model annotations or forecasts.

Two disjoint real-source packets were preregistered and screened with eight
native Qwen calls. Development matched assistant expectations 5/8; held-out
matched 6/8. Three false positives and two false negatives remain across both
packets. Some item types were unsupported. The daily path is enabled only for
clearly labelled experimental source annotations; it does not veto source
leads, create model watches or change trading weights. The prior broad-request
hold remains. Today's older daily reservation was not reset, so the first new
daily result is still pending the next eligible idle day.

The full source packet, prior model attempts and all 27 private native response
archives were preserved and their hashes checked. The Sasol paired experiment's
definition remains intact. Verification passed 1,557 full offline tests,
99 focused tests and 54 protected checks. See [ADR0083](../adr/0083-source-specific-batch-radar.md),
[operating notes](../research/SOURCE_SPECIFIC_RADAR.md) and
[evidence](../evidence/source-specific-radar-validation.json). P1 remains open.
