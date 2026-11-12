## Dashboard and milestone audit — 12 November 2026

- **Swing volume.** Radar 1.1.2 and Backtest Lab 1.3.1 use the latest completed
  session's volume divided by the median of the prior 20 sessions, strictly
  above 1.0. A zero median uses the mean ratio. Older strategy versions keep
  their original thresholds and `relative_volume20` remains the mean ratio.
  The restarted browser showed MTN on Radar 1.1.2. Its API volume check passed
  at 1.5759 times the median. Exact-version fill evidence is still open.
- **Strategy Radar M1–M11.** Recorded local acceptance stands, including
  M7–M10. This audit confirmed five visible choices and four retained watches
  outside the view. The dashboard and PostgreSQL responded in shadow mode.
  M11 returned eight freshness areas with zero errors and a PREPARED context
  packet. The browser showed both.
- **Strategy Radar M12.** Source preference is implemented and verified on the
  restarted API. The historical MTN sample is insufficient for a current
  intraday checklist or 30-minute monitor evaluation. Visible provenance for
  a real overlap is still open.
- **UIM.** UIM0–UIM2 are complete. UIM3 remains partial/deferred. UIM4 was
  closed at owner direction with its verification gap recorded. UIM5 remains
  partial. Its worker is running and reports SOURCE_UNAVAILABLE. A qualified
  unattended intraday feed, visible Windows banner, and Alpha Vantage JSE
  mapping/entitlement remain open. The repository contains Strategy Radar
  M7/M8 completion records and no separate UIM7/UIM8 briefs.
- **Verification.** The 172-test focused run passed, including the Swing,
  Backtest Lab, forward monitor, freshness, ViewPoint and mocked UIM5 paths.
  The first full offline run ran 2,122 tests with four failures, 21 errors and
  one skip. The refresh timer stub and profile-version assertion were corrected
  and passed in the focused rerun. The other 23 results came from the offline
  runner blocking Windows asyncio's socket pair. The affected mocked UIM5
  modules passed under direct unittest. A clean full offline run is pending.
- **Operational checks.** Startup took over a minute. An earlier Swing request
  exceeded 15 seconds. After restart the endpoint returned nine evaluations
  in about four seconds. The browser showed unavailable paper-account data
  and an unavailable Top 40 value. A fresh median-vs-mean performance replay
  was outside this dashboard audit.

## Strategy Radar M11 - freshness and prepared context — 12 November 2026

The user-authorized follow-up adds source-specific dashboard clocks and
manual/existing refresh actions. A local-only status endpoint reads retained
data, and the browser updates its snapshot once per minute while visible.
Bounded local context packets are initialized for existing choices and prepared on Top-5/manual-choice changes,
ViewPoint imports, retained news capture, and the existing SENS/calendar tick.
Research M5 remains active with its original scope. The dashboard was restarted
and the M11 freshness route now returns AVAILABLE with eight dashboard areas and
no endpoint errors; the live dashboard displays freshness rows and PREPARED
Radar context. M12 implements owner-approved ViewPoint preference for
overlapping retained intraday fields. The restarted API marked all 40 OHLCV
fields of eight historical MTN five-minute bars VIEWPOINT_PREFERRED. The browser
showed the five-minute view with five unknown rules. Visible provenance for an
actual source overlap remains open. See [Strategy Radar M11](../strategy-radar/milestones/M11.md) and
[M12](../strategy-radar/milestones/M12.md), ADR 0103/0104, and the M11/M12
change notes.

## Owner-authorized parallel execution — 12 November 2026

Research M5 remains active with its documented scope. Separately, the owner
asked to continue the narrowly scoped Strategy Radar M10 work in parallel; the
six-choice UI, archived-rank audit and owner-accepted ViewPoint CSV
normalization are implemented and verified locally.
This is a one-time sequencing exception. It does not complete, replace or
change the status of research M5. The supplied IRESS CSV is normalized for
local shadow research under documented owner-accepted conventions; no
unattended collector is enabled. See [Strategy Radar M10](../strategy-radar/milestones/M10.md)
and the [M10 checkpoint](../strategy-radar/CHECKPOINT.md).

## Strategy Radar M6 — completed locally, 11 November 2026

After a normal dashboard restart, health and PostgreSQL were available and the
swing endpoint returned 11 research-only evaluations with live execution
disabled. All six dashboard handoffs were exercised with typed context; Ask
prompt preview reconstructed the trace without a model call; retained news and
sector context loaded; technical selection and manual Costs behavior passed.
The selected VOD share had no exact match in the saved backtest run, so no
substitute or run was selected. Keyboard selection/focus, collapse/expand,
reversible pin/unpin and 390px touch emulation passed (49.9×44px target,
375px document width); physical touchscreen hardware was not available.

The final focused combined M6/issuer-news/sector-context/watch suite passed 35
tests, as did JavaScript syntax and `git diff --check`. The 2,091-test offline
suite reported 21 errors and 2 failures in UIM5 async/storage/search tests; its socket
guard blocks `socket.socketpair` used by asyncio. No M6 test failure was
identified. Daily Swing 1.1.1 has no exact-profile fill backtest; no forecast
skill or profitability claim is made. No model/provider generation, backtest,
broker action, notification or monitor setting change occurred. M6 acceptance
is complete locally with these limitations. See [M6 checkpoint](../strategy-radar/milestones/M6.md),
ADR 0102 and [change note](../changes/2026-11-11-swing-ema20-reclaim-window.md).

## Strategy Radar status reconciliation — 11 November 2026

The Strategy Radar M-series is separate from the UIM/research redesign.
Strategy Radar M6 was completed locally and committed/pushed as `bfec6fc`;
its post-restart dashboard verification is recorded in the M6 brief below.
Older entries saying M6 is pending are dated snapshots, not current status.
Strategy Radar M7, M8, M9 and M10 are completed locally. M10's six-choice
view and normalized ViewPoint CSV research path are complete under the owner's
one-time parallel authorization. Exact browser idle timeout and unattended
collection remain operational follow-ups, not barriers to manual use. See
[M10](../strategy-radar/milestones/M10.md).
No UIM6/UIM7/UIM8 briefs are implied by these M-series labels.

## Strategy Radar M7/M8 completed locally — 11 November 2026

The monitor/notification/startup suite passed 13 tests; one Windows shortcut test
was skipped to preserve an existing user shortcut. The existing monitor
configuration was already enabled (30-minute shadow profile, 900-second check,
desktop notifications enabled, sign-in startup disabled), but its lease had
expired and no worker process was running. The worker was relaunched with those
same settings. Actual dashboard status now reports `SOURCE_UNAVAILABLE`, no
error, zero alerts, and a live worker lease. An isolated hidden worker using a
temporary store checked an empty watchlist without a dashboard dependency and
exited cleanly on pause. A `TEST ONLY` toast was submitted; Windows event 3052
recorded delivery to Strategy Radar on session 1, but visible banner
presentation was not independently observed. The actual System view displayed
the status at 390px without horizontal page overflow. No source/provider,
model, paid request, broker action, or notification/startup preference was
changed. There are no qualified clocked intraday bars; the locally verified
software path therefore remains separate from an actual live/delayed feed.

M8 read-only dashboard measurements: 11 watches, Top 5 VOD/TFMJ/MTN/NTU/NPN;
one watch-endpoint response took 1.09 seconds. The five Top 5 histories ended
on 10 November and retained ShareData/Yahoo daily fields had 11 November
receipts; IRESS/OST had no retained fields. The intraday cache had two
unknown-clock ABSPJ records and zero verified bars. The runtime folder was
135,198,108 bytes; the worker's working set was about 4.0 MB. These are point
measurements, not service-level guarantees.

The focused M8 integration suite passed 47 tests. `scripts/run_tests.py` ran
2,091 tests in 160.493 seconds with 21 errors, 2 failures, and 1 skip. Errors
were confined to UIM5 async/MCP/OAuth/Qwen tests affected by the offline
socket guard and Windows Proactor `socketpair`; both failures were UIM5 tool
research API storage/stage results. No Strategy Radar test failed. JavaScript
syntax checks and `git diff --check` passed. Desktop and 390px browser checks,
isolated worker lifecycle, retained-bar alert replay, and OS-recorded TEST ONLY
toast delivery are recorded in [M7](../strategy-radar/milestones/M7.md) and
[M8](../strategy-radar/milestones/M8.md). No qualified intraday source, visible
toast presentation, or sign-out/sign-in lifecycle is claimed.

## Strategy Radar M9 completed locally — 11 November 2026

The explicit public ShareData MTN capture retained raw HTML
`b99c9ac275fed977829d321da7969866b6029b9a89facdc4e6a93007288ba472` and
ZAR 228.88. Provider session metadata and HTTP `Date` agreed with the 11
November SAST receipt date. The last-trade label was 16:17 SAST; actual local
receipt was 16:33:00.648 SAST. ShareData declared “15 mins delayed”; the
observed timestamp gap was about 16 minutes. The running radar displayed the
quote as DELAYED with its source/receipt times and minimum delay. Existing
quotes differed across source times and remain separately visible.

The swing view's 1,800-second freshness threshold classified this quote as
DELAYED; the 300-second default/intraday threshold classified it as STALE.
Capture is explicit, MTN-only, and limited to one request per five minutes.
It produces a delayed last-price observation, not OHLC, candles or live data.
It uses the public page without browser credentials and has no login session;
automatic collection, other-symbol qualification, unattended permissions and
continuous source availability remain unverified.

The live capture was persisted but its POST initially returned 503 because
Flask `jsonify` received positional and keyword data together. The endpoint
now returns the captured payload correctly, logs source/input failure classes,
and reports raw-file and SQLite retention errors separately. API tests cover
success, rate-limit no-call, source interruption/recovery, and retention
failures. The live
dashboard GET/browser display confirmed the persisted observation. Focused
ShareData quote tests: 7 passed; JavaScript syntax check passed. The latest
full safe suite ran 2,097 tests in 168.792 seconds: 21 UIM5 async/MCP/OAuth/
Qwen Windows Proactor socket-guard errors, one unrelated Release Inbox
concurrency error about an unsafe local store file, 2 UIM5 tool-research API
storage/stage failures, and 1 skip; no Strategy Radar failures.

