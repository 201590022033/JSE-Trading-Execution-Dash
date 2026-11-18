# Unified reconnection and research roadmap — 18 November 2026

## Context and operating contract

The owner wants one working flow from ViewPoint and Zebra through indicators, sector-aware research, strategy radar, manual trade plans, news and AI, and the agreed dashboard. Earlier UIM, AI, HR and Strategy Radar milestones remain historical references; this roadmap integrates their outstanding acceptance rather than replacing or repeating working engines. Each milestone is deliberately a small end-to-end slice. Do not mark a milestone complete from unit tests alone when its outcome requires a running UI or an actual source. Record commands, real results, timestamps, revision, changed files and remaining gaps in a dated checkpoint. If a market session or login is unavailable, finish offline work and mark the live observation pending; do not block unrelated milestones or claim completion.

Preserve the authenticated OST/ViewPoint session, existing raw captures, Zebra decisions, research, budgets and trading controls. Avoid a second concurrent ViewPoint login; no orders or credentials. Retain source identity, acquisition and observation clocks, field units and provisional bars. Missing or differing fields must not disable unrelated usable data. Research comparisons and alerts are not proof of profitability or permission to trade. Never silently introduce a new feed, database or competing dashboard. Reuse existing repositories, intraday cache, work roster, registries and UI. Do not run chargeable model calls or alter schedules without authorization applicable at the time.

Current evidence: `CURRENT_MILESTONE.md` records successful real MTN and STX40 ViewPoint exports on 16 November and partial unattended acceptance. `VIEWPOINT_SESSION_HANDOFF.md` says the collector owns a separate Edge profile and warns about concurrent sessions. On 18 November at 22:51 SAST the dashboard API reported the last check at 13:04, `START_OST_SETUP`, and `worker_running=false`; no collector process was found. A signed-in ViewPoint window alone does not establish a collector listener. The precise shutdown cause is unverified. HR7 has a frozen historical dataset; HR11 describes an intraday feature registry. AI status and UIM checkpoint dates must be reconciled with current source and runtime before marking them complete.

## Execution rule

Work sequentially unless a later task is explicitly independent. Each milestone begins by rereading this contract and the prior checkpoint. Reuse the stated existing paths; verify the current revision and dirty files before changes. End each with focused tests, actual-path verification when available, a rollback instruction, and the next executable milestone. Commit and push only when authorized. A single unavailable symbol, indicator, source or model must not make independent data disappear.

## Milestones

### R01 — Reconnect the existing ViewPoint session
Dependency: none. Inspect the live collector, monitor, profile ownership and dashboard runtime. Provide a safe way to re-establish the listener without a duplicate login or closing the user's active session; use the existing setup when appropriate. Acceptance: one actual native five-minute table reaches the existing cache with exact symbol, source and receipt clocks; record previous/new count and worker status. If the only available setup requires replacing the active session, leave it untouched and document the handoff. Rollback: stop only any newly started owned process; retain downloads and session.

### R02 — Verify a complete market-session pass
Dependency: R01. Exercise the current canonical Top 5 and required benchmark through the existing collector and monitor in an open session. Acceptance: per-instrument imported/already-retained/error status, native evidence, completed/provisional bar distinctions and latest timestamps; verify an error in one source does not stop another. Preserve gaps and identify unattended versus manual results. Rollback: pause only the newly enabled monitor if needed; keep retained data.

### R03 — Define one reusable five-minute update
Dependency: R01; use retained data if R02 awaits the market. Extend existing intraday store/roster interfaces with a traceable update containing symbol, interval, bar time, receipt, source, units, completeness and revision identity. Acceptance: a new bar, duplicate, revision and missing-volume case reach consumers without duplicate records; existing API clients remain compatible. Rollback: revert the adapter; retain raw bars.

### R04 — Make the work roster visible and independent
Dependency: R03. Connect existing ViewPoint, retained-SENS and explicit Backtester work lanes without changing source schedules. Acceptance: queued/running/succeeded/failed and retry states visible for each lane; a failed lane does not hold the others; exercise an actual safe request and fixtures. Rollback: disable the new consumers without deleting queue history.

### R05 — Reconcile indicator implementations
Dependency: R03. Inventory current daily and intraday indicator calculators, definitions, input requirements and consumers; map RSI, EMA, OHLC stochastic, Ichimoku and the remaining implemented indicators to a shared versioned registry. Acceptance: table of implemented/used/missing with code references; test definitions and per-indicator handling of insufficient input. Preserve HR7/HR11 frozen evidence. Rollback: revert registry wiring only.

### R06 — Calculate indicators from the existing cache
Dependency: R05. Recalculate affected indicators from retained completed daily and five-minute bars when new data arrives; include parameters, timeframe and clocks. Acceptance: one actual retained share produces RSI, EMA, stochastic and Ichimoku; compare named timestamp/parameters with ViewPoint where possible and disclose differences and gap treatment. A missing volume field cannot disable price-only indicators. Rollback: disable the consumer; keep cache and historical outputs.

