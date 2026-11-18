# AI series status

Planning snapshot, 17 November 2026. Implementation has not started in this
planning turn. AI1 is ready for the dedicated implementation task.

| Item | Written | Unit-tested | Run on trading | Visible in UI |
| --- | --- | --- | --- | --- |
| Prior Llama task profile, commit b90765f | Yes | 124 focused + 25 Sasol checks | Pending unattended verification | Dashboard-path mismatch identified |
| AI0 roadmap and implementation prompts | Yes | Ten Markdown files and all local links verified | Not applicable | Dedicated AI task created |
| AI1 runtime integration and reporting | Partial implementation | 97 focused tests passed | Read-only API check passed; no eligible share event | Browser unavailable; activation pending |
| AI2 source-linked radar cards | Implemented | 185 focused checks and JS interaction harness pass | Read-only API check passed | Browser check and main-dashboard activation pending |
| AI3 event preparation | Implemented; acceptance partial | 99 focused Python tests and two JS harnesses passed | Read-only API checked against trading | DOM fixture passed; live browser acceptance pending |
| AI4 usefulness and outcome review | Partial implementation | 125 focused tests and JS harnesses passed | Read-only counts checked | Live browser and activation pending |
| AI5 unattended acceptance | Prompt ready | Pending | Pending | Pending |

## Evidence required at each checkpoint

Append milestone revision, changed files, commands/results, API identity and
runtime version, UI route/screenshot or DOM proof, actual record IDs, call counts,
unattended window observations, remaining conditions and next action. Keep this
file compact. Raw data, source bodies, logs and model responses stay under the
existing ignored runtime paths. Preserve earlier failure evidence.

## AI3 partial checkpoint — 18 November

Added a read-only projection joining confirmed events to existing warning and
preparation receipts, sidecars and saved model attempts. A proposed expectation
with invalid citations or only a date source is withheld by the projection;
historical receipts are unchanged. Share and macro expectation refreshes now
fail independently. Reads make zero model calls and have zero trading weight.

The trading API returned HTTP 200. SARB event e4699f27, CPI event 8dea1fd9
and retail event 01927101 each linked two saved packets and an ABSTAIN result.
The SARB and CPI 168h windows were missed before confirmation; their 24h
receipts were observed at 00:01:40 SAST on 18 November and 00:01:41 SAST
on 17 November respectively. CPI and retail date-only anchors have passed;
that does not establish the actual release outcome.

96 focused Python tests and the independent-panel and source-card JavaScript
harnesses passed. All nine frozen file Git hashes match the pre-change HEAD;
research_calendar.py has no diff. No browser acceptance has been performed.
Related sources are now shown on the event card, alongside saved packet data,
warning receipt IDs and source-input freshness. The instrument research panel
shows matching upcoming events and links to News & SENS. New macro proposals
must cite non-calendar evidence and include a weakening condition and unknowns;
older saved drafts retain their original fields and display missing values as
not recorded. Empty quotes are rejected. Existing budgets and gates remain.

A fresh read-only PostgreSQL API check returned HTTP 200 and zero model calls;
SARB, CPI and retail each still had two packets and ABSTAIN results. No current
matching news or SENS sources were returned for these three events. The 99
focused Python tests and JS fixture checks passed; all nine frozen files match
the starting Git revision. Browser inventory contains no browser window in
this remote session; live browser acceptance and activation remain open. AI3
is implemented but not fully accepted. Earlier
full-suite failures and AI1/AI2 runtime acceptance gaps remain open.

## AI4 partial checkpoint — 18 November

Added separate immutable operator-asserted usefulness reviews with explicit
verdicts, source/input identity, actual cutoff, model and prompt attribution
where known. Protected POST and read-only period counts use existing paper
records; review or read invokes no model or calendar operation. Frozen share
plans expose existing outcome state. Dashboard controls and an empty state are
written, but have not been checked in a live browser or loaded by the running
dashboard. Exact duplicate submissions reuse the same immutable record.

On localhost:5433/trading, read-only 30-day counts were six macro attempts,
six outputs, four abstentions, two failed or invalid, zero reviewed and zero
owner-usefulness denominator. No synthetic review was written to trading.
125 focused tests passed, including existing expectation, Hermes and frozen
guards, plus the JavaScript harnesses. AI4 remains partial: clocked later
source/price follow-up, citation and coverage denominators, bounded prompt
comparison, full fixture browser workflow and wider tests are outstanding.
AI5 has not started.

AI4 follow-up: added selectable periods, explicit citation/follow-up counts,
same-URL later source receipts with actual availability clocks, existing frozen
share outcome/reference data and request IDs for separate review actions with
retry deduplication. Same-URL follow-up is a lead for review, not proof that an
announcement is about the event. The latest focused AI4/expectation/Hermes/
price-context/frozen suite passed 135 tests. A read-only trading check found
six macro attempts, six outcomes (four abstained, two invalid/failed), zero
owner reviews, zero checked cited proposals and zero later same-URL receipts;
no model call or synthetic production review was made. AI4 remains partial:
the bounded prompt-version comparison, broader follow-up linking and full
fixture-browser acceptance are still outstanding.

## Dedicated implementation task

Created `AI — Local research integration and unattended operation` with thread
ID `01a1ea68-c3d4-77e2-ac7b-c934e36ec8df`, using a same-directory fork so the
existing local checkout and host context are available. The app returned no
saved projects from list_projects, so a fork retained the correct workspace.
The implementation handoff requests `gpt-6.1-terra` with low reasoning to match
the owner's Terra Light selection. START.md supplies the complete assignment.
The receiving task records actual implementation progress in this file.

## AI1 partial checkpoint — 17 November