No qualified unattended JSE intraday OHLC source or verified candle clocks
are available. M9 qualifies only a single public delayed MTN last-price
observation; it does not claim price-feed continuity or strategy performance.
At 16:51:59 SAST the sample source age reached 2,099 seconds and was correctly
marked STALE after the 1,800-second swing threshold. The next step is a
separate source/options brainstorm, not automatic polling. See [M9](../strategy-radar/milestones/M9.md)
and the [verification note](../changes/2026-11-11-strategy-radar-m9-sharedata-qualification.md).

## Historical M6 snapshot — post-restart performance fix pending reload, 7 November 2026

IRESS was observed online and the new radar was served, but concurrent evidence scans caused timeouts. The local fix avoids scans for unsupported profiles and loads evidence only on selection; 6 focused tests passed. The dashboard process still needed a normal restart to load the backend fix at this checkpoint. This pending state was superseded by the 11 November M6 completion. See [M6 checkpoint](../strategy-radar/milestones/M6.md).

## Historical M6 snapshot — implementation ready, verification pending, 7 November 2026

Exact-context desk, retained evidence matching, share-aware handoffs and fixture browser checks were in place. 1957 offline tests passed. Actual dashboard integration and real touch checks awaited restart; no model or broker call was made. This pending state was superseded by the 11 November M6 completion. See [M6 checkpoint](../strategy-radar/milestones/M6.md).

## Strategy Radar M6 — active / partial, 7 November 2026

Interactive radar and typed research handoffs are implemented locally; all 1954 offline tests passed. Exact context propagation into all legacy views, evidence-backed best/least-loss labels and full accessibility/shortcut checks remain. The running dashboard was not restarted. Existing dirty work remains uncommitted; M7 is not started. See [M6 checkpoint](../strategy-radar/milestones/M6.md).

## Strategy Radar M5 — completed locally, 7 November 2026

Manual cash-share and CFD scenarios reuse existing estimators and display costs, risk and assumptions; other products expose missing terms. OST field mapping is unverified and copying disabled. 1954 offline and 9 focused tests passed. Dashboard restart is needed. Prior dirty work remains uncommitted; M6 awaits explicit go. See [M5 checkpoint](../strategy-radar/milestones/M5.md).

## Strategy Radar M4 — completed locally, 6 November 2026

Five- and thirty-minute shadow profiles, source-aware traces, causal derived bars and a disclosed hypothetical next-bar baseline comparison are implemented. 1945 offline and 35 focused tests passed. Actual retained ViewPoint rows have unverified interval clocks and yield zero replay samples; full stop/target/exit simulation and source qualification remain separate. The running dashboard needs its normal restart for M4 endpoints. User changes remain uncommitted; M5 awaits explicit go. R12, P1 and earlier research statuses remain unchanged. See [M4 checkpoint](../strategy-radar/milestones/M4.md).

## Strategy Radar M3 — completed locally, 6 November 2026

Quote and intraday contracts, protected bounded cache, manual source input and explicit budget-gated API adapter are implemented. 1930 offline tests and 55 focused checks passed; two ViewPoint rows were retained as manual evidence with timestamp semantics unverified. No unattended provider feed is claimed. Existing collectors and running dashboard remain in place; the user will restart later. M4 awaits explicit go. R12, P1 and older research statuses remain unchanged. See [M3 checkpoint](../strategy-radar/milestones/M3.md).

## Strategy Radar M2 — completed locally, 6 November 2026

Top 5/pinned durable watches, field-level Zebra prewarm, bounded public refresh and local UI/API are complete. 1913 offline and 41 focused tests passed; actual Yahoo/ShareData captures succeeded for five current watches. OST/IRESS automation remains unverified; the existing dashboard process needs its normal restart to load the changes. Existing user work is preserved and uncommitted. M3 awaits explicit go; R12, P1 and earlier research statuses remain unchanged. See [M2 checkpoint](../strategy-radar/milestones/M2.md).

## Strategy Radar M1 — completed locally, 6 November 2026

Separate Strategy Radar series: inactive responsive shell, collapsible import panel, provenance-aware contracts and baseline/ADR are complete; 1905 offline tests, 24 focused tests and desktop/mobile browser checks passed. Existing uncommitted work preserved, no commit. M2 awaits explicit go. This does not change R12, P1 or prior research milestone statuses. See [M1 checkpoint](../strategy-radar/milestones/M1.md).

## Strategy Radar roadmap — prepared 6 November 2026

The user-approved radar, product-aware manual trade plan, data lifecycle and alerts are tracked in the separate [Strategy Radar roadmap](../strategy-radar/README.md), with [hierarchy](../strategy-radar/HIERARCHY.md). Strategy Radar M1–M9 are complete; the owner authorized M10 on 12 November 2026 for the six-choice view and IRESS intraday qualification. The owner also requested this bounded M10 work alongside research M5; that one-time exception leaves research M5's scope unchanged. Earlier research M5–M7, R12 and P1 retain their recorded status. Preserve existing uncommitted work and prior evidence.

## Research redesign: M6/M7 continuation — 6 November 2026

The 07:30 collector did run: public sources refreshed, while the legacy OST export stage reported expired data. After fresh IRESS captures, the forward monitor retained the 5 November BTI and SASOL observations; both frozen cases remain partial and have zero matured three-session outcomes. A separate Zebra-backed BTI/SASOL Lab replay completed even without a current OST export; the new fallback has not yet been verified in a later scheduled run. See `docs/changes/2026-11-06-0730-ingestion.md` and `docs/changes/2026-11-06-trade-tape-and-zebra-continuity.md`.

M7's retained target/exit comparison is visible in the restarted dashboard, and the source clocked context and descriptive peer work remain available. Share-cost scenarios and the trade-tape snapshot reader have been added locally; they require the dashboard to reload their new routes. Cash-share fee sensitivity is a fixed-fill calculation, not a full portfolio replay, and does not apply to CFDs or other products. M6 remains open for later forward outcomes and the next scheduled fallback; M7 remains open for broader product-aware iteration and feedback. The 6 November targeted tests should be used instead of assuming the earlier pre-ingestion status below is current.

## Research redesign: pre-ingestion M6/M7 cleanup — 6 November 2026

The daily forward step now has durable status, per-instrument error isolation and input-specific partial explanations. Family-specific box and pullback component cycles were added under the shared instrument budget; BTI and Sasol exploratory examples are recorded. The 07:30 task and later outcomes have not yet occurred. See `docs/changes/2026-11-06-m6-m7-pre-ingestion.md`.

## Research redesign: M6 daily hook and M7 FX/gold examples — 5 November 2026

The existing 07:30 local swing collector now invokes the forward monitor after source refresh; the next scheduled run has not yet been observed. A listed-NewGold component-learning cycle and a separate price-only USD/ZAR component study are retained, with no model calls. M6's later outcomes and M7's broader feedback and live visual verification remain open. See `docs/changes/2026-11-05-daily-forward-fx-gold.md`.

## Research redesign: M6 forward monitoring started — 5 November 2026

The frozen BTI/Sasol plan and its dependency hashes verify. The manual, read-only forward monitor retained the first 5 November cases, which remain partial because exact volume is unavailable, and exposes pending descriptive close outcomes. The registered engine now replays complete consecutive forward segments without compressing gaps. A separate after-close Zebra import admits the eight retained 5 November IRESS prices without changing prior receipts. M6 continuous forward evidence and M7 broader integration remain open. See `docs/changes/2026-11-05-m6-forward-monitor.md`.

## Research redesign: M5 cross-sector evaluation — 5 November 2026

BTI, FSR and ABSPJ now have matched swing and pullback context comparisons across the retained training and inner-validation windows. The filters produced mixed outcomes on very small samples; FSR and ABSPJ have no linked event records in these studies. M5 remains open for broader timely event evidence and later observations. See `docs/changes/2026-11-05-m5-cross-sector-evaluation.md`.

## Research redesign: M5 Sasol evidence timeline — 5 November 2026

Retained issuer documents, extracted source-quoted financial values, Zebra history, resources ETF, Brent and USD/ZAR now connect to Sasol trade cases and retrospective proxy-filter replays. A user-invoked research brief exposes the selected case without a model call. Sample sizes remain very small; capture timing is explicit and M5 remains open. See `docs/changes/2026-11-05-sasol-context-research.md`.

## Research redesign: M5 matched context replay — 5 November 2026

A price-only control and an event-context candidate now run through the same daily engine with retained source clocks and evidence. Sasol/BAT first runs were identical because no recent source was eligible; this is not evidence of improvement. A narrow source-quoted fundamental percentage adapter is available; richer factual coverage and prospectively available context remain open. See `docs/changes/2026-11-05-m5-matched-replay.md`. M5 remains open.

## Research redesign: M5 macro and proxy context cycle — 5 November 2026

Calendar-source macro leads and keyword-only fundamental tags join the retained SENS/Hermes archive. Eligible context can reach the training-only proposer, while later or unknown evidence remains an annotation. A USD/ZAR reference was captured and a labelled Sasol Brent/FX trade-subset comparison was retained. M5 remains open for a genuine matched context-dependent replay, structured fundamentals and prospective evidence. See `docs/changes/2026-11-05-m5-macro-proxy-cycle.md`.

## Research redesign: M5 source-context work started — 5 November 2026

Radar SENS and Hermes issuer-news revisions can be joined to research cases with publication, acquisition and receipt clocks; late or uncertain items remain descriptive and price-only work continues. First Sasol/BAT coverage audits and remaining work are recorded in `docs/changes/2026-11-05-m5-context-start.md`. M5 remains open.

## Research redesign: M4 local workflow implemented — 5 November 2026

