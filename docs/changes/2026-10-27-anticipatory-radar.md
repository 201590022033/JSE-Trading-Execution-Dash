# Anticipatory radar: installed integration and operating evidence

27 October 2026. This completes the authorized software/scheduling slice inside
R12. **Real model qualification and prospective radar accuracy remain pending.**
P1 return forecasting remains unqualified; this radar does not depend on passing it.

## What now runs

The existing public news scanner, Hermes archive and calendar are connected to a
separate advisory radar account and Market AI / News panel. The curated universe
is **18 issuers in nine sectors**. It includes Naspers, Sasol, banks, miners,
retailers and telecommunications issuers. Membership is frozen with its actual
receipt. Literal topic labels also route sector news (for example gold to Mining)
without inventing an affected share or a causal exposure.

The old four-date capture task now runs **daily at 08:00, 12:00 and 16:00 SAST**
while signed in. Windows readback confirms it is enabled and has no EndBoundary.
Each slot reserves before fetching, with at most three attempts/day, 100 returned
excerpts per attempt and no failed-slot retry. A synchronous scan replaces the
old cached dashboard fetch. Actual raw responses and source states are retained;
repeated captures cannot turn an old article into new evidence.

The first actual capture at **10:29:55 SAST** retained **25 articles**, with **23 new
article identities and two repeated identities**. Moneyweb and SENS were available;
NewsAPI is unconfigured. No additional login was needed. These are bounded feed
excerpts, not full publisher documents or complete JSE coverage. Sources with
unknown publication times keep that uncertainty.

A new hourly idle worker uses the installed **Qwen 2.5 1.5B** model with its exact
digest, two CPU threads, no GPU/cloud/download, 3.5-GiB free-memory start margin,
1.5-GiB abort and the existing owned process containment. It stops if user activity
returns. Three initial requests check date/quote copying and two abstentions against
a retained real SARB passage. They are qualification probes, not forecasting tests.
They run one per eligible worker invocation, followed by qualification registration
and normal daily discovery. Failures remain spent and require review.

**At delivery those native probes have not run.** Actual invocation returns
WAITING_FOR_10_MINUTES_IDLE with zero calls/reservations. The job is installed and
enabled; the UI honestly says it is awaiting first idle qualification. Installation
is not evidence that a real LLM-to-watch chain has already succeeded. The legacy
Llama runner/profile and its old reservations remain separate and unchanged.

## What the radar records

After qualification, one daily bounded source-discovery request may identify
future dated candidates or conditional watches over the next 48 hours. The host
checks exact source IDs/quotes, explicit issuer mentions, literal full dates and
actual cutoff/receipt clocks. Unsupported dates, issuer links, invented fields and
non-finite/duplicate-key JSON are rejected. Sector membership/topic navigation is
not evidence of price direction. The saved source packet selects issuer diversity,
then published sector-topic excerpts, then latest context, within eight sources
and a 12,000-character prompt/schema bound.

Dated machine candidates remain **unconfirmed**. An authenticated operator can
send a candidate to the existing calendar proposal/confirmation workflow. Undated
news watches retain a 48-hour expiry and never claim a precise SENS date. All watch
items preserve their initial evidence cutoff, failure condition and state.

The five-minute light clock saves **48-hour and 24-hour preparation packets** for
confirmed dates. They include actual lead time and current evidence, with a cited
model hypothesis or an explicit pending state. Late registration, cancellation,
revisions and expired windows remain distinguishable. The first native tick has
two MISSED_EVENT_PASSED packets for the old October event, not fabricated warnings.
There are currently zero model-generated watches, observations or accuracy claims.

The dashboard shows capture freshness, the nine-sector scope, pending model status,
watch expiry and observation counters. Its refresh/API are read-only. Authenticated
reviews can record occurrence, non-observation after expiry, or an incorrect issuer
link. Human assertions stay separate from model suggestions and price labels. Metrics
retain the reviewed denominator; unreviewed expiry is never auto-labelled a false
alarm. Missed-market-event rates outside the retained calendar are not measurable
from this bounded feed. No probability calibration or trading skill is claimed.

## Verification and an integration correction

**1,506 full offline tests pass**, including **22 new radar tests**; the final suite
runs in approximately 120 seconds. All **54 protected checks pass**, and JavaScript
syntax/Python compilation pass. Tests cover citations, future-date/issuer rejection,
cutoffs, exact replay, source deduplication, failed reservations, qualification,
model budgets, late windows, cancellation, expiry, review authentication and read-only
publication. These model tests use doubles; they are not native inference evidence.

Native PostgreSQL verification proves duplicate scope/tick idempotence and restart
durability. The real API returns HTTP 200 for both the radar and existing Sasol
refinement; the latter is OPERATIONAL_SHADOW_ONLY. The browser panel was checked
and a refresh-handler error was corrected before delivery.

Browser verification also exposed that the original calendar core is included in
the existing Sasol experiment's frozen implementation hashes. An initial attempt
to add 48h to that core paused the experiment. The core and its tests were restored
byte-for-byte; the extra preparation now lives in the radar extension. Native
verification confirms the original frozen definition matches again, and the UI
shows its operating state. One intermediate **MISSED_EVENT_PASSED** 48h calendar
receipt at 08:31:42 UTC remains in the append-only history. It is disclosed rather
than deleted or re-labelled. No experiment definition or old trial was rewritten.

## Operational limits and continuation

Keep the PC on and Windows signed in. The model must encounter ten minutes idle;
its first probes and discovery may take several hourly invocations. Check Market
AI / News for its qualification/result state. Failure receipts stay visible.

This is a starting watch universe and bounded public excerpt stream. Broader
publisher calendars, full SENS bodies, explicit verified commodity/FX exposure maps
and independently reviewed outcomes remain further coverage work. The present
radar can already publish useful uncertain sector themes without claiming direct
issuer impacts or waiting for a profitable trading model. No broker order, strategy
weight change, historical trial reset, cloud deployment or GitHub push occurred.

See [design](../research/ANTICIPATORY_RADAR.md), [ADR0077](../adr/0077-anticipatory-advisory-radar.md),
[native evidence](../evidence/anticipatory-radar-final-native-2026-10-27.json),
[installed jobs](../evidence/anticipatory-radar-jobs-2026-10-27.json),
[final tests](../evidence/anticipatory-radar-final-tests.json) and
[API evidence](../evidence/anticipatory-radar-api-2026-10-27.json).
