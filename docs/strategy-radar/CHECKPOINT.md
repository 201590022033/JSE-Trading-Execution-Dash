# Strategy Radar checkpoint

Prepared 2026-11-06; updated 2026-11-12. M1–M9 completed locally; M10 is active with source limitations recorded. At the owner's request, bounded Radar M10 work proceeds alongside the existing research M5; M5 remains unchanged. This is a one-time sequencing exception, not a general parallel-work policy. This Strategy Radar M-series is distinct from UIM/research milestones; no UIM6–UIM8 briefs are present. The old dated M6/M7/M8 entries below are historical snapshots, superseded by the later completion entries. Reference: [roadmap](README.md), [hierarchy](HIERARCHY.md), [M1](milestones/M1.md). Preserve R12/P1 and the separately ongoing research M5/M6/M7 records.

## Strategy Radar M10 — six-choice radar and churn audit, 12 November 2026

The visible UI now limits active radar choices to the current Top 5 plus at
most one manual pin. Other non-archived watches remain retained in a collapsed,
non-selectable history section. Pinning a second watch is rejected at both
contender selection and pin-update boundaries; the existing pin is not silently
replaced. The previous multiple-pin case remains inspectable and can be
released. No grace, monitor or event history is deleted.

The 75 archived Zebra screen snapshots (5–11 November) contain eight distinct
chronological rank/score/input states, seven distinct Top-5 sets and six
membership transitions. On 6 November NPN first retained 3 November inputs
(rank 14, score 53.1538), then updated to 5 November inputs (rank 1, 89.4459),
then to 6 November inputs (rank 6, 73.2194). It returned to rank 5 on 9
November with the same 6 November inputs as competing ranks changed; newer
inputs then moved it to rank 6 on 10 November (77.8324) and rank 5 on 11
November (80.0091). This separates stale/new-input changes from relative
ranking churn. The descriptive score and weights were not changed.

The owner-supplied MTN.JSE five-minute chart-table CSV was imported into the
local Radar intraday cache. Its 823 raw bytes are retained under SHA-256
`D64F5286D80D81995F75343EF48BCEFF96FF137D2C278EE8F63CDD4236A4BCD3`,
with eight source rows from 07:20 to 07:55 UTC. File modification and import
receipt clocks remain distinct. All normalized OHLCV fields are null; the
records remain unknown-clock, unverified-unit evidence and are excluded from
canonical bars, shadow evaluation and daily Zebra ranking. Manual local
research use was authorized; unattended collection rights remain unverified.

The focused intraday integration file passed 10 tests, including chronological
ordering of reversed CSV rows. JavaScript syntax and `git diff --check` passed.
At approximately 10:07 SAST both OST and ViewPoint pages were accessible, but
there was no known login start or controlled idle interval, so no timeout
duration is established. The Save dialog was not exposed to the browser tool;
the downloaded CSV appeared in Downloads after manual Save and the pause's
cause remains unknown. No browser setting, polling or keepalive was changed.
See [M10](milestones/M10.md), the [CSV/session change note](../changes/2026-11-12-viewpoint-csv-import-and-session-review.md)
and [churn change note](../changes/2026-11-12-strategy-radar-m10-six-choice-churn.md).

## M1 completed locally — 6 November 2026

Inactive responsive radar shell, collapsible import panel, typed unconnected contracts and baseline/ADR delivered. 1905 offline tests and 24 focused tests passed; desktop/390px browser, keyboard and shortcut checks passed. See [M1 checkpoint](milestones/M1.md) and [baseline](M1_BASELINE.md) for commands, prior failure and limitations. Existing dirty work remains uncommitted and preserved; no broker write, new provider/model integration or monitoring. M2 is planned and awaits explicit instruction. R12/P1 and prior research statuses remain unchanged.

## M2 completed locally — 6 November 2026

Top 5 and pinned watch lifecycle, local Zebra prewarm/cache, bounded public refresh and local watch UI/API delivered. 1913 offline tests passed before final narrow concurrency/zero-grace hardening; 41 focused tests passed afterward. Real Yahoo and ShareData captures succeeded for all five saved Top 5 shares; manual OST/IRESS automation remains unverified. Existing dashboard process needs a normal restart to load M2. See [M2 checkpoint](milestones/M2.md), ADR 0096 and change note. No commit; prior dirty work preserved. M3 awaits explicit go, and R12/P1 and prior research statuses remain unchanged.

## M3 completed locally — 6 November 2026

