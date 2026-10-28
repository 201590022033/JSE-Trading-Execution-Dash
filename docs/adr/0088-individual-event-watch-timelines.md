# ADR0088 — Keep separate source-cited event watches through their dates

28 October 2026. A saved news watch named the Israeli and US votes together.
The first had ended before the watch, while the second was scheduled after its
48-hour expiry. A single verdict or shared deadline cannot describe both.

Keep the original watch, discovery, source packet, Qwen response, reviews and
expiry receipts immutable. Recognizable parallel event clauses and lists with a
shared event noun may produce separately identified child watches from exact
source fragments. These are host-derived suggestions, with their own actual
creation time; the original model did not necessarily name each child. If Qwen
copied just one named clause, an overlapping multi-event headline can still be
split. Unsupported forms remain visible as the original source lead rather than
being discarded. The splitter is a bounded text heuristic, not a claim that all
multi-event headlines or event meanings can be identified automatically.

An individual watch, whether split or originally single, may acquire an
append-only, source-cited date record. Dates apply from the time the new record
is made, never from an earlier source publication or parent-watch time. Exact
full dates may be recognized in one event-specific clause; earlier retained
sources and later follow-ups are both usable. Separated event mentions in the same
sentence and conflicting candidate dates do not get an automatic date
assignment; adjacent terms such as an earnings release can describe one event.
While dates conflict, the watch remains visible through the latest candidate
date without selecting it. A named conflicting issuer cannot supply a date for another
issuer. A local operator may review a specific date and source through the
existing authenticated radar UI/API. Old date and conflict records remain
available. Model output, source-wording fallback, host-derived candidate,
assistant interpretation and operator review retain distinct origins.

A date-only watch remains active through the end of its date. With a reviewed
IANA timezone this is the next local midnight, including daylight-saving
changes. When its timezone is unknown, use the conservative end of that date
in UTC-12; this is a duration boundary, not an asserted event or release time.
Earlier dated-watch expiry receipts remain stored. A legacy extension is
recorded when the follow-up clock applies it, so earlier as-of views retain
their original expiry; current state and new no-observation reviews use the
extended date boundary. A source date is
not an occurrence or a price prediction. A date explicitly attributed to
"today" may be interpreted only in an assistant/operator review with a source
publication timestamp and a stated publication-local timezone.

The regular follow-up clock records event-specific related-source leads,
unique date candidates, conflicting dates and expiry observations. It cannot
record a human verdict or score P1 by itself. Read-only status cannot write or
call a model. Existing idle-only/model call limits, original source records,
calendar core and research/trading weights are unchanged. R12 remains
ACTIVE/PARTIAL; P1 remains open.

See [the operating note](../changes/2026-10-28-individual-event-watches.md)
and [the saved real-source checkpoint](../evidence/radar-event-components-2026-10-28.json).