The queue, recovery, training-only proposal cycle, sector grouping, interaction plan, source links and holdout ledger are implemented and tested; the live dashboard process needs a restart to load the latest read routes. One real model call and real instrument/sector examples are retained. The worker is explicitly started, not scheduled, and its results remain exploratory. See `docs/changes/2026-11-05-m4-end-to-end.md`. M5 context and prospective outcomes remain open.

## Research redesign: M4 component learning in progress — 5 November 2026

Paired component cycles, a training-only proposer interface, deterministic fallback and retained experiment records are implemented. Two real candidates per instrument were recorded in the latest namespace, alongside earlier prototype trials. M4 remains partial: global trial accounting, robust queued/model recovery, actual cloud verification, broader diagnostics, sector pooling, source lineage and protected holdout handling remain. See `docs/changes/2026-11-05-component-learning-progress.md`.

## Research redesign: M3 component engine implemented locally — 5 November 2026

Versioned component controls and exploratory NewGold/Sasol replays are available through the read-only Lab API. M4's automatic learning loop and M5's point-in-time event and fundamental context remain separate work. The running dashboard must be restarted to load the new endpoint. Details and test results: `docs/changes/2026-11-05-component-gold-research.md`. R12 remains ACTIVE/PARTIAL and P1 open.

## Research redesign: M2 completed locally — 5 November 2026

Dated benchmark mapping, per-session fallbacks, the three-sector replay and the technical and Lab views are connected. Missing historical sector membership is retained as an explicitly retrospective proxy rather than blocking the stock. See `docs/changes/2026-11-05-dated-sector-benchmarks.md`. M3 component-level experiments are next; R12 remains ACTIVE/PARTIAL and P1 open.

## Research redesign: M2 field-level flow integrated locally — 5 November 2026

The v2 Zebra field reader, selectable-segment multi-share replay and technical history view are connected. Retrospective BTI/SASOL replay and its source coverage are recorded in `docs/changes/2026-11-05-zebra-field-windows.md`. Sector proxies use current research classifications; independently dated historical memberships remain unavailable and are labelled. M3 component experiments are the next implementation step. R12 remains ACTIVE/PARTIAL and P1 remains open.

## Research redesign: M1 Top 5 completed locally — 5 November 2026

The owner prioritized availability-first Zebra flow, a functioning Top 5 and a component-level autonomous research loop. The starting-state inventory and hash-checked local data snapshot are recorded in `docs/changes/2026-11-05-research-starting-baseline.md`. M1's Zebra-backed Top 5 slice is complete locally; M2, field-level backtest and benchmark flow, is next. R12 remains the single ACTIVE/PARTIAL umbrella and P1 remains open. See `docs/changes/2026-11-05-zebra-top5-research.md`. Existing frozen plans, model budgets, uncommitted work and paper/live trading boundaries are preserved.
## Multi-stock zebra and session freshness — 30 October 2026

R12 remains ACTIVE/PARTIAL and P1 open. The research-only radar expands via
source-linked SENS codes and exact Yahoo equity metadata, with a verified BVT
mapping. BVT's IRESS/Yahoo close handover and a five-share lab replay are
available; BTI's two older source discrepancies are retained and disclosed
while its recent matched source history permits an exploratory handover. Local
source freshness now uses the reviewed 2026 JSE calendar and a separate HLC
research calculation can use OST observations without fabricated opens.
The 02:00 SAST availability convention, prospective plans and tighter paper
limits remain. See `docs/changes/2026-10-30-zebra-multistock-and-freshness.md`.

## Zebra and historical research handover — 30 October 2026

R12 remains ACTIVE/PARTIAL; P1 remains open. A verified research-panel handover
now exposes 8,472 source-labelled closes through 27 October without expiring the history.
The daily local collector also attempts bounded Yahoo captures for linked radar
issuers independently of OST freshness. Initial ABSPJ and IMPJ captures each
contained 250 completed closes through 28 October. The current worker and
prospective comparison contracts remain unchanged; automatic fusion, broader
issuer mapping and IRESS/OST automation are unfinished. See
`docs/changes/2026-10-30-zebra-radar-handover.md`.

## Backtest Lab — partial implementation, 29 October 2026

The new dashboard tab runs a clearly labelled synthetic demo from frozen local
replay output and exposes read-only strategy traces, decisions, trades, price
charts and an idle-gated advisory prompt. The real `local-swing-dataset-v3`
loader is not implemented: the current OST open fields and verified calendar
coverage are insufficient for the unchanged replay contract. Full acceptance
is not met; 1280/390px browser checks are pending and the unrestricted test
suite reported five failures and eight errors, including baseline-reproduced
canonical API failures. R12 remains ACTIVE/PARTIAL and P1 remains open. See
`docs/changes/2026-10-29-backtest-lab.md`.

## Daily public SENS discovery — 28 October 2026

The existing local capture slots now import bounded, replay-verified Moneyweb
and ShareData source leads from the separate research archive. The 16:00 run
imported 423 leads and 12 Moneyweb details; coverage is partial and ShareData
detail remains pending. IG's local Demo diagnostic was repaired, while
authentication and JSE entitlement remain unverified without credentials.
R12 remains ACTIVE/PARTIAL; P1 stays open. See
`docs/changes/2026-10-28-daily-public-sens.md` and ADR0091.

## Vague commentary and SENS detail — 28 October 2026

R12 remains ACTIVE/PARTIAL; P1 remains open. A narrow host-side check holds
generic questions for review instead of creating a new specific-event watch,
while retaining the Qwen answer and original source. The research repository
indexes direct SENS pages and prepares a separate governance feature family;
the registered Bidvest/BAT forecast continues to use its unchanged model.
No new model fit, Qwen call or trading action was made. See
[change note](../changes/2026-10-28-vague-headline-event-guard.md) and ADR0090.

## Source-reviewed outcomes and price context — 28 October 2026

R12 remains ACTIVE/PARTIAL and P1 open. The Israeli vote is recorded as a
retrospective assistant-reviewed timing error. A pre-decision Fed price-context
plan now binds independently archived 27 October IRESS Sasol and Satrix 40
captures; both later paired horizons are pending, and the ETF's public-source
close differs. No model forecast, learning improvement or F6 confirmation is
claimed. Next: source actual outcomes, capture later matching prices and freeze
a separately sourced prospective P1 candidate. See
[checkpoint](../changes/2026-10-28-event-outcome-price-context.md) and ADR0089.

## Individual event watches — 28 October 2026

The radar now splits recognizable multi-event headlines into separate, source-cited
watches and keeps dated split or single events active through their own dates.
The Israeli vote is a retrospective expired item; the US election remains active
through 3 November. Original watches, source clocks, model attempts and prior
expiry records remain intact. Later dates and conflicts retain their actual
review times; no Qwen call, model fit or human outcome was made. R12 remains
ACTIVE/PARTIAL; P1 remains open. Next: collect actual event outcomes and, if
pursuing price learning, freeze a prospective numerical hypothesis and comparator.
See `docs/changes/2026-10-28-individual-event-watches.md` and ADR0088.

## First prospective source review — 28 October 2026

R12 remains ACTIVE/PARTIAL; P1 remains open. The first watch review has four
assistant source assessments with actual publication and acquisition clocks.
One later report concerns the still-pending Fed decision; one election had
already ended before its watch, and the separate US election outlives that
watch. Qwen matches two of four previously seen assistant headline assessments.
There is no frozen prospective price prediction or later price outcome to
score. Next, review actual event and price outcomes and address multi-event
splitting and watch expiry. See
[review](../changes/2026-10-28-prospective-radar-review.md).

## Cited event reading and prospective watches — 28 October 2026

R12 remains the sole ACTIVE/PARTIAL milestone and P1 is open. The radar now
retains source-cited event suggestions, unlinked/headline-only leads, later
related source receipts and expiry. The first daily event parent has spent four
calls; three conditional watches include a flagged false positive and a
separate source-wording fallback. Eight retained examples matched six assistant
assessments, not independent forecast labels. Subsequent work must review the
actual later sources and continue P1 learning and evaluation without claiming
accuracy from this diagnostic. See [ADR0086](../adr/0086-cited-event-reading-and-follow-up.md).

## Individual radar rechecks and IRESS event alignment — 27 October 2026

Four current source misses all matched on exact individual rechecks; the original
pairs reproduced the misses. One separate wrong-event control still failed alone.
New daily parents preserve four pair calls and may add at most four idle-only
single rechecks for source-supported disagreements, retaining both responses.
The current review displays its four rechecks; the first new daily parent remains
pending. Source cards expose retained headlines, issuer/sector links, source and
unconfirmed mentioned dates. Nineteen diagnostic calls were separately registered;
no model forecast or training improvement is claimed. The separate research
workspace aligned 45 Sasol disclosures and 12 CPI releases to 600 IRESS sessions.
R12 stays ACTIVE/PARTIAL; P1 remains open. See ADR0085 and
`docs/changes/2026-10-27-source-rechecks-and-event-cards.md`.

## Boolean-only source screening — 27 October 2026

At the owner's request, the known errors were addressed without waiting for a
new day. The revised per-source protocol asks only true/false and derives source
type from retained host metadata. On the same development packet it matched the
frozen assistant assessment 7/8 versus 5/8 before; a different held-out packet
matched 6/8. One false positive and two false negatives remain. These small
assistant assessments are not independent accuracy or forecasting evidence.
A separate current-packet review returned 4/8 model matches; the four false
answers conflict with host-supported source links and remain visible as such.
The new version is selected for experimental annotations only, with the same
four-call daily budget and no source suppression. The old broad hold and today's
spent slot remain. R12 remains ACTIVE/PARTIAL and P1 is open. See
`docs/changes/2026-10-27-boolean-source-screening.md`, ADR0084 and
`docs/research/SOURCE_SPECIFIC_RADAR.md`.

## Source-specific batch radar — 27 October 2026