Quote contracts, protected intraday cache, manual source input, source-aware merge and explicit EODHD adapter delivered. 1930 offline tests and 55 focused checks passed. Two real ViewPoint 30-minute rows are retained as manual evidence with source timing unverified; an unattended entitled intraday feed remains unverified. Existing daily collectors are preserved, and the dashboard process remains running until the user chooses to restart. See [M3 checkpoint](milestones/M3.md), [source qualification](M3_SOURCE_QUALIFICATION.md) and ADR 0097. No commit. M4 awaits explicit go; R12/P1 and prior research statuses remain unchanged.

EODHD preference recorded: use it for JSE intraday if the existing account includes it. The account status check on 6 November returned a free subscription and 19/20 credits used; the documented intraday endpoint costs five credits and lists paid intraday plans. No intraday request or upgrade was made. See M3 source qualification.

Source preference: keep OST, IRESS, EODHD and IG paths open independently; lack of unattended broker access does not block usable per-field data. The user may reconnect the existing IG API. Reuse the existing IG integration read-only, verify present JSE instrument mappings, history/streaming entitlements, costs and timestamps when access is restored, and do not treat earlier entitlement failures as current. No order submission.

## M6 completed locally — 11 November 2026

After restarting the workspace dashboard, health and PostgreSQL were available;
the swing endpoint returned 11 research-only evaluations with live execution
disabled. The live UI was exercised across all six research handoffs, including
typed instrument/product/strategy/version/timeframe context. Ask prompt preview
reconstructed the selected trace without calling a model. Retained issuer news
and sector context loaded; technical history was preselected; Costs remained a
manual scenario; pin/unpin persistence, updated labels and focus restoration
were verified. The selected VOD share had no exact-instrument match in the
available saved backtest run, so no alternate instrument was selected and no
backtest was run.

Keyboard selection/focus and collapse/expand passed. Touch emulation selected a
watch using a 49.9×44px target at a 390px viewport; document width was 375px.
Physical touchscreen hardware was unavailable. The final focused combined
M6/issuer-news/sector-context/watch suite passed 35 tests; JavaScript syntax and
`git diff --check` passed. The 2,091-test offline suite reported 21 errors and
2 failures, all in separate UIM5 async/storage/search tests; the offline socket
guard blocks `socket.socketpair` used by asyncio. No M6 test failure was
identified. These failures remain recorded, not suppressed.

No model/provider generation, backtest run, broker action, notification or
monitor setting change was made. Daily Swing 1.1.1 remains a research-only
profile without an exact-profile fill backtest; no performance claim is made.
M6 acceptance is complete locally with these evidence limitations. M7/M8
operational verification and the earlier research M5/R12/P1 work remain
independent. Commit state is recorded by Git, not implied by this checkpoint.

Post-restart M3 check, 6 November 2026: localhost:5000 serves the watch, quote and intraday endpoints (HTTP 200). Saved ranking CLS/BVT/MTN/VOD/ABSPJ matches the five leading watches; BTI/FSR/NPN/PRX are retained in grace. The dashboard displays the two ABSPJ ViewPoint manual records with unknown interval timing. IG demo account status is CREDENTIALS_MISSING; current IG mapping/entitlements remain untested. EODHD intraday account check remains scheduled. No M4 work or order was started.

M4 started 6 November 2026. Working tree was dirty with M1–M3 and prior user work, preserved. Build distinct intraday shadow profiles, causal traces and honest replays; no provider/model/order calls.

## M4 completed locally — 6 November 2026

Separate 5m/30m shadow rules, causal per-field traces and receipt-versioned aggregation, with descriptive costed next-bar baseline comparison, are implemented. 1945 offline tests and 35 focused tests passed. The retained ABSPJ observations yield zero replay samples because their interval clocks are unknown; no profitability inference. The comparison does not simulate actual fills or the full stop/target/exit path. The current dashboard process needs its normal restart for M4 endpoints. See [M4 checkpoint](milestones/M4.md), ADR 0098 and the change note. Existing dirty work remains uncommitted; M5 awaits explicit go. R12/P1 and prior research statuses are unchanged.


## M5 completed locally — 7 November 2026

Manual cash-share and CFD scenario plans and evidence-gated OST field mappings are implemented; unsupported products report missing terms. Exact OST order-field mapping remains unverified, so copying is disabled. 1954 offline and 9 focused tests passed; the isolated browser form was inspected. The dashboard needs a normal restart. Prior dirty work remains uncommitted. No broker order or quote was requested. See [M5 checkpoint](milestones/M5.md) and [evidence gap](M5_OST_EVIDENCE.md). M6 awaits explicit go.


## Historical M6 status snapshot — 7 November 2026 (superseded)