The owner selected a 330-second Llama request timeout. The share worker now
passes its own 3.75 GiB/500 MiB/330-second profile without changing Qwen defaults.
The SENS bridge launches a separately locked AI supervisor with sequential macro
and share checks. The share child has a 390-second outer limit for startup and
cleanup. Existing task definitions were not changed. Status reports the latest
attempt and result and distinguishes the configured dashboard repository from
legacy research. Historical unresolved reservations remain unknown.

97 focused tests passed, including Sasol tests. Nine frozen hashes match HEAD,
and the research_calendar.py diff is empty. The dashboard blueprint API returned
HTTP 200 against localhost:5433/trading, with zero eligible share events,
zero reservations/results and zero model calls from the read. The previous
290-second supervised synthetic attempt timed out; a 330-second real unattended
request is not yet observed. The 480-second synthetic attempt passed in 309s.

Computer-use inventory returned no browsers and the in-app browser was unavailable.
Visual verification of the updated panel and actual detached-supervisor survival
under the SENS host remain pending. The running dashboard has not been restarted.
Separately verify child lifetime under actual Windows job containment and complete
AI1 acceptance before marking it complete. Legacy and trading budgets are separate.

The owner later requested progress while away from the desktop. Offline tests
now additionally simulate a request that reaches 245 seconds and verify that
concurrent AI supervisors cannot both hold the same dispatch lock. Both pass.
The collector login window timed out before the owner could access the desktop;
the Radar monitor remained running. The session recovery steps are documented
in `docs/strategy-radar/VIEWPOINT_SESSION_HANDOFF.md`.

## AI1/AI2 browser follow-up — 18 November

The owner requested no Llama run during development; no model test was made
and temporary memory conditions are not a model failure. A read-only Flask API
check using current source and localhost:5433/trading returned 0 eligible share
events, 0 reservations, 0 results and 0 model calls on read. The configured
profile is 3.75 GiB start, 500 MiB emergency, 330-second timeout and 600-second
idle. An unattended generation remains unverified; it was not rerun here.

The open live dashboard was inspected without restarting it or the collector.
News & SENS displayed retained SENS and SARB data, but its older backend still
reported a 7 GiB share threshold, lacked the event-preparation API, and the
SARB retained-source button returned HTML instead of JSON. These are version
mismatches, not evidence of a model run. The user's open OST and ViewPoint tabs
were left alone.

An isolated temporary localhost-only browser fixture using current code and a
read-only trading connection displayed the real SARB quote, official-sync hash,
preparation and retained SENS cards. The SARB source detail opened successfully,
and the SASOL source handoff selected SASOL research. Only the temporary
fixture server was stopped after validation. 159 focused radar, SENS and
frozen-guard tests and both JS harnesses passed without a real model call.
Activation of the updated backend and live UI verification remain pending a
separately coordinated dashboard reload. The isolated test did not change the
live frontend/backend mismatch.

## AI2 implementation checkpoint — 17 November

Source and SENS cards now expose retained-source details and a paged history,
actual available assessment/model clocks, catalogued instrument research
handoffs, safe HTTP(S) source links, and explicit missing data. Duplicate SENS
cards are suppressed by source ID. Confirmed calendar cards preserve date/time
precision and macro sidecar attribution. US macro cards are grouped under a
collapsed secondary section. Retained detail/history endpoints require the
existing operator access and do not fetch sources or invoke a model.

172 focused Python checks and the source-card JavaScript rendering harness
passed; all nine frozen implementation hashes matched HEAD. A Flask blueprint
test against localhost:5433/trading returned HTTP 200: 30 SENS cards, 8 source
leads, and confirmed retail, CPI and SARB events with sidecar labels and hashes.
History returned 100 records with a bounded-window indicator; a retained SENS
detail returned HTTP 200 and zero model calls.

No accessible Edge or in-app browser was available in this remote session. The
JavaScript harness verifies cards and unsafe links, but retained-source clicks,
pagination, instrument handoffs, desktop/narrow rendering and activation in
the running dashboard remain pending real browser verification.
The dashboard and collector were not restarted. AI1 unattended verification
also remains pending. This checkpoint is implemented with UI verification open,
not a claim of completed live acceptance.

## AI2 pagination and interaction follow-up — 18 November

Receipt-keyset paging now traverses batches larger than 500 records sharing a
timestamp and preserves a separate source-availability clock. Regressions cover
505 same-time SENS records, empty SENS and Hermes receipt windows, multiple
articles in one capture, and an older capture whose article became available
later. Eight consecutive API pages against localhost:5433/trading returned 800
distinct source/receipt pairs with zero model calls. Each individual database
query remains bounded; the cursor continues through supported receipts. A
malformed boundary lacking both a receipt identity and receipt time may still
report a truncated window without an advance cursor.

The JavaScript harness now invokes the source-detail, history/pagination and
instrument-handoff handlers using simulated dashboard controls. 185 focused
tests passed, and all nine frozen modules matched HEAD. The full safe runner
executed 2,209 tests and reported 4 failures, 22 errors and one skip. Most
errors arose because its socket block prevents Windows asyncio's local socket
pair and local OAuth test callbacks; subsequent OAuth tests hit an already
pending test authorization. Two old Hermes tests expect a SASOL-only state
name while HEAD returns the already-expanded SHARE name. Two MCP failures also
occurred under the runner's local-socket block. The log is retained at
`runtime/ai2-full-offline-check.log` and is excluded from Git.

The in-app browser was unavailable and the computer-use inventory exposed no
browser window. The actual desktop and narrow layouts, browser click flow and
main-dashboard activation remain unverified. No existing process or collector
was restarted. AI2 is implemented and API/harness verified; live UI acceptance
remains open until a browser is available and the running dashboard loads the
updated code.