The new worker freezes up to eight source items and uses at most four two-item
calls under one daily parent. Model errors affect individual annotations only;
retained news and confirmed calendar leads remain visible. Two disjoint packets
produced 5/8 development and 6/8 held-out matches against preregistered
assistant assessments, with three false positives and two misses in total.
The path is enabled as an experimental source annotation, not a qualified
relevance model, forecast, watch generator or trading signal. The old broad
request hold and today's spent slot remain. The first real daily batch is
pending its next eligible idle date. 1,557 offline / 99 focused / 54 protected
checks passed; R12 remains ACTIVE/PARTIAL and P1 remains open. See
`docs/changes/2026-10-27-source-specific-batch-radar.md`, ADR0083 and
`docs/research/SOURCE_SPECIFIC_RADAR.md`.

## Request and packet-width comparison — 27 October 2026

The four approved local Qwen calls are complete. The existing broad request
selected both candidates in the two-item packet but 0/8 in the full packet;
the explicit Sasol AGM request selected the correct item at both widths. This
is one retained packet with assistant assessments, not independent accuracy
or forecasting evidence. The broad two-item case had no negative controls.
Earlier responses, the spent daily slot and the exact-request hold remain.
The separately documented next fix plans source-specific tasks in two-item batches,
per-item failure handling and a complete merged eight-item validation. No future
model calls were authorized by the completed comparison. R12 remains the sole
ACTIVE/PARTIAL milestone; P1 remains open. See
`docs/changes/2026-10-27-request-width-comparison.md`, ADR0082 and
`docs/research/REAL_SCREEN_BATCH_FIX_PLAN.md`.

## First real screening reviewed — 27 October 2026

The owner-approved one-call real packet returned 0/8 matches despite the 8/8
narrow event checks. A source assessment frozen before generation disagrees;
it is explicitly assistant review, not human ground truth or training labels.
The exact broad request/model is held pending correction; source collection,
calendar clocks and source leads continue. Source intake now excludes stale
headlines from current watches without deleting research history, reuses known
calendar references without duplicate watches, and checks each news item separately.
1,533 offline / 74 focused / 5 private spender tests and 54 protected checks pass.
The one extra call and all earlier budgets/receipts are preserved. A historical
Sasol calendar date discrepancy is flagged without rewriting frozen evidence.
R12 stays sole ACTIVE/PARTIAL; P1 open. Next: the proposed four-call request/width
comparison; no further inference is queued. See
`docs/changes/2026-10-27-first-real-screen-review.md` and ADR0081.

## Qwen relevance correction verified — 27 October 2026

The explicit boolean protocol passes all eight frozen native source-relevance
checks, including unrelated issuer, wrong event, unsupported facts and reversed
candidate order. Exactly eight newly approved foreground calls were used; the
same batch resumes after a memory wait and cannot make a ninth call. Earlier
six attempts and today's spent discovery slot remain. No model weights or
trading defaults changed. 1,526 full offline tests, 67 focused tests and 54
protected checks pass. The live local dashboard shows 8/8 checks, two confirmed
calendar events and eight source leads. Narrow relevance qualification is
established; broad news accuracy, forecasts and P1 acceptance remain open.
R12 stays sole ACTIVE/PARTIAL. See
`docs/changes/2026-10-27-qwen-boolean-relevance.md` and ADR0080.

## Source radar restored; Qwen selection unqualified — 27 October 2026

Confirmed calendar dates and recent retained source leads now appear independently
of failed model extraction. Native verification completed exactly four approved
foreground calls: one selection pass, two abstention failures, one private real
packet diagnostic. No model watch or qualification was published; both historical
failures remain. A repeat invocation makes no fifth call. Routine ten-minute
idle, two CPU threads and memory limits remain unchanged. Two sourced calendar
events and eight news leads are visible; 1,519 offline tests and 54 protected
checks pass. The Sasol paired definition remains intact. R12 stays the sole
ACTIVE/PARTIAL milestone; P1 remains open. See
`docs/changes/2026-10-27-host-grounded-radar.md` and ADR0079.

## IRESS 600-session target met — 27 October 2026

Owner authorized finishing the signed-in ViewPoint capture here. A native 645-row
SOL.JSE daily CSV now supplies 600 completed sessions, 4 June 2024–26 October 2026,
through the existing installer/collector and accepted local PostgreSQL ingress.
Live row excluded; all raw bytes and 64 earlier source/capture hashes preserved.
All five OST series remain separate, Open null. Prior 324-session IRESS overlap
has zero revisions; all 600 OST/IRESS closes agree, with H/L/volume differences
retained. 79 focused tests pass; readiness/alignment/history-target checks pass.
No paper worker/model fit/cloud upload or strategy gate change. R12 remains sole
ACTIVE/PARTIAL; P1 and radar native correction checks remain separate. See
`docs/changes/2026-10-27-iress-600-history-complete.md`.

## Radar citation correction — 27 October 2026

Owner authorized fixing the observed Qwen response failure. Typed named fields
replace the ambiguous string-array probe; exact date/source/quote checks remain.
The original failed generation is retained. Corrective v2 has one immutable
three-probe contract, with reservations and passes scoped to that contract.
1,510 offline tests and 54 protected checks pass. Native v2 validation is still
0/3, waiting for ten minutes idle; no corrected-model success or forecast skill
is claimed. Memory/profile/idle controls and daily discovery budget are unchanged.
R12 remains ACTIVE/PARTIAL; P1 remains open. See ADR0078 and
`docs/changes/2026-10-27-radar-citation-correction.md`.

## Anticipatory advisory radar — 27 October 2026

Owner authorized the first radar integration slice. The existing calendar and
Hermes source archive now feed a separate cited discovery/watch lane and the
Market AI / News radar panel. Recurring public captures run at 08:00/12:00/16:00
SAST; the first real capture retained 25 articles (23 new identities). Scope is
18 curated issuers across nine sectors. Literal sector-topic navigation also
supports macro/industry watches without inventing affected issuer links.

The small Qwen worker is installed with 3.5-GiB free-memory and ten-minute idle
requirements, owned-process cancellation and bounded real-source qualification.
Native qualification is still pending idle: no production discovery or forecast
accuracy is claimed. Daily discovery has a spent-on-reservation budget; failed
attempts remain visible. Confirmed dates get immutable 48h/24h radar preparation;
unconfirmed dates and unscheduled watches stay distinct. Read-only UI/API never
starts model work. R12 remains the sole ACTIVE/PARTIAL milestone; P1 stays open.

The original calendar core is frozen by the Sasol paired experiment and remains
byte-identical. Extra warning preparation lives in the radar extension. Native
verification confirms the paired definition matches and the operational UI is
restored. One intermediate missed 48h legacy receipt from browser verification
is retained honestly; no experiment definition or old attempt was rewritten.
See docs/research/ANTICIPATORY_RADAR.md, ADR0077 and the operating checkpoint.

## P1 conditional pilot — 21 October2026

Owner authorized P1; ViewPoint is currently unavailable. Independent research
completed a conditional pilot using14 source-clock leads and250 IRESS sessions.
16 engine attempts are recorded. The frozen candidate underperformed its baseline;
numerical result INCONCLUSIVE, P1 acceptance DATA_BLOCKED. Two model trials yielded
no supported candidates; Yahoo exact history remains quarantined.298 research
tests/54 protected checks pass. See [report](../research/P1_PILOT_2026_10_21.md).
No additional login needed now; no executing model/runtime/schedule change.
P1 qualification remains next; R12 stays sole ACTIVE/PARTIAL. Local checkpoint.

## R5b bounded refinement delivered for review — 21 October2026

Owner authorized R5b, commit and push. Independent research now coordinates finite
parent→training diagnosis→proposal→native campaign→decision→successor chains and
scoped lesson memory.278 research tests,21 synthetic engine attempts across three
generations and54 protected checks pass. See
[checkpoint](../research/R5B_REFINEMENT_2026_10_21.md).
No executing model, strategy, runtime or schedule change; no real accuracy or
accepted P1/release. P1 is next proposed; R3c is separate. R12 stays sole ACTIVE/PARTIAL.

## R5a language sensitivity delivered for review — 21 October2026

Owner authorized R5a. Independent research now fits training-only scoped language/
event sensitivity, freezes a JSON scorer and evaluates independent labels against
the current-score/context and constant baselines.252 research tests (31 new), five
synthetic studies and54 protected checks pass. See
[checkpoint](../research/R5A_LANGUAGE_SENSITIVITY_2026_10_21.md).
No real accuracy, accepted release or executing weight change. R5b is next; P1
remains later real-campaign work. R12 stays sole ACTIVE/PARTIAL. Local commits only.

## Reusable research intake delivered — 21 October2026

Owner requested recovery of the earlier multi-source workaround and a repeatable
pipeline. Independent research now reuses R2a SENS indexing and audited whole-source
IRESS/OST/Yahoo/IG export routes. Actual710-session Sasol repair matches the prior
hash;221 research tests and54 protected checks pass. See
[operating record](../research/RESEARCH_DATA_PIPELINE_2026_10_21.md).
Numerical exploration is available; qualified historical replay and P1 completion
remain separate. R12 stays sole ACTIVE/PARTIAL; no execution runtime/schedule change.

## R4b bounded campaigns delivered for review — 21 October2026

Owner authorized R4b and GitHub push. Independent research now persists finite
cross-engine attempts, shared-policy screening/native shortlist, chronological
purging, frozen one-shot confirmation, seen-label memory and cluster uncertainty.
See [checkpoint](../research/R4B_BOUNDED_CAMPAIGNS_2026_10_21.md).198 research tests,
three synthetic studies and54 protected checks pass. R12 stays sole ACTIVE/PARTIAL.
R5a/R5b and real discovery/data/time/cost evidence still gate P1. Read-only OST/
public intake is now authorized; private data stays local. No runtime adoption.
Earlier local-only/pending-R4b entries are historical. Exact push heads in task receipt.

## R4a metrics/outcome contracts delivered for review — 21 October 2026