Interactive radar and typed handoff banners were implemented locally; the Backtest handoff offered a user-invoked exact-profile shadow comparison. 1954 offline tests passed; isolated desktop and 390px fixture checks covered selection and the initially idle Backtest handoff. Context propagation and live dashboard checks were still outstanding. This dated snapshot was superseded by the M6 completion entry below; see [M6 checkpoint](milestones/M6.md).


Historical M6 continuation, 7 November: exact-context desk and verified evidence matching were implemented, with fixture handoff and keyboard checks. 1957 offline tests passed; no model or broker call. Actual dashboard integration and touch checks remained pending at that point. SENS issuer matching and exact backtest evidence remain explicitly unavailable when absent. See the later [M6 checkpoint](milestones/M6.md).


Historical post-restart M6 check: IRESS ViewPoint was online and the dashboard served the new UI, but simultaneous frozen-run evidence scans caused timeouts. The local fix made evidence selection-driven and skipped unregistered profiles before reading runs; 6 focused tests passed. A further dashboard restart was still required at that point. The later 11 November completion entry records verification after restart. IRESS unattended ingestion and live entitlement remain unverified.


9 November source check: EODHD free plan reports 19/20 daily calls used plus 500 extra prepaid calls; provider documentation excludes intraday from the free plan, so no intraday request was made. Existing five watch captures already reach 6 November. Africa API was the additional 4 November source; a 9 November bounded SASOL probe succeeded with 188 completed daily rows through 22 October, source-labelled Yahoo EOD, 49/60 matching closes against retained reference. IRESS and OST sessions are open; unattended access remains unverified. The one-time EODHD automation was removed. See [source qualification](M3_SOURCE_QUALIFICATION.md).


## Historical M7/M8 implementation snapshot — 9 November 2026

As of 9 November, explicit local-only background monitor, persistent trace-linked alert history, dashboard controls and Windows notification submission were implemented. Nine focused tests passed; synthetic retained-bar-to-alert history and isolated worker start/pause passed; Windows accepted a test notification submission but visible delivery was not verified. Actual Top 5 had daily history through 6 November and zero clock-qualified intraday bars. The dashboard had not yet been restarted to load the routes, and M6 post-fix verification was open at that time. Subsequent M6 and M7 completion records follow. See [M7](milestones/M7.md), [M8](milestones/M8.md) and [operator guide](OPERATOR_GUIDE.md).


Optional Windows sign-in startup was subsequently added as an explicit opt-in. The control registers a named logon task when checked and requests removal on pause; mocked tests cover success and failure. It is not enabled by default and was not actually installed or verified through a Windows sign-out/sign-in in this check. Earlier statements in this document that no startup option exists describe the preceding state.

The monitor now allows either five-minute or 30-minute shadow profiles; transition deduplication is keyed by instrument and profile. Eleven focused monitor tests passed after this change.

Final M7/M8 local regression passed 1968 offline tests and 11 focused monitor tests after profile-switch race hardening. The user-requested StockData and African Market Data repository reviews are recorded in M3 source qualification; neither currently establishes JSE intraday coverage.

## Interactive source review — 9 November 2026

In the user-opened in-app browser, ShareData showed a signed-in session, timestamped JSE market information labelled at least 15 minutes delayed, and current SENS listings. Sharenet's public home displayed 15-minute-delayed market data and SENS but also a Login link; an authenticated Sharenet session or account entitlement was not confirmed. IRESS ViewPoint was Online. Its STX40.JSE chart offered 5-, 15- and 30-minute periodicities; selecting 30 minutes and Table View displayed dated OHLC rows for 9 November and Copy/Download controls. The chart was restored to the original daily interval and table closed. This verifies interactive access only: the exact bar timestamp semantics, completeness, volume, actual feed delay, unattended operation and permission for automated collection remain unqualified. No bars were imported and no orders placed.

The running dashboard on this 9 November check displayed twelve research watches and no intraday monitoring; its monitor endpoint returned HTTP 404, consistent with the earlier backend still running. M6 post-fix and M7/M8 real-dashboard checks were pending the owner's dashboard restart at that time. M6 has since been completed locally; M7/M8 operational checks and M9 source qualification remain separately scoped.

### Restarted dashboard verification — 9 November 2026

The restarted dashboard displayed 12 watches and the actual background monitor controls. A user-authorized enable/pause exercise started the real worker: the status endpoint reported worker_running=true, a real last_check, SOURCE_UNAVAILABLE, no error and zero events. The UI pause returned the monitor to paused. No desktop notification, logon task, provider request, order or model call was made. This verifies the actual start/check/pause path but not visible toast delivery, dashboard-closed lifecycle or qualified source-to-alert behavior. At the time, M6 post-fix interaction and broader M8 checks remained pending; see the later M6 completion entry for its resolved local verification.

