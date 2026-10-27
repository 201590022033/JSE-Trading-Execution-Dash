## Current state: individual source rechecks and event cards

27 October 2026. Four previously missed sources matched when the exact questions
were asked individually; byte-identical original pair prompts repeated the four
misses. A separate mixed-control comparison retained one false positive in an
individual test. New daily parents can spend up to four additional idle-only
single rechecks on host-supported disagreements, preserving original answers,
for up to eight total calls. No new daily run has yet been observed. The current
review displays the four singleton rechecks. Source cards show retained headline,
excerpt, named issuer/sector, topic, source and unconfirmed mentioned dates.
This is sourced navigation, not LLM event forecasting. See ADR0085.

## Earlier state: boolean-only source screening selected experimentally

27 October 2026. At the owner's request, the existing source-matching errors
were addressed without waiting for a new daily packet. Qwen now answers only
per-item booleans while the host displays source type from retained metadata.
The same development packet improved from 5/8 to 7/8 relative to its frozen
assistant assessment; a different held-out packet matched 6/8. One false match
and two misses remain. Prompt wording and response shape changed together, so
the cause of the observed difference is not isolated. The small assistant
review is not independent accuracy or forecast evidence.

The v2 protocol is selected for experimental daily source annotations with the
same four-call limit; an in-progress v1 packet retains its original protocol.
An additional separately registered current-packet review returned four of
eight model matches and four host/model disagreements. The dashboard shows
reviewed sources and reconciled source-link disagreements without rewriting
those false responses or presenting an all-positive review as model accuracy.
Source leads, calendar dates, the old broad-request hold and today's spent
daily slot are preserved. See [operating notes](SOURCE_SPECIFIC_RADAR.md),
[ADR0084](../adr/0084-boolean-only-source-screening.md) and
[evidence](../evidence/boolean-source-screening-v2.json). P1 remains open.

## Earlier state: source-specific batch annotations are experimental

27 October 2026. The two-item batch path is implemented and enabled for
experimental source annotations. A daily parent preserves its source packet and
allows up to four spent child calls; partial failures leave other assessments
and all retained leads available. The dashboard identifies headline-only
sources, explicit dates mentioned in text and confirmed calendar dates.

Eight native validation calls over two disjoint eight-source packets matched
assistant expectations 5/8 in development and 6/8 held out. Three false matches
and two misses remain; no independent accuracy or forecasting skill is claimed.
The previous broad request hold stays active. Today's daily slot was already
spent, so the first new daily batch awaits the next eligible idle date. See
[operating notes](SOURCE_SPECIFIC_RADAR.md),
[ADR0083](../adr/0083-source-specific-batch-radar.md), and
[native evidence](../evidence/source-specific-radar-validation.json).
R12 remains active/partial and P1 remains open.

## Earlier state: request/width diagnosis complete; batch fix planned

27 October 2026. Four authorized native calls found that the existing broad
request selected 2/2 expected items in the small packet, but 0/8 in the full
packet. A specific Sasol AGM request selected the correct candidate at both
widths, including negative issuer/event controls. The broad small packet had
only positives, and all expectations are preregistered assistant assessments.
This is an observed interaction on one retained packet, not an accuracy or
forecast claim. The original broad-request hold and source leads remain.

The next planned fix asks explicit source-specific questions in batches of up
to two, merges results back into the full daily packet, and preserves useful
source leads if a model call fails. Its proposed future model budget, held-out
comparison and per-item admission are described in
[the fix plan](REAL_SCREEN_BATCH_FIX_PLAN.md). See
[ADR0082](../adr/0082-request-width-diagnosis.md) and
[native evidence](../evidence/request-width-comparison.json). P1 remains open.

## Earlier state: real broad-request review failed; sources remain available

27 October 2026. The separately approved one-call real-source screen selected
0/8 candidates. The earlier eight passes tested literal event requests on one
or two candidates. They do not qualify the broader eight-candidate daily request.
The pre-generation assistant source assessment disagrees with all eight choices;
it is not independent human ground truth or a training target.

Only repetitions of that exact broad request/model are held pending correction.
Append-only latest review/clearance records control this operational hold.
Collection, source leads, calendar warnings and other research continue. Display
both narrow checks and actual screening review instead of implying readiness.

Current v4 news eligibility expires at the earlier of known publication and
first usable receipt plus 48 hours; unknown publication uses first receipt.
Filter expired items before diversity/capping and retain all older archive data.
Known calendar matches keep event/title/issuer references without duplicate
model watches or consuming the five-news cap. Validate each selected news item
individually and retain matched/rejected/admitted/cap-held IDs in the audit.

The real response remains ABSTAIN with zero fabricated watches. Its one-call
allowance and original daily reservation stay spent. Next is the separately
proposed four-call request-versus-width comparison, not queued. See
[review](../changes/2026-10-27-first-real-screen-review.md),
[ADR0081](../adr/0081-source-screening-review-and-admission.md) and
[corrective design](REAL_SCREEN_REQUEST_CORRECTION.md). P1 remains open.

## Earlier v4 narrow-check qualification

27 October 2026. The same bounded request/evidence/boolean schema now serves
qualification and daily discovery. Every candidate needs true or false; only true
IDs map to retained host facts, capped at five in host order. Reject omitted or
invented IDs, duplicate keys and non-boolean substitutes. No generated date,
quotation or issuer link replaces the host-validated record.