Owner authorized R4a. Independent research now has complete daily portfolio
metrics, frozen numeric outcome contracts, matched baselines and bounded paired
descriptive uncertainty. See [checkpoint](../research/R4A_PORTFOLIO_OUTCOMES_2026_10_21.md).
Research171/protected54 pass. Illustrative thresholds only; no actual performance
or accepted release. Local checkpoint, no R4a push. Next daily card R4b; R3c
remains pending genuine intraday data. R5 and real discovery/data/time/cost still
gate P1. R12 stays sole ACTIVE/PARTIAL; runtime unchanged. Earlier entries historical.

## R3b component policies delivered for review — 21 October 2026

Owner authorized R3b. Independent research now has causal entry/exit/volume/
timing/initial-stop/risk interfaces and controlled comparisons. See
[checkpoint](../research/R3B_COMPONENT_POLICIES_2026_10_21.md). Research134 and
protected54 pass;9 synthetic hand-answer comparisons;7 exact R3a regressions.
Local checkpoint, no R3b push. Next daily card R4a metrics/outcome contracts;
R3c remains a separate pending genuine intraday/paired-market study. Actual P1
still needs R4/R5 and real discovery/data/time/cost qualification. R12 stays sole
ACTIVE/PARTIAL; runtime unchanged. Earlier entries below are historical.

## R3a cash lifecycle replay delivered for review — 21 October 2026

Owner authorized R3a. Independent research now has native Backtrader cash replay,
2–5-session holds, dated cost scenarios, splits, net dividends and complete
portfolio equity. See [checkpoint](../research/R3A_CASH_REPLAY_2026_10_21.md).
Research94/protected54 pass;11 synthetic independent cash proofs. Local checkpoint;
no R3a push. Next proposed card R3b; real discovery/data/time/cost qualification
and remaining R4/R5 still gate P1. R12 stays sole ACTIVE/PARTIAL; runtime unchanged.
Earlier entries below are historical checkpoints.

## R2b software delivered; real trial rejected — 21 October 2026

Owner authorized R2b and GitHub push. Research now has source-bound discovery,
local-model budget/journal, strict event validation and proposed episode handoff.
See [checkpoint](../research/R2B_DISCOVERY_2026_10_21.md). Research61 and protected54
pass. One real local-model candidate failed numeric validation; none promoted.
Empirical discovery qualification/P1 remain pending. R3a is proposed next code
card; stop after authorized push. R12 stays sole ACTIVE/PARTIAL; runtime unchanged.

## R2a source archive delivered for review — 21 October 2026

Owner authorized R2a and requested completion. The independent researcher now
archives/queries bounded saved public captures with provenance, persistent budgets,
dedup and replay. See [R2a checkpoint](../research/R2A_SOURCE_ARCHIVE_2026_10_21.md).
Research44 and execution protected54 checks pass. No new downloads/model calls,
runtime adoption or actual P1 campaign. R2b is proposed next; stop for review.
R12 remains sole ACTIVE/PARTIAL; execution code/runtime remain unchanged.

## R1 research foundation delivered for review — 20 October 2026

Owner authorized R1 after R0. The independent research app now implements the
dated sector/exposure/vehicle registry, causal snapshots and tiered data admission.
See [R1 checkpoint](../research/R1_FOUNDATION_2026_10_20.md). All 28 research tests
and 54 execution protected checks pass. Examples remain synthetic; no real P1
campaign or source/model work started. R2a is proposed next. Stop R1 for review;
R12 remains the sole ACTIVE/PARTIAL milestone and execution runtime is unchanged.

## R0-ENGINE delivered for review — 20 October 2026

Owner authorized the missing research qualification. The independent local
`jse-strategy-research` workspace now has pinned engines/shared-core, independent
hand answers, explicit capability refusals and a measured finite comparison.
See [R0 checkpoint](../research/R0_ENGINE_QUALIFICATION_2026_10_20.md).
Ten research tests and54 execution protected checks pass. Execution runtime is
unchanged; R12 remains sole ACTIVE/PARTIAL. Stop for R0 review; R1 is proposed
next. Actual P1 and real X3/X4 acceptance/adoption remain pending.

## X5 owner acceptance and P1 readiness — 20 October 2026

Owner accepted X5. Commit3af0f8c was pushed and verified equal to GitHub master.
P1 preflight found the separate research application/engine/campaign prerequisites
not delivered in the audited locations. See [readiness and next assignment](../research/P1_READINESS_2026_10_20.md).
R0-ENGINE is the next proposed bounded research task; no campaign or new ACTIVE
milestone was started. R12 remains the sole ACTIVE/PARTIAL milestone. Prior code
checkpoint entries below are historical; real X3/X4 adoption remains pending.

## X5 observed execution feedback — 20 October 2026, for review

Owner requested X5. Shared-core0.4.0 adds immutable observed feedback; an explicit
append-only outbox/receiver returns idempotent batch receipts and durable sender
checkpoints. Decision/no-setup/risk/order/fill/cost/exit/correction provenance is
retained with causal as-of availability. No automatic learning/activation occurs.
All examples are synthetic; operational capture and real X3/X4 release acceptance
remain pending. R12 remains the sole ACTIVE/PARTIAL milestone. See
[checkpoint](../changes/X5_EXECUTION_FEEDBACK_2026_10_20.md),
[protocol](../research/X5_EXECUTION_FEEDBACK.md),
[ADR0076](../adr/0076-observed-execution-feedback-round-trip.md).
All numbered X software slices are delivered for review; research/P1, P2
operational shakedown and U1 reporting remain separate. Stop for owner review.

## X4 inactive StrategyRelease evaluator — 20 October 2026, for review

Owner authorized X4 and a GitHub push. Shared-core0.3.0 adds immutable strategy,
component and exact mapping contracts without changing earlier v1 identities.
The explicit inactive adapter reuses the existing Swing policy and verifies
frozen full-result parity, exact capabilities and current-as-of source/admission
timing. All qualification examples are synthetic; real research release acceptance
and operational activation remain pending. R12 remains sole ACTIVE/PARTIAL.
See [checkpoint](../changes/X4_INACTIVE_STRATEGY_EVALUATOR_2026_10_20.md),
[protocol](../research/X4_INACTIVE_STRATEGY_EVALUATOR.md),
[ADR0075](../adr/0075-inactive-strategy-release-boundary.md).
X5 feedback is the only remaining numbered X card. Research/P1, P2 operational
shakedown and U1 reporting remain separate. Stop after the authorized GitHub push.

## X3 reviewed radar evaluator — 20 October 2026, for owner review

Owner requested X3. Software is delivered: bounded frozen-JSON evaluator,
explicit current-radar adapter, separate review/selection/rollback journal and
source-bound decision feedback. Synthetic same-snapshot and lifecycle tests pass.
No compatible real accepted research artifact was supplied: real-artifact review
and production adoption remain pending. R12 remains the sole ACTIVE/PARTIAL
milestone; legacy defaults/runtime remain unchanged. See
[checkpoint](../changes/X3_REVIEWED_RADAR_EVALUATOR_2026_10_20.md),
[protocol](../research/X3_REVIEWED_RADAR_EVALUATOR.md) and
[ADR0074](../adr/0074-reviewed-radar-release-evaluation.md).
Stop for owner review. X4 and X5 are the two remaining numbered execution cards;
research R/P1, P2 operational shakedown and U1 reporting are separate.

## X2 inactive release inbox — 20 October 2026, for owner review

Owner assigned X2 using the prepared handoff. R12 remains the sole ACTIVE/PARTIAL
milestone. The bounded explicit local importer validates complete packages and
support/evidence chains, retaining immutable inactive bytes/registry/acks in one
transaction. No runtime integration, active release, strategy/scorer/default or
service changes. See [checkpoint/verification](../changes/X2_INACTIVE_RELEASE_INBOX_2026_10_20.md)
and [ADR0073](../adr/0073-inactive-radar-package-inbox.md). Stop for owner review.
X3 accepted radar evaluation/adoption, strategy/SSF execution, UI and separate
research R0-ENGINE work have not started. Existing SSF/UI/rename backlog is retained.

## X1b pure legacy scorer — 20 October 2026, for owner review

20 October backlog-only addendum: [deferred execution to-dos](EXECUTION_BACKLOG.md)
record SSF pre-cash radar versus exact-product readiness and later owner-selected
GitHub interactive UI assessment. Existing work/order is preserved; no card starts.