## Daily swing connection - 9 November 2026

Daily Swing 1.1.0 is connected to the radar in code and verified in an isolated local preview. MTN showed 2/6 descriptive conditions passed and 4 unknown for the completed 6 November session. Five-minute remains separately selectable; this does not supply intraday bars or daily monitoring. The running dashboard needs a restart. M6-M9 remain partial; see M9 for acceptance gaps and validation.

Follow-up: prewarmed four saved benchmark ETF histories locally. MTN now evaluates 3/6 passed and 3 unknown for 6 November, including aligned benchmark outperformance. Benchmark prewarm was one-off, not automatic. Full safe suite passed 1974 tests; four focused swing tests passed after the added API-locality check.

## Daily Swing reclaim profile 1.1.1 — 11 November 2026

The Radar now selects the additive `swing-ohlcv-wilder-v2` profile, counting an
EMA20 reclaim from any of the latest three sessions and displaying breakout OR
reclaim as one trace row. Feature 1.1.0 and the 1.2.0 shadow policy remain
unchanged. No exact-profile fill backtest is available; this version skips the
legacy fill-run scan. Eighty-five focused Swing/Radar/profile API tests and
JavaScript syntax/OR-state checks passed. At that point actual-dashboard
verification was still pending; it is documented in the later completion entry
below. No performance claim is made.

## M6 completed locally — 11 November 2026

After restarting the workspace dashboard, health and PostgreSQL were available;
the swing endpoint returned 11 research-only evaluations with live execution
disabled. The live UI was exercised across all six research handoffs, including
typed instrument/product/strategy/version/timeframe context. Ask prompt preview
reconstructed the selected trace without calling a model. Retained issuer news
and sector context loaded; technical history was preselected; Costs remained a
manual scenario; pin/unpin persistence, updated labels and focus restoration
were verified. The selected VOD share had no exact-instrument match in the
available saved backtest run, so no alternate instrument was selected and no
backtest was run.

Keyboard selection/focus and collapse/expand passed. Touch emulation selected a
watch using a 49.9×44px target at a 390px viewport; document width was 375px.
Physical touchscreen hardware was unavailable. The 25-test M6 group and an
additional 14 issuer-news/sector/watch tests passed; JavaScript syntax and
`git diff --check` passed. The 2,091-test offline suite reported 21 errors and
2 failures, all in separate UIM5 async/storage/search tests; the offline socket
guard blocks `socket.socketpair` used by asyncio. No M6 test failure was
identified. These failures remain recorded, not suppressed.

No model/provider generation, backtest run, broker action, notification or
monitor setting change was made. Daily Swing 1.1.1 remains a research-only
profile without an exact-profile fill backtest; no performance claim is made.
M6 acceptance is complete locally with these evidence limitations. M7/M8
operational verification and the earlier research M5/R12/P1 work remain
independent.

## M7 completed locally — 11 November 2026

The monitor/notification/startup suite passed 13 tests; one shortcut test was
skipped to avoid modifying an existing user shortcut. The actual dashboard was
healthy. Its existing settings (enabled, 30-minute profile, 900-second
interval, desktop notifications on, sign-in startup off) were preserved while
the dead worker was relaunched. The dashboard now reports worker running,
`SOURCE_UNAVAILABLE`, no error, and zero events. A separate hidden worker on a
temporary store acquired its lease, checked an empty watchlist without a
dashboard dependency, and exited cleanly on pause, releasing the lease.

A `TEST ONLY` Windows toast was recorded by PushNotification-Platform event
3052 as delivered to Strategy Radar on session 1; visible banner presentation
was not independently observed. The System view showed the running status at
390px with no horizontal page overflow. Existing retained-bar→trace→dashboard
history replay covers the end-to-end alert path. No provider, model, broker,
paid quote, live order, notification setting, or startup task was changed.
No clock-qualified intraday feed was available at M7 completion; M8 records the
full rollout and source gaps without implying live-data qualification.

## M8 completed locally — 11 November 2026

The read-only live dashboard was healthy. The watch endpoint returned 11
instruments in 1.09 seconds (one observation, not a latency guarantee); Top 5
was VOD/TFMJ/MTN/NTU/NPN. Each had completed daily history through 10 November.
For VOD, 2,524 sessions were available; retained ShareData and Yahoo daily
fields had receipts on 11 November at approximately 10:03 UTC. IRESS and OST
had no retained fields and remain manual-capture paths with automation
unverified. This is completed daily history, not a current quote.

