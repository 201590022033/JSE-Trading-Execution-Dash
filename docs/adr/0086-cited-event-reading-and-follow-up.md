# ADR0086 — Source-cited event reading and prospective watch follow-up

28 October 2026. The owner requested that the existing radar read retained
headlines and excerpts for specific events, retain incomplete sources, and
record watches early enough to review later related reports and expiry.
This extends R12 as an experimental advisory lane; P1 remains open.

The new lane freezes up to 100 fresh captured news sources locally, including
items with no catalog issuer or recognized topic. It prioritizes sources not
previously examined and then explicit forward-looking wording. It asks Qwen
about up to four individual sources per local day, under a separate immutable
parent from the existing source-screening budget (up to eight calls). These
are maximums, not a claim of complete source or internet coverage; some
fresh items may expire before a four-item daily budget reaches them. Full
retained sources remain in their original archives. Headline-only items are
usable, and one failure does not exclude the rest. The event parent checks
its own eligibility even when the separate screening result is incomplete.

Each model response is tied to its exact source and receipt. Model-written
event phrases must be literal source substrings; issuer links come from direct
host-supported mentions. A fully specified future date is tentative, source
cited, and requires separate review to become a confirmed calendar entry. If
a date is missing, past, incomplete or not in the source, it is withheld
while a valid event phrase remains usable. Known calendar events remain
references rather than duplicate model watches. A fresh source is required
when the watch is actually saved. The first saved watch timestamp is never
backdated or reset by repeat receipts.

When Qwen misses a source containing explicit forward-looking wording, the
literal wording may create a separate conditional review lead. This is
labelled as a source-wording fallback, not a Qwen answer or a confirmed
event. Questions that may be general commentary are flagged. These mechanisms
do not establish whether an event will occur and do not suppress Qwen errors.

Later sources are linked only after the watch's actual save time, using an
exact event phrase or at least two shared event words. Shared-word links need
the original direct issuer or topic to be repeated; an exact phrase can also be
kept when the issuer or topic is absent, with that gap flagged. A source naming
a different known issuer is not linked. Shared-word links are visibly labeled for review.
These are leads, not automatic outcome labels. A dedicated five-minute radar
clock points to this checkout and records observed expiry while signed in;
human review records occurred, not observed, or
incorrect link with a note. The UI shows actual watch, later receipt and review
times, elapsed hours, and date-only lead where available. A review time is not
represented as the event's actual occurrence time.

The first eight separately registered idle-only diagnostic calls agreed with
pre-generation assistant assessments on six cases. A commentary headline was
mistaken for an event; a Fed-rate headline was missed. Two responses proposed
unsupported dates, which were withheld. These are previously retained,
assistant-assessed examples, not independent labels, accuracy validation,
model training, or proof of advance prediction. The first four-call daily
packet produced two Qwen suggestions, including the flagged commentary; a
later host wording fallback retained the missed Fed-rate source. The record
timestamps are actual creation times. Evidence is summarized in
[event-extraction-native-2026-10-28.json](../evidence/event-extraction-native-2026-10-28.json).

Reservations are spent before calls, failed or interrupted calls are retained
without automatic retry, and each source is independent. The routine ten-minute
idle check, two CPU threads, no GPU, 3.5 GiB minimum free RAM at start,
1.5 GiB abort floor, isolated owned process, and existing screening budgets
remain. The current day's completed screening and event parent are not reset.
All outputs are advisory, with zero trading weight and no live execution.
