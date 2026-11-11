# Strategy Radar checkpoint

Prepared 2026-11-06; updated 2026-11-11. M1–M6 completed locally; M7–M8 implementation and live verification remain separate. Reference: [roadmap](README.md), [hierarchy](HIERARCHY.md), [M1](milestones/M1.md). Preserve the separately ongoing research M5/M6/M7 and R12/P1 records. Before each implementation milestone refresh this checkpoint from actual repo status; after completion include commit state, tests, source availability, residual work and a concise handoff.

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


## M6 active / partial — 7 November 2026

Interactive radar and typed handoff banners are implemented locally; the Backtest handoff offers a user-invoked exact-profile shadow comparison. 1954 offline tests passed; isolated desktop and 390px fixture checks covered selection and the initially idle Backtest handoff. Full context propagation, backtest evidence classification and complete shortcut/accessibility checks remain. Do not mark M6 complete. Existing dashboard process remains untouched and needs a normal restart to load changes. No commit; see [M6 checkpoint](milestones/M6.md).


M6 continuation, 7 November: exact-context desk and verified evidence matching are implemented, with fixture handoff and keyboard checks. 1957 offline tests passed; no model or broker call. Implementation is ready locally; actual dashboard integration and physical touch checks remain pending the user's chosen restart. SENS issuer matching and exact backtest evidence remain explicitly unavailable when absent. See [M6 checkpoint](milestones/M6.md).


Post-restart M6 check: IRESS ViewPoint was online and the dashboard served the new UI, but simultaneous frozen-run evidence scans caused dashboard timeouts. Local fix makes evidence selection-driven and skips unregistered profiles before reading runs; 6 focused tests passed. A dashboard restart is required to load the backend fix. IRESS unattended ingestion and live entitlement remain unverified. M6 remains active.


9 November source check: EODHD free plan reports 19/20 daily calls used plus 500 extra prepaid calls; provider documentation excludes intraday from the free plan, so no intraday request was made. Existing five watch captures already reach 6 November. Africa API was the additional 4 November source; a 9 November bounded SASOL probe succeeded with 188 completed daily rows through 22 October, source-labelled Yahoo EOD, 49/60 matching closes against retained reference. IRESS and OST sessions are open; unattended access remains unverified. The one-time EODHD automation was removed. See [source qualification](M3_SOURCE_QUALIFICATION.md).


## M7/M8 local implementation — 9 November 2026

Explicit local-only background monitor, persistent trace-linked alert history, dashboard controls and Windows notification submission implemented. Nine focused tests passed; synthetic retained-bar-to-alert history and isolated worker start/pause passed; Windows accepted a test notification submission but visible delivery was not verified. Actual Top 5 has daily history through 6 November and zero clock-qualified intraday bars. Actual dashboard has not been restarted to load the routes, automatic feed and Windows logon restart are not installed, and M6 post-fix verification remains open. M7 and M8 remain pending live verification; see [M7](milestones/M7.md), [M8](milestones/M8.md) and [operator guide](OPERATOR_GUIDE.md).


Optional Windows sign-in startup was subsequently added as an explicit opt-in. The control registers a named logon task when checked and requests removal on pause; mocked tests cover success and failure. It is not enabled by default and was not actually installed or verified through a Windows sign-out/sign-in in this check. Earlier statements in this document that no startup option exists describe the preceding state.

The monitor now allows either five-minute or 30-minute shadow profiles; transition deduplication is keyed by instrument and profile. Eleven focused monitor tests passed after this change.

Final M7/M8 local regression passed 1968 offline tests and 11 focused monitor tests after profile-switch race hardening. The user-requested StockData and African Market Data repository reviews are recorded in M3 source qualification; neither currently establishes JSE intraday coverage.

## Interactive source review — 9 November 2026

In the user-opened in-app browser, ShareData showed a signed-in session, timestamped JSE market information labelled at least 15 minutes delayed, and current SENS listings. Sharenet's public home displayed 15-minute-delayed market data and SENS but also a Login link; an authenticated Sharenet session or account entitlement was not confirmed. IRESS ViewPoint was Online. Its STX40.JSE chart offered 5-, 15- and 30-minute periodicities; selecting 30 minutes and Table View displayed dated OHLC rows for 9 November and Copy/Download controls. The chart was restored to the original daily interval and table closed. This verifies interactive access only: the exact bar timestamp semantics, completeness, volume, actual feed delay, unattended operation and permission for automated collection remain unqualified. No bars were imported and no orders placed.

The running dashboard on this check displayed twelve research watches and no intraday monitoring; its monitor endpoint returned HTTP 404, consistent with the earlier backend still running. M6 post-fix and M7/M8 real-dashboard checks therefore remain pending the owner's dashboard restart. A potential M9 could focus on delayed swing-data source qualification and supported ingestion, session recovery and practical debugging; do not defer unresolved M6–M8 verification to a new label or assume an M9 has already been authorized.

### Restarted dashboard verification — 9 November 2026

The restarted dashboard displayed 12 watches and the actual background monitor controls. A user-authorized enable/pause exercise started the real worker: the status endpoint reported worker_running=true, a real last_check, SOURCE_UNAVAILABLE, no error and zero events. The UI pause returned the monitor to paused. No desktop notification, logon task, provider request, order or model call was made. This verifies the actual start/check/pause path but not visible toast delivery, dashboard-closed lifecycle or qualified source-to-alert behavior. M6 post-fix interaction and broader M8 checks remain pending.

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