### R07 — Show indicators in the running dashboard
Dependency: R06. Present actual values and timeframe, parameters, source/receipt and last completed bar for the selected instrument, with partial results. Acceptance: verify selection and refresh on the real dashboard for a retained instrument and an unavailable-field example. Rollback: revert the UI view without deleting calculations.

### R08 — Reconnect historical and sector research
Dependency: R05; independent of market-session verification. Map HR7–HR11, frozen backtests and sector/benchmark assignments to current instrument and strategy identifiers. Acceptance: one share shows the relevant historical result, sector benchmark, exact version and sample count, with honest missing matches and no mutation of frozen evidence. Rollback: remove the projection only.

### R09 — Test strategy components individually
Dependency: R08. Use the existing backtester to compare a baseline with one chosen component change (entry, volume, risk, stop, target or exit), preserving data provenance and cost assumptions. Acceptance: reproducible actual-data run with signals, trades, costs, performance and sample size for both versions; missing data remains local to affected calculations. Rollback: remove the new research configuration; keep frozen runs.

### R10 — Connect the selected strategy to the trade card
Dependency: R07 and R08. Use the selected instrument and actual strategy/profile version to present entry conditions, volume, stop, target, expected duration and evidence label. Acceptance: real selected share reaches the card and backtester with identical profile/version and truthful research status. Rollback: revert card projection; do not touch strategies.

### R11 — Cost and instrument-specific manual execution details
Dependency: R10. Reuse available broker evidence and cost engine; show entry/exit estimates, financing if supported, units and OST input format by instrument type. Acceptance: independently checked worked example and explicit unknowns for unverified tariffs; correct cents/rands on a visible card. Rollback: revert presentation/calculation adapter, preserve tariff evidence.

### R12 — Test the real alert journey
Dependency: R02 and R10. Connect conditions to existing alert history and notification controls, with deduplication and traceable price timestamps. Acceptance: a safe test and a real-data observation show approaching/met states in dashboard/history; verify actual Windows display separately from submission. No order. Rollback: pause alert delivery; preserve history.

### R13 — Assemble instrument-centred news context
Dependency: R03; may proceed while live data awaits the market. Join existing SENS, calendar, retained news, sector/ETF, instrument and hypothesis context using actual identifiers and clocks. Acceptance: a selected share and a macro event each display source-linked context and missing coverage without model calls. Historical acquisition times are not backdated. Rollback: remove the read-only projection.

### R14 — Measure emerging themes and relevance
Dependency: R13. Add bounded, source-labelled trend and semantic relevance analysis across retained material, with an extensible vocabulary or model-assisted proposals rather than hard-coded SARB terms alone. Acceptance: dated SARB/rand regression plus a distinct share/sector case; show input coverage, deduplication and reviewable evidence. Do not equate retained counts to the whole internet or invent forum coverage. Rollback: disable the added analysis and preserve evidence.

### R15 — Finish AI routing and contextual outputs
Dependency: R13–R14. Reconcile AI1–AI3 with current runtime, use existing model/provider interfaces, and attach source-backed instrument/sector/event context. Acceptance: one authorized model cycle produces an inspectable report in the actual dashboard with model, input IDs, clocks, outcome and honest failures; reads invoke no model. Preserve existing budgets unless explicitly changed. Rollback: disable the added AI route without impacting data lanes.

### R16 — AI follow-up and unattended verification
Dependency: R15. Finish AI4/AI5 usefulness reviews, outcome links, recovery and unattended acceptance. Acceptance: a genuine scheduled or explicitly authorized cycle, subsequent dashboard visibility, failed-cycle recovery and traceable follow-up; report measured coverage and reviewed count rather than assert predictive skill. Rollback: disable the added AI supervisor only; preserve attempts and reviews.

### R17 — Finish the agreed dashboard hierarchy
Dependency: R07, R10–R11 and R13. Reconcile UIM checkpoints against the mockup, complete missing layouts and selected-share handoffs, including costs at the top and collapsible radar. Acceptance: actual running UI checked against the mockup, keyboard and narrow viewport; send-to-backtester, panel and news preserve the selected share. Rollback: restore previous UI assets; retain back-end records.

### R18 — Integrated reliability and handover
Dependency: R01–R17 or explicitly recorded external pending observations. Resolve relevant archive capacity and regression failures, verify restart/recovery and document one operational status. Acceptance: relevant Python and JavaScript suites, source-to-UI trace, no duplicate data, restart test and unchanged protected trading controls; report exclusions and unfinished market-dependent observations. Rollback: documented per-component procedure, no destructive reset.

## Evidence and handoff template

For every milestone record: objective; base and resulting revision; files; commands with actual results; selected record IDs and source/receipt clocks; UI and runtime identity; what was not verified; rollback; and the exact next milestone. Preserve prior evidence and explicitly distinguish implementation, isolated test, live UI, and unattended validation.
