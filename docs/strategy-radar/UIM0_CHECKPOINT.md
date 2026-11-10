# UIM0 baseline checkpoint — 9 November 2026

Status: **UIM0 COMPLETE — baseline and contract**, with limitations below. This does not sign off any implementation or M6–M9 milestone.

The repository was clean at master `d97062f` before this audit. A Python 3.12 `app.py` process started at 16:04:35 on 9 November was listening on 127.0.0.1:5000. Process identity alone does not prove the loaded revision. Static controls, API families and historical M6–M9 gaps are recorded in `UIM0_SOURCE_INVENTORY.md`.

On 9 November an in-app browser opened the running dashboard and selected MTN. Opening the page triggered the dashboard's automatic public feed refresh and activity lease; a public index and news result appeared. The full set of underlying requests and any quota impact was not independently audited. No explicit model request, order, or restart was made. MTN showed daily Swing v1.1.0, 3/6 passed and 3 unknown, exact-profile backtest evidence unavailable, and a stale ShareData last value with source and receipt timestamps. The monitor was paused with SOURCE_UNAVAILABLE. These are point-in-time observations, not current market prices.

Desktop and mobile first-screen captures are saved in `C:/Users/Deon/Documents/Codex/2026-11-09/uim-radar/outputs/uim0-desktop.jpg` and `uim0-mobile.jpg`. The desktop viewport reported 1672 × 942, one pixel taller than the reference; the 390 × 844 viewport reported document width 375px, though navigation itself has a horizontal scroller. The first screen places imports, introduction and monitor above the radar, unlike the reference's immediate two-card workspace. The observed radar has selectable labelled markers and a selected research trace, but not the reference's first-screen selected decision card, market strip, sector breadth or events composition. This is a baseline, not a full measured comparison.

## Reference contract

The authoritative original is `C:/Users/Deon/Documents/Codex/2026-11-06/this-is-the-new-dedicated-strategy/UIM_exact_user_mockup.png` (1672 × 941); the repository copy has a different hash. It depicts two header rows, a side-by-side radar and selected-instrument card, and sector and events cards below. Price, plan, checklist and four navigation actions are illustrative. Its printed ring order conflicts with the owner correction: R5 is innermost and R1 outermost, with stronger setups nearer the centre. Setup progression, data freshness and backtest evidence are separate states.

## Capture and fixture plan

Compare the original and a deterministic synthetic fixture at 1672 × 941, recording each element's bounds and meaningful differences rather than claiming pixel accuracy. Capture the actual running app separately, including selected instrument, source and receipt clocks and unknowns; inspect 390px for page overflow, focus and touch targets. Use fixed clocks and named synthetic values in separate partial, stale, empty and error cases. Isolate the store and disable outbound sockets, or fully intercept data and mutation routes. `scripts/check_dashboard_browser_fixtures.py` intercepts only selected market/news routes and interacts with refresh controls; it is not a complete isolated radar fixture and must not be run unmodified against the user's process.

`scripts/capture_uim0_offline_fixture.py` now captures four labelled synthetic cases at 1672 × 941 and 390 × 844 using a fixed clock, a fictitious host and intercepted requests. Unknown APIs return 503; this is a partial/unavailable fixture, not a complete realistic data fixture. Eight captures and a request log are under `C:/Users/Deon/Documents/Codex/2026-11-09/uim-radar/work/fixture-captures`. Run with Python Playwright installed separately and existing Edge: `py -3.12 scripts/capture_uim0_offline_fixture.py --output <directory>`. The observed run used scratch Playwright 1.64.1; its log reported 370 GET requests to the fictitious host. The selected fixture scrolls to the radar and is not a first-screen reference comparison.

The updated harness also replays a locally recorded, MTN-only historical snapshot, labelled as not live. The snapshot is `C:/Users/Deon/Documents/Codex/2026-11-09/uim-radar/work/uim0-mtn-snapshot.json`; add `--snapshot <path>` to the command. Capture at 15:27:43 UTC used local watches, swing and quote GETs; this is a partial historical replay, not a replacement for the real application. A subsequent run generated ten captures and logged 464 GETs to the intercepted fictitious host; the stale synthetic quote was asserted visible. The complete element and action/state checklist is `UIM0_COMPARISON.md`.

In an independent offline keyboard audit, the first two Tab presses focused Dashboard then Scan. Focusing each of the eight navigation buttons and pressing Enter exposed its corresponding section and retained focus. These are fixture observations; full sequential tab order, visual focus, selection announcements, history, physical touch and reduced motion remain unverified. The buttons did not expose `aria-selected`. One exploratory run timed out; the clean rerun passed, with 24 GETs to the fictitious host only.

## Known limitations and later verification

- Native window capture timed out twice; in-app browser capture subsequently worked at a reported 1672 × 942, one pixel taller than the reference. The element checklist identifies missing and unverified features; an exact same-viewport measured comparison remains for UIM2. Dynamic listener and per-view runtime inventory remains incomplete.
- Verify running revision, current data and source ages. Historical M6–M9 checkpoint claims are not current tests: qualified intraday candles, visible Windows toast, source-to-alert flow, dashboard-closed operation and exact-profile handoffs remain open.
- Exercise keyboard, focus, reduced motion and available touch paths; document any environment limitations. Keep real, stale and synthetic evidence distinct.

Ollama-to-Alpha Vantage MCP remains a concrete UIM5 workstream, subject to explicit user invocation and verified access, entitlement and nonchargeable quota. Direct Alpha Vantage repair and existing Ollama advisory code do not demonstrate that workflow.