All eight frozen native checks passed (five supported matches and seven rejected
boolean decisions across two retained sources). Matching, unrelated, same issuer /
wrong event, unsupported precision and reversed order are covered. Prior failures
remain. This qualifies narrow source relevance only, not broad news accuracy,
free-text date extraction, learning gains, forecasting or P1.

The owner's separate eight-call foreground allowance is spent. One memory wait
resumed only unattempted cases; replay makes no ninth call. The original four-call
allowance also remains spent. Routine screening keeps ten-minute idle, two CPU
threads, no GPU and unchanged memory limits; today's previously spent discovery
slot cannot reset. Next eligible daily screening uses v4, with independent source
leads/calendar dates remaining visible. Source/watch expiry and observation rules
are unchanged. See [operating result](../changes/2026-10-27-qwen-boolean-relevance.md)
and [ADR0080](../adr/0080-explicit-boolean-radar-relevance.md).

The earlier checkpoints below retain the failed protocols and installation state.

## Earlier v3 checkpoint: host-grounded sources and selection

27 October 2026. Confirmed schedules and up to eight recent source leads now
remain visible independently of Qwen. The host freezes exact dates, quotations
and direct issuer links; the model selects IDs. Source leads are literal
issuer/topic navigation, carry actual first-receipt/publication clocks and expire
48 hours after first receipt. Repeated capture cannot revive an identical old
lead. Reading status creates no model input, watch, inference or labels.

All four explicitly approved foreground calls completed: the v3 matching case
passed, both nonmatching cases failed, and the real eight-candidate packet stayed
private/diagnostic. No model qualification or watch was published. Both previous
native failures remain. Routine workers still require ten-minute idle and stop
for review on the failed contract. The persistent foreground receipt is spent;
repeating verify-now makes no fifth call. See
[operating result](../changes/2026-10-27-host-grounded-radar.md) and
[ADR0079](../adr/0079-host-grounded-radar-selection.md). Recognition, free-text
extraction and forecast quality remain separate claims; none is inferred from
an enabled schedule or a deterministic source lead.

The installation notes below describe the prior v1/v2 checkpoints. Their pending
native status is superseded by the recorded results above.

# Anticipatory radar â€” 27 October 2026

Owner authorized implementing the audited missing integration. This is an advisory
R12 slice, not a new active roadmap milestone or acceptance of P1 forecasting.

Extend the existing calendar, Hermes capture archive, curated cash-share catalog,
owned idle Ollama runner and Market AI page. Retain historical pilot receipts and
budgets. A separate radar account holds immutable scope snapshots, acquisition
attempts, daily model reservations, cited candidates, warning packets and reviews.

Recurring public collection runs at 08:00, 12:00 and 16:00 SAST while signed in,
maximum three attempts/day, 100 excerpts/attempt. It fetches synchronously with
zero inference, retains raw responses, source failures and deduplication counts.
No broker login or paid account acquisition is needed. Previously configured
NewsAPI remains optional; public Moneyweb/SENS are the base sources.

The existing curated issuer catalog supplies issuer names and sector membership,
frozen with actual receipt and code/catalog hash. Membership is a navigation map,
not proof that sector news affects every constituent. Macro/thematic items remain
context-only unless a retained source explicitly names an issuer. No invented
commodity/FX exposure mappings or precise dates for unscheduled news.

The small installed Qwen model retains its 3.5-GiB start margin, 1.5-GiB abort,
two CPU threads, no GPU/cloud/download, ten-minute idle and owned-process cleanup.
Before normal use, three hash-bound real-source schema/citation/abstention probes
must pass; failures stay spent. At most one daily source-discovery request follows,
with a bounded packet, immutable input cutoff and no automatic failed-call retry.
Model output is untrusted: exact quotes, issuer links and explicit future dates
are host-validated. Candidates remain unconfirmed watch items, never silently
confirmed SENS events. Prompt injection, unsupported issuers and dates are rejected.

Confirmed dates reuse calendar confirmation; add 48 hours alongside 168/24/2.
At 48/24 hours save the actual source packet and latest eligible model result or
an explicit pending/abstention status. Late registrations and passed deadlines
stay missed. Warning packets are never backdated. Read-only radar publication
shows source freshness, status, expiry, direct issuer/sector navigation and why
to watch. Revisions/cancellations suppress obsolete entries without erasing them.

Review records keep occurred/not-observed/incorrect-link outcomes separate from
model suggestions. Metrics report lead time, missed windows, expiry and adjudicated
false alarms with denominators; no self-labelled forecast or trading skill.

Acceptance: offline integration/time/citation/failure/replay tests, full safe suite,
protected checks, actual PostgreSQL idempotence and dashboard/API check; installed
Windows jobs read back with no end boundary. Native model qualification is reported
as passed or honestly pending idle, never inferred from a mock or an enabled task.

Sector-only themes also receive literal topic-navigation labels (for example gold
news under Mining) without assigning any affected share. Packet selection gives
issuer diversity first, then published sector-topic excerpts, then latest context.
This avoids unknown-publication-time SENS headings crowding out all sector news.

## Corrective qualification v2

The first real call ran successfully but failed its ambiguous array-output probe.
ADR0078 replaces that probe with typed decision/date/source/quote fields. A separate
three-case contract retains the original failure and binds every corrective attempt
and qualification pass. `scripts/anticipatory_radar.py qualify-register` freezes it
without inference; the existing hourly idle worker then runs its bounded cases.
Read-only status exposes its ID, version, budget and passed/failed counts, never
source packets or expected answers. At installation v2 is registered with zero
native checks completed. The dashboard distinguishes this from the old failure.