The intraday cache contained two ABSPJ records with unknown clock semantics,
zero verified interval bars, and no records for the current Top 5. Thus no
current/delayed intraday path can be claimed. The named dependency is an
entitled, permitted, unattended JSE intraday source with verified bar clocks;
the observed EODHD free plan does not establish intraday entitlement, and
interactive IRESS/OST access does not establish unattended ingestion.

The existing monitor remained enabled on the owner's existing 30-minute,
900-second interval, desktop notifications enabled, sign-in startup disabled.
Its live worker reports `SOURCE_UNAVAILABLE`, no error, and zero alert events.
The separate temporary-store worker lifecycle and retained-bar→trace→history
fixture passed. `TEST ONLY` Windows toast delivery was recorded by OS event
3052, although visible banner presentation was not independently witnessed.
The actual System view was checked on desktop and at 390px; mobile document
width was 390px. M6 had verified all six research handoffs and keyboard/touch
emulation.

Focused M8 integration passed 47 tests. The full offline suite ran 2,091 tests
in 160.493 seconds: 21 errors, 2 failures, and 1 skip. The errors were confined
to UIM5 async/MCP/OAuth/Qwen tests affected by the safe runner's socket guard
and Windows Proactor `socketpair` behavior. The two failures were UIM5 tool
research API storage/stage results. No Strategy Radar test failed. JavaScript
syntax and `git diff --check` passed. Runtime folder size was about 135.2 MB;
the worker process used about 4.0 MB working set at the point measured.

No paid/provider/model request, broker action, live order, source capture,
notification preference or sign-in task was changed during this verification;
only the clearly labelled TEST ONLY Windows toast was submitted. M8's local
software, fixture, lifecycle and browser verification is complete. A qualified
live/delayed intraday source, user-visible toast confirmation, and actual
Windows sign-out/sign-in testing remain operational evidence gaps, not claims
of live-feed qualification or strategy performance.

## M9 completed locally — 11 November 2026

One explicitly invoked public ShareData MTN capture retained a raw response
(`b99c9ac275fed977829d321da7969866b6029b9a89facdc4e6a93007288ba472`) and a
delayed last-price observation of ZAR 228.88: source label 16:17 SAST on
11 November, local receipt 16:33:00.648 SAST, provider-declared delay at least
15 minutes (observed source-to-receipt gap about 16 minutes). The live radar
display showed source, receipt, delay floor and that retained values differ.
This is one delayed trade observation, not OHLC or a candle.

The swing quote view uses an explicit 1,800-second source-age limit; the
intraday/default view remains 300 seconds. The same saved observation reads
`DELAYED` for swing and `STALE` for the default view. Capture is a manual
MTN-only action with a five-minute minimum interval; other instruments,
authenticated sources, continuous coverage and unattended permissions are
not qualified. At 16:51:59 SAST its source age reached 2,099 seconds and the
swing view correctly reclassified it STALE after its 1,800-second limit.
Public capture has no login session to expire; source-date or
transport failures remain visible, and mocked failure/recovery and throttle
tests cover the operator path.

The real capture initially returned a false HTTP 503 after saving the quote.
The API response construction now merges capture fields as keyword arguments;
source/input failures are logged and reported as unavailable, while raw-file
and SQLite retention failures are separately reported. After a normal dashboard restart,
health and PostgreSQL were available, 11 watches loaded, and the same retained
quote was read by API and browser. By 16:51:59 SAST its source age was 2,099
seconds, so both API and radar correctly showed STALE. The updated POST
response is verified by isolated API tests; no second provider capture was
made.

The focused ShareData quote test module passed 7 tests and JavaScript syntax
validation passed. The latest full safe suite ran 2,097 tests in 168.792
seconds with 22 errors, 2 failures and 1 skip. Twenty-one errors were existing
UIM5 async/MCP/OAuth/Qwen Windows Proactor `socketpair` failures caused by the
safe runner's socket guard; one unrelated Release Inbox concurrency test
reported an unsafe local store file. Both failures were UIM5 tool-research API
storage/stage expectations. No Strategy Radar test failed. A suitable unattended,
permitted intraday OHLC source, verified interval clocks and candle coverage
remain open for post-M9 planning; no intraday feed or trading signal is
qualified. See [M9](milestones/M9.md) and its
[verification note](../changes/2026-11-11-strategy-radar-m9-sharedata-qualification.md).
