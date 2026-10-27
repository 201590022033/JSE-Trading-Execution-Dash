# ADR0084 — Separate model relevance from source-type labelling

27 October 2026. The owner asked to work on the daily screening errors now.
The prior two-item protocol asked the small model to answer independent relevance
questions and assign source types together. It returned wrong issuer/event
matches, missed matches and unsupported source types in its bounded checks.

The v2 protocol asks only for one explicit boolean per source. The host supplies
the retained source kind for display: a confirmed calendar reference, SENS
headline, or news excerpt. This type is not presented as a model-generated fact.
The revised wording and simpler output were tested together; the results do not
isolate which change caused any difference. Every candidate still has its own
question, an independent true/false response and per-item source admission.

Before inference, register the same eight development questions and sources
used previously, plus eight new disjoint retained-source questions with positive,
wrong-issuer and wrong-event controls. Freeze the inputs, expected answers,
model/digest and an eight-call budget. The assistant's expectations are not
independent human ground truth or training data. Before generation, require a
minimum 6/8 on each packet and both correct positive and negative held-out cases
for an experimental replacement, not a forecast or strategy promotion.

The repeated development packet improved from 5/8 to 7/8. The new held-out
packet returned 6/8; one false positive and two false negatives remain across
both packets. The old and new held-out packets differ, so their scores are not a
paired comparison. Preserve all earlier and new raw responses. Select v2 as an
experimental annotation, never as a filter on source leads. Keep the previous
broad-request hold, all calendar facts, 48/24-hour clocks, zero trading weight,
one daily parent and at most four child calls. An existing in-progress v1 parent
continues with its frozen protocol; only a new parent uses v2. Today's spent
daily slot is not reset.

The owner also requested progress before the next daily run. A separate frozen
four-call review processed today's eight current host-linked candidates without
resetting that slot. Qwen matched four and returned false for four. All eight
were assistant-assessed as source-linked; this all-positive review is not a
negative-control test or general accuracy estimate. The four misses included the
confirmed SARB briefing, two SENS headlines and an oil story.

For daily and one-off review packets only, when a false model decision conflicts
with the host's own confirmed calendar reference or literal issuer/topic link,
show a host/model disagreement. Revalidate source identity, quote, freshness and
the exact host-derived task first; never apply this reconciliation to altered
validation questions. Preserve the raw false response. Prioritize the reviewed
sources in the bounded visible list so a disagreement is not hidden below the
display cap. This makes existing information accessible; it does not turn a
model error into a correct model decision or predict an announcement.