Naming completion: the canonical checkout is
`C:/Users/Deon/Documents/GitHub/JSE-Trading-Execution-Dash`. The former
`trading-system-complete` path is a compatibility junction preserving nine task
references and virtualenv launchers, not a duplicate. See [completed rename record](EXECUTION_BACKLOG.md#completed-local-folder-rename--jse-trading-execution-dash).
The planning receipt reports authorized restart and HTTP 200 verification; this
documentation update performs no restart or further milestone work. Railway is unchanged.

Owner requested continuation after X1a. R12 remains the sole ACTIVE/PARTIAL
milestone. X1b provides shared-core 0.2.0 and a pure legacy-news-v1 scorer with
fixed-versus-assessed provenance, source lineage and pinned old/new fixtures.
The running analyzer, issuer/source guards, current scores and strategy defaults
are unchanged; X1a schemas/identities remain v1. See [checkpoint and verification](../changes/X1B_PURE_LEGACY_NEWS_2026_10_20.md)
and [ADR0072](../adr/0072-pure-legacy-news-scorer.md). Stop for owner review.
X2 inactive release inbox/registry/acknowledgements is proposed only; no runtime
adoption, learned weights or UI is started. Earlier checkpoints remain historical.

## X1a shared contracts — 20 October 2026, for owner review

R12 remains the sole ACTIVE/PARTIAL milestone. X1a is a bounded shared-contract
continuation: standalone jse-intelligence-core 0.1.0 with immutable SectorScope,
EvidenceReference and RadarReleaseManifest v1, strict schemas and offline fixed
oracles. All runtime/scoring/default paths remain unchanged. This checkpoint
does not complete R12 or the two-app platform. See [verification and handoff](../changes/X1A_SHARED_CONTRACTS_2026_10_20.md)
and [ADR0071](../adr/0071-shared-intelligence-contract-boundary.md). Stop for owner
review; X1b legacy scorer characterization/extraction remains proposed only.

## Operational Sasol paired refinement — 20 October 2026

The fixed baseline/candidate numerical shadow loop is implemented and active on real local source data. One change only: relative-volume threshold>1.2 versus>1.0; other1.1/1.2 rules fixed,3-observed-session horizon. The existing five-minute clock records controls, paired outcomes and comparative reviews. Native:1episode, bothNO_SETUP,0/20informative pairs; no further software prerequisite to collecting this experiment. Source dates/actual receipts, whole feature dependencies, executable hashes and revision exclusions are frozen; independent source/time and integration reviews passed.1355safe tests/54protected checks pass; dashboard verified. This is sampled-path exploratory numerical research with assumed costs, no model training, promotion or Live execution. R12 remains the sole ACTIVE/PARTIAL milestone for broader news/historical/execution evidence. See [operating record](../research/SASOL_PAIRED_REFINEMENT_2026_10_20.md) and ADR0070. Earlier checkpoints below remain historical.

## Evidence-bound learning coordinator — 20 October 2026

R12 remains the sole ACTIVE/PARTIAL milestone. The existing light clock now records idempotent weekly/evidence-triggered training reviews and source-linked lesson memory, with separate news/Swing acceptance checks. Heldout labels do not enter adaptive memory; prior lessons cannot become news citations. The older Swing validator now enforces one changed parameter. Native PostgreSQL shows1review/0lessons/0adjudicated targets, correctly WAITING. The21–28October frozen protocol and four acquisition attempts remain unchanged. A calibrated Qwen actual-source trial is queued behind10-minute idle/3.5GiB gates; production llama3 remains unchanged.1330safe tests/54protected checks pass. No executable candidate, learned weights, source unpause or trading promotion is claimed. See [operating record](../research/HERMES_COORDINATOR_2026_10_20.md) and ADR0069.

## Prospective review and outcome software — 20 October 2026

R12 remains the sole ACTIVE/PARTIAL milestone. Separate immutable as-of references and future observed-session gross price outcomes are implemented; no real hypothesis outcomes exist yet. Protected blinded news review, distinct human adjudication and preregistered future-cohort evaluation are wired into Market AI / News. Actual corpus:79 articles/1422 article-share questions,0 human labels. The21–28October future plan and four bounded idle-only capture attempts (21/23/26/27October08:00SAST) are registered; missed runs remain missing. Registered cash-share IRESS numerical routing is generalized without expanding the Sasol-only configured universe. Explicit duplicate-row transformation retains original/derived hashes and survives v3 ingest; native SQL preview consumes IRESS Open R264.08 through16 October, with OST Opens still missing. R10:8 captures,0 revisions,5/4/3 clean and3/4/5 pending at3/4/5sessions. One actual pinned qwen calibration passes with1.23GiB sampled owned memory; production llama3/7GiB profile remains unchanged. 1313 safe tests and independent source/model reconciliation pass; see [operating record](../research/PROSPECTIVE_LEARNING_COMPLETION_2026_10_20.md) and ADR0068. Human/future evidence, B5 source definitions and execution requirements remain pending; Live remains disabled. Earlier checkpoints below remain historical.

## Cited expectations and daily import routine — 19 October 2026

R12 remains the sole ACTIVE/PARTIAL milestone. Source-bound local Ollama draft preparation, strict citation/issuer/numerical checks and explicit operator freeze are implemented; outcome scoring and learned weights remain pending. The hourly idle task is enabled with two CPU threads, owned-process cancellation and a 7 GiB free-RAM start gate. Current free RAM is about 4 GiB: actual inference is waiting, with zero new model calls. A weekday08:00SAST internal-calendar routine and persistent red import button provide a copyable broker-login/capture prompt. Published Top5 changes queue source/evidence requests and preserve prior candidates; the actual fresh universe is still Sasol-only, the ranking is stale, and eight pilot/context requests exist. Five-share price-row planning is1.92MB, distinct from109MB runtime/4.66GB models and raw/news/backup growth. Browser/API/native clock verification, 1207 safe tests and 54 protected artifacts pass. Existing weekly source pause was restored after an earlier explicit source-toggle POST; source writes now require operator authority and strict boolean input. No B5/AI/execution promotion. See [operating record](../research/SOURCED_EXPECTATIONS_AND_DAILY_IMPORTS.md) and ADR0067.

## Internal early-warning calendar and news testing — 19 October 2026

R12 remains ACTIVE/PARTIAL. Market AI / News now shows a source-bound research calendar with separately confirmed dates, optional frozen expectations and append-only warning/acknowledgement records. The light local five-minute clock runs while signed in, without model/provider/paper calls; heavy work retains idle gating. Three official date-only events are installed: Sasol quarterly22Oct, AGM13Nov and SARB19Nov. Actual sources/receipts, native PostgreSQL restart/idempotence and Windows taskresult0 are verified. A late seven-day Sasol window is marked missed. Fresh public-feed capture retains25articles, expanding the biased review corpus to27articles/486pairs, still0labels/noholdout/learnedweights.147focused/1115fullsafe/54protected checks pass; browser verified. Next is the prospective prediction/trigger/outcome radar, not yet an active news-to-price learning loop. Weekly source remains paused; B5/AI/execution gates unchanged. See [calendar operating and next-learning record](../research/RESEARCH_EARLY_WARNING_CALENDAR.md) and ADR0066.

## Local Hermes evidence foundation — 16 October 2026

R12 remains the sole ACTIVE/PARTIAL milestone. The owner-requested local Hermes first slice now has durable scientific experiment storage, a hash-bound retained-excerpt review corpus, blinded human label queue/import, descriptive frozen-guard evaluation and a read-only dashboard summary. Native PostgreSQL restart/idempotence/exclusive-lock proof passes. Actual first run: two retained articles, 36 article/share examples, zero reviewed labels, one DRAFT experiment; INCONCLUSIVE, no learned weights or model calls. Future weekly ingress preserves bounded normalized supplied articles including zero-case scans; legacy missing denominators stay explicit. Full safe suite:1058 pass; final focused suite:91 pass;54 protected checks pass. No source unpause, new supervisor schedule, B5/historical AI admission or execution change. Next: prospective denominator, independent adjudicated labels and grouped chronological holdout before evaluating a candidate or scheduling either Hermes supervisor. See [local Hermes operating record](../research/LOCAL_HERMES_FOUNDATION.md) and ADR0065.

## Current status — L1 completed; R12 ACTIVE/PARTIAL, 15 October 2026

Owner-authorized fresh local lineage is operational: isolated PostgreSQL18, shared dashboard/worker, idle-only tasks, duplicate-cycle verification and27-table backup/restore parity.1012offline tests and54protected checks pass. Railway web/worker sources disconnected and cron removed; original inactive volume retained. No hosted history restored, old decisions changed or AI/execution gates relaxed. R12 resumes as the sole ACTIVE milestone; weekly source stays paused. See [local operating guide](../research/LOCAL_PC_OPERATING_GUIDE.md) and [Hermes plan](../research/HERMES_IMPLEMENTATION_PLAN.md). Earlier paragraphs below are historical checkpoints.

## L1 local PC migration — original activation checkpoint, 15 October 2026

Owner explicitly authorized migration and agent work after reviewing the local plan. L1 is the sole ACTIVE milestone. R12 is DEFERRED/PARTIAL at owner reprioritization, not accepted as a working news-learning system; its source pause and existing gates remain. L1 orders hosted data recovery and verified restore before local worker activation or Railway retirement. Source/data, runtime and independent acceptance agents are assigned; no historical record or strategy is reclassified. See ADR0064 and LOCAL_PC_MIGRATION_PLAN.

## Final R10 capture and local migration planning — 15 October 2026

Six scheduled IRESS captures are preserved; final14 October reminder deleted. A separately dated15 October seventh capture restores benchmark alignment through14 October. Open R259.05 and numerical preview AVAILABLE; zero revisions,4/3/2clean and 3/4/5pending price-only observations at3/4/5sessions.33 focused tests/54 protected checks pass. No B5/historical AI/execution promotion. Owner selected future PC operation: [restore-first migration and two learning-loop plan](../research/LOCAL_PC_MIGRATION_PLAN.md) is prepared, not implemented. Railway backup/restore remains the first cutover dependency. No cloud resources removed; R12 remains ACTIVE/PARTIAL. See [final capture record](../research/R10_CAPTURE_FINAL_2026_10_15.md).

## 13 October operating continuation

R10 scheduled capture5/6 completed locally through12 October: separate IRESS Sasol OHLCV and native OST Sasol/Top40 exports retained with actual acquisition/hash. Five immutable IRESS captures have zero revisions; cohorts3/4/5 sessions now2/1/0 clean and3/4/5 pending. Four later observed sessions meet the descriptive readiness counter only. Numerical preview AVAILABLE, IRESS Open R246.05. Today's calendar reminder deleted;14 October remains. Railway upload still404; validated local snapshot retained.33 focused tests and independent integer comparison pass. No admission, AI model, strategy, execution or weekly-source activation change. See [13 October record](../research/R10_CAPTURE_2026_10_13.md). R12 remains ACTIVE/PARTIAL.

## R12 relevance guard continuation — 12 October 2026

R12 remains ACTIVE/PARTIAL. Weekly model proposals now pass the same versioned issuer applicability guard locally and at authenticated ingress: every cited article must explicitly name every proposed issuer. Unmatched/indirect links are retained with reasons, zero boost and no historical samples. Broad sector terms, model descriptions and bare tickers cannot establish applicability. Clicks requires its unambiguous full catalog name. Older frozen scans remain unchanged; unchecked or failing legacy cases are excluded from new historical screens.

The dashboard exposes bounded, deduplicated rejection/unchecked counts and an advisory next experiment. This is an error-review foundation, not model training or a completed Hermes loop. No executable Hermes agent exists; historical M35 remains a proposal. A future learning cycle needs independent relevance labels, reviewed exposure mappings, chronological holdout evaluation, outcome/cost controls and experiment-registry proposals. No automatic model/rule/weight promotion is implemented. The weekly source remains paused pending runtime semantic acceptance; Railway recovery remains with the owner. B5 and execution gates remain unchanged.

## R12 acceptance — PARTIAL, 12 October 2026

Local software integration, capture 4/6 and calendar removal are verified. The CPU-bounded Ollama retry completed, but its two instrument links (Pepkor→CFR; wheat→CLS) lack supporting evidence. Independent review rejects usable-trigger acceptance. The local weekly research source is paused as reviewer-approved containment until applicability validation is fixed; other news remains active. Both proposals remain source-review-required with zero attention boost and no trading effect; a prominent operator audit records the rejected links. Full weekly trigger evaluation and verified issuer/cross-asset mapping remain pending. R12 stays active; no next milestone is started. Railway upload awaits the owner’s subscription recovery. 989 safe tests and 54 protected checks pass.

## R12 weekly context comparison — ACTIVE, 12 October 2026

Extend existing derived weekly-news research with prior-receipt context and explicit claim audit. Complete local capture 4/6; hosted upload blocked by removed Railway deployments. Preserve all B5, trading and provenance gates.

# Current milestone — R11 IRESS numerical Open routing

9 October operating continuation completed: calendar capture 3/6 and separate native OST Sasol/STX40 refresh uploaded; current local/hosted numerical preview AVAILABLE through 8 October, IRESS Open R243.63 and ATR14 9.0474. Three immutable IRESS captures have zero revisions and 0 clean/3 pending at each horizon. Independently reviewed R9 readiness-counter correction now reports two later observed sessions, still not ready. Dated one-CFD statement/fill/financing evidence is reconciled locally, current account tariffs observed, and private financial files remain offline. No trade action, admission change, forced learning cycle or schedule change. 983 safe tests/54 protected checks pass. See [9 October record](../research/R10_CAPTURE_2026_10_09.md). R11 remains complete; B5/historical AI/execution requirements remain separate.

R11 NUMERICAL INTEGRATION COMPLETED, 8 October 2026. Three independent source/pipeline/reviewer investigations confirmed OST has no native Open and the v3 cutover disconnected the already captured whole IRESS chart. A separate raw-bound, fresh Sasol IRESS chart now survives v3 collection/normalization/storage/upload and supplies numerical technical shadow research. Canonical OST remains intact. Day-two capture has 536 completed bars through 7 October, no missing Opens and zero overlapping revisions; first capture is unchanged. A fresh OST STX40 benchmark aligns on 7 October. Local and hosted preview AVAILABLE; Open R237.30 and ATR14 8.7518. R10 has two captures and zero clean/two pending at each horizon. Exact-cent audit exposes 14 H/L and nine volume discrepancy dates across 534 overlaps; zero close differences. 38 focused/980 safe tests and 54 protected checks pass. Successful web/worker deployments and normal upload verified; hosted source hash/acquisition preserved, frozen decisions unchanged, next worker 9 October 08:00 SAST with no forced cycle. Independent reviewer accepted closure. See [R11 record](../research/IRESS_OPEN_ROUTING_R11.md) and ADR 0061. Cost investigation remains partial: a supposedly delayed CFD link automatically deducted 19c from the quotes bank, disclosed and closed with no order; reviewer stopped further authenticated cost navigation. Dated account tariff/actual charges remain pending. B5/historical AI/execution gates unchanged. No following milestone is active.

## Prior R10 record

R10 completed locally, 6 October 2026. The local onboarding status now computes 3/4/5 observed-session price-only shadow cohorts from dated OST or IRESS captures. It uses only the newest completed session in each capture as an anchor, requires a later capture for each exit, keeps providers separate, and excludes revised endpoints. It reports sample and pending counts, assumed 10 bps round-trip net returns, and unresolved calendar/action definitions. With zero actual capture files at implementation time, there are no real samples or return claims. Verification: 970 safe tests and 54/54 protected checks pass. See [R10 record](../research/PROSPECTIVE_PRICE_OUTCOMES_R10.md) and ADR 0060. Historical B5/AI admission, strategy promotion and live execution remain unchanged. No following milestone is active.

## Prior R9 record

R9 completed locally, 6 October 2026. Each newly imported OST or IRESS export now creates an immutable, provider-specific capture containing its actual acquisition timestamp, raw-source hash and validated daily bars. The local onboarding status reports captures, subsequently observed sessions and revisions. Old imported histories are not relabelled as historical point-in-time observations. Outcomes require later captured sessions; no outcome or performance claim is made from today's baseline. Verification: 969 safe tests and 54/54 protected checks pass. See [R9 research record](../research/PROSPECTIVE_PRICE_EVIDENCE_R9.md) and ADR 0059.

R8's unresolved price/volume definitions and B5 PARTIAL_CLOSED status remain in force. Historical AI admission and live execution remain blocked. This milestone does not depend on a bank reply. No following milestone is active.

## Prior R8 record

R8 EVIDENCE AUDIT COMPLETED; HISTORICAL SOURCE PROMOTION BLOCKED, 6 October 2026. Renewed OST access verified a dated Sasol 200-cent ex-dividend example. The owner's signed-in IRESS chart subsequently supplied a separate 263-session daily OHLCV capture spanning that event: 263/263 OST closes match, and all overlapping HLCV matches for 11–15 March 2024. The older raw capture and audit are retained locally without replacing the current Sasol candidate. Standard Bank's ViewPoint charting guide and the visible feeds still do not define raw/adjusted prices, volume eligibility, corrections or historical as-of availability. No historical AI/B5 gate changed; broker launch terms were not accepted. Full safe verification passed 968 tests and protected checks passed 54/54 before this docs/evidence-only continuation. See [R8 evidence](../research/PRICE_SOURCE_SEMANTICS_R8.md) and ADR 0058. No following milestone is active.

# R7 ViewPoint whole-source verification

R7 COMPLETED WITH NO SOURCE PROMOTION, 6 October 2026. Signed-in ViewPoint exposed complete daily OHLCV tables for Sasol, STX40, STXFIN, STXRES and STXIND. Four new sector candidates were captured and registered locally, 250 completed sessions each through 5 October. All five candidate histories match OST on 250/250 overlapping closes; their high/low and volume discrepancies remain visible. The local parser accepts ViewPoint's Copy CSV timestamp format and excludes the live session. Chart controls and available Iress documentation did not establish corporate-action adjustment, volume eligibility, revisions or historical as-of availability. OST stays primary, all IRESS candidates stay local, and B5/historical AI admission remains closed. The full safe suite passed 968 tests; protected verification passed 54/54. See [R7 evidence](../research/MULTI_SOURCE_PRICE_RESOLUTION.md#r7-viewpoint-check--6-october-2026) and ADR 0057. No following milestone is active.

# R6 multi-source price resolution

R6 COMPLETED, 6 October 2026. The local dashboard and daily collector automatically audit complete-source alternatives alongside the OST primary JSE research feed. The earlier ViewPoint/IRESS Sasol table is registered as a separate 250-bar OHLCV candidate with 250/250 OST close agreement; saved Yahoo histories are checked for invalid OHLC without fallback. Every registered stock gets a next source action, and the dashboard accepts future exact-identity IRESS daily exports locally. ShareData and JSE remain explicit access/format routes; SharePoint is optional storage. No cross-provider bar fields are mixed, no alternative is uploaded or promoted, and historical AI/B5 source-semantics gates remain in place. All 967 safe tests and 54 protected checks pass. See [R6 operating record](../research/MULTI_SOURCE_PRICE_RESOLUTION.md) and ADR 0056.

# R5 Standard Bank primary onboarding

R5 COMPLETED, 6 October 2026. Standard Bank OST is the primary JSE research source with no Yahoo fallback in that lane. The owner signs into OST independently; a bounded, credential-free local import accepts its native HTML-table `.xls` exports and CSV, maps each to an exact registered instrument, hashes the raw bytes and uploads a fresh v3 snapshot through the existing collector. Six series are installed in local and Railway storage: Sasol, Naspers, STX40 and all three sector ETFs. The other 16 registered candidates wait for exports. Dashboard coverage reports actual sessions, missing opens, HLC errors and freshness. Historical AI evaluation remains gated by unverified source/action/volume/availability semantics. Frozen records and strategy rules remain unchanged. Gold/USDZAR need separate source/product contracts; B5 remains PARTIAL_CLOSED. See [operating record](../research/OST_PRIMARY_ONBOARDING.md) and ADR 0055.

# Current milestone - R4 supplemental research integration

R4 COMPLETED, 6 October 2026. Provenance-preserving supplements are installed locally and accepted in Railway PostgreSQL: 250 IRESS Sasol OHLCV bars and 600 OST STX40 benchmark bars through 5 October. Current Sasol numerical preview is AVAILABLE. The original 21 canonical charts, frozen decisions, accounting and historical AI evaluation remain unchanged. Source/action/volume/availability semantics remain unverified and B5 remains PARTIAL_CLOSED with real-data admission false. All 950 safe tests (87.733s), 54 protected checks, JavaScript syntax checks, Windows background-launch verification and visible dashboard review passed. Final web and worker deployments are successful; local and hosted health/overview return HTTP 200. Existing next scheduled worker: 7 October at 08:00 SAST; no manual worker/model cycle was forced. Outcomes remain 25 pending / zero matured per horizon. Genuine fresh exports are required; acquisition receipts expire after four days. No following milestone is active. See [integration record](../research/SUPPLEMENTAL_RESEARCH_INTEGRATION.md).

# Current milestone — R3 broker-source continuation

R3 BROKER-SOURCE CONTINUATION COMPLETED LOCALLY, 6 October 2026. Renewed owner login enabled capture of 2,000 displayed OST STX40 rows and 2,000 SOL rows. Completed STX40 5 October close R102.27 resolves offline alignment: the separate IRESS Sasol + OST benchmark diagnostic now has AVAILABLE numerical technical inputs. Missing benchmark opens and six retained HLC inconsistencies stay explicit; no feed blend or cloud upload. Fresh OST confirms 250/250 Sasol closes, 247/250 highs/lows and 248/250 volumes. Remaining source-definition/provenance gates are documented. 52 focused tests, 940 full safe tests (89.733s) and 54 protected checks passed. Live labels remain 25 pending / zero matured per horizon. B5 remains PARTIAL_CLOSED, source admission/integration remains outstanding; no next milestone active.

# Current milestone — R3 data readiness audit

R3 DATA READINESS AUDIT COMPLETED LOCALLY, 6 October 2026. Operating path verified; 876 invalid OHLC rows across 21 saved charts identified. Recovered 250 valid single-source IRESS Sasol bars through 5 October, with 249 matching overlapping closes and valid alternatives for all 19 damaged Sasol dates. Separate numerical snapshot now calculates ATR/RSI/structure but remains partial on missing 5 October STX40 alignment. All overlapping volumes differ, so recovery is offline only, with hashes and explicit RAW/action/volume/availability gates. Live labels remain genuinely pending: 25 / zero matured per horizon. Five new plus 44 related tests, 937 full safe tests (89.156s) and 54 protected checks pass. No source mixing/upload, strategy change, worker/model call, decision rewrite or premature maturity. B5 remains PARTIAL_CLOSED; complete data repair and admission are outstanding. See [audit](../research/DATA_READINESS_AUDIT.md) and ADR 0053. No following milestone is active.

# Current milestone â€” R2 daily learning connection and visibility

R2 COMPLETED LOCALLY, 6 October 2026. Verified the existing collector â†’ Railway PostgreSQL â†’ scheduled frozen Swing decisions â†’ 3/4/5-session outcome path; consolidated collector/configuration/receipts into the main checkout and successfully retried the saved 21-chart upload. Main dashboard now exposes runtime-labelled Railway progress and quality/control evidence through a read-only bounded projection. Browser refresh shows 25 pending / zero matured labels per horizon, 21 partial charts and zero AI holdout samples. Existing workers, B5 admission, strategy rules, paper accounting and AI budgets are preserved. Fifty focused tests, 932 full safe tests (93.188s), all 54 protected checks and browser review passed. See [connection record](../research/DAILY_LEARNING_CONNECTION.md) and ADR 0052. Future sessions are genuinely pending; no following milestone is active. R1 records below are historical completed work.

6 October 2026 continuation: R1 is installed in the main local checkout, with a reusable Windows launcher and sanitized summary in ignored runtime storage. Trading Strategies opens first; Portfolio & demo is last. Browser checks cover all six tabs. Full safe suite: 926 tests passed in 87.585s after resolving resource contention. IG local endpoint reports CREDENTIALS_MISSING; history/entitlements remain unverified. Hosted deployment remains future work. See [main local verification](../research/MAIN_DASHBOARD_LOCAL_VERIFICATION.md).

Owner approved B5's partial close and proceeding on 5 October 2026. B5 is PARTIAL_CLOSED, not fully accepted: its software/source/accounting preparation is delivered while real-data admission and provider semantics remain deferred gates. Zero admitted real trades. ADR 0051 records the explicit scope change.

R1 is COMPLETED LOCALLY: a bounded safe report summary is integrated into the existing Trading Strategies dashboard through a read-only API. It shows source comparisons, dated verification and unresolved data gates, with unavailable states. No provider calls or engine replay on refresh. IG runtime access remains a separate check. Five focused tests, 926 full safe tests (87.712s), all 54 protected checks and local browser review passed. See [operating interface](../research/LOCAL_BACKTEST_RESEARCH_INTEGRATION.md). Main/hosted installation and runtime IG checks remain future work; no next milestone is active.

## Historical B5 checkpoints

Latest continuation: source research now includes 33 official Sasol SENS PDFs and issuer dividend corroboration. A separately written offline cash oracle prepares 36 conditional observed-price probes and passes 72 directional fee comparisons. No manifest/replay admission bypass occurred; real trades admitted remain zero. RAW/action and provider interval/volume contracts remain unresolved. Cash-only research scope is permitted by the original specification; real broker fills and historical invoices limit execution readiness, while unsupported real FX/gold can remain blocked. See ADR 0050 and the latest section of `LOCAL_BACKTEST_B5_CONTINUATION.md`. No following milestone is active.

Verification for this continuation: 921 safe tests pass (87.686s), 54 protected artifacts pass, independent reference byte-identical on repeat, all 736 existing stress-report fees match its independent arithmetic, and two fixed hand fee answers pass. No engine/selection change; eight killed mutation results are retained from the earlier applicable run.

## Autonomous continuation â€” 5 October 2026

Owner requested autonomous completion. This continuation resolved the official daily calendar/access gate and implemented the outstanding directional cash fee adapter; **full B5 remains BLOCKED on external evidence**, with zero admitted real trades. No following milestone is active.

Browser-acquired JSE notice 380/2025 and EquityMarketTradingHours PDFs were frozen and inspected. The 1 Septemberâ€“2 October window has 23 weekdays excluding the green-marked 24 September public holiday; broad equity hours are explicitly 09:00â€“17:00 SAST. This establishes the daily schedule, not every trade-reporting phase or the chart's interval convention.

OST native history export contains 8,457 unique dates from 1994â€“2026. Pilot high/low/close/volume matches IRESS daily on 23/23 dates and Sharenet on ten available dates. IRESS 391 intraday observations aggregate to all 23 daily OHLC values; daily volume remains larger on every date. A native IRESS OHLC CSV in Downloads has 177 UTC-stamped rows matching the captured table interpreted in SAST on all 177; it contains no volume. The bar start/end convention and adjustment/volume policy remain unverified.

Opt-in `OSTCashShareCosts` reuses the published component formula, includes fees in sizing, applies purchase-only tax and rejects inappropriate products. ADR 0049 records scope and assumptions. 368 post-hoc cost/daily-capacity cases were generated; maximum modeled position is 0.024953% of observed daily volume, which does not certify closing liquidity or full fills. ShareData's detailed calendar required Premium, the 2016 broker chart guide did not define volume/timestamp filters, and both available local .env files still lacked complete IG credentials. No subscription, terms acceptance, authentication credential export or broker mutation was performed.

Verification: 26 focused tests pass; 921/921 safe tests pass in 87.851s; five engine/cost and three selection mutations killed; protected 54/54 pass. Existing equity/FX/gold example semantic hashes remain identical. Stress report reproduces byte-identically. Remaining gates: complete action/adjustment evidence; provider interval/volume semantics; reconstructed historical availability contract; historical account tariff/quotes/fill evidence; own real FX/gold product evidence. See `docs/research/LOCAL_BACKTEST_B5_CONTINUATION.md` for artifact navigation and resolution criteria.

## Earlier checkpoints

Historical SENS integration/test slice completed locally on 5 October 2026: ShareData ten full-text notices, Moneyweb ten search leads with subscriber body still gated, Sharenet one public full-text notice. Twenty-one records group into ten releases in the same Sasol window; zero qualify as September point-in-time evidence. 917 safe tests and 54 protected artifacts passed; the final capture-provenance hardening passed 17 focused tests. Offline context audit reproduced byte-identically. See [SENS evidence and operating interface](../research/LOCAL_SENS_HISTORY.md). Full B5 remains BLOCKED on the external acceptance evidence below; no following milestone is active. The earlier acquisition/audit results are preserved as a checkpoint.

Date: 5 October 2026. Status: BLOCKED on external acceptance evidence; the resumed acquisition/audit slice is completed locally. Starting master HEAD 9ce6ea0ed416e7ec4db13621579c271b43c4cf4a; working tree was clean, expected origin verified. Owner authorized full B5 with flexible use of existing Yahoo, IG and Alpha Vantage integrations. No following milestone is active; wider integration remains deferred.

Work: bounded provider discovery/acquisition with isolated caches, source-verified identity/units/session/action/availability contracts, independent real-trade/accounting audit and cost/liquidity/intraday/product checks. Do not relax admission when a provider is absent, blend cash and CFD products, synthesize bars, print credentials, bulk-call paid APIs, change hosted configuration or submit broker orders. Continue independent gates if another data gate blocks.

Prior delivery: B1â€“B4 completed; 900 safe tests and 54 protected artifacts passed. Seven deliberate defects caught. Prior daily archive contained 883 inconsistent OHLC bars among 5271; prior intraday manifest had zero admitted bars. Provider access and new evidence must be reassessed rather than assumed from those old results.

New results: 23 fresh numerically valid Yahoo SOL daily bars and 368 actual 30-minute bars frozen; zero complete daily/intraday aggregates reconcile. Issuer identity/no-final-dividend evidence and current cash-share fee sensitivity recorded. Alpha search found no verified JSE mapping, and the shared five-reservation local probe budget was exhausted; no further FX/gold calls made. IG credentials unavailable in both relevant local checkouts. Official JSE calendar/session libraries returned HTTP 403. No action-complete, calendar-verified window was admitted; zero real trades audited.

Final verification: 906/906 safe tests passed in 86.994s, all seven disposable mutations killed, 54/54 protected artifacts passed. New diagnostics have six independent tests. Frozen offline report reproduced byte-identically. No default strategy, scheduled collector, external broker account, hosted configuration or production wiring changed. No push/deploy.

Required to unblock: verified exchange/session/action evidence; explicit reconstructed availability contract; complete intraday closing coverage and units; dated costs/quotes/capacity; own executable FX/gold contract/conversion/carry/margin evidence. Then admit the bounded window and independently reconcile actual-price hypothetical trades/cash/equity. See [full B5 attempt and evidence](../research/LOCAL_BACKTEST_REAL_DATA_ACCEPTANCE.md).


Optional Windows sign-in startup was subsequently added as an explicit opt-in. The control registers a named logon task when checked and requests removal on pause; mocked tests cover success and failure. It is not enabled by default and was not actually installed or verified through a Windows sign-out/sign-in in this check. Earlier statements in this document that no startup option exists describe the preceding state.
