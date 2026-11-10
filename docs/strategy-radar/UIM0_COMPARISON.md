# UIM0 reference comparison and action/state matrix

Evidence: authoritative original `C:/Users/Deon/Documents/Codex/2026-11-06/this-is-the-new-dedicated-strategy/UIM_exact_user_mockup.png` (1672 × 941); actual first-screen `C:/Users/Deon/Documents/Codex/2026-11-09/uim-radar/outputs/uim0-desktop.jpg` (reported viewport 1672 × 942); mobile `.../outputs/uim0-mobile.jpg` (390 × 844); and separate labelled synthetic screenshots in `.../work/fixture-captures`. The actual selected MTN state below is from the parent's browser accessibility observation, not the first-screen image. Source inventory in `UIM0_SOURCE_INVENTORY.md` is static, not runtime proof. The one-pixel desktop height difference and browser capture scaling preclude a pixel-perfect claim.

## Reference elements

The reference positions below are approximate anchors from the roadmap in CSS pixels at 1672 × 941. “Not in first screen” refers to the actual screenshot only; it does not imply the feature is absent from the application. Reference values are illustrative.

| Element | Reference | Actual baseline and difference / unknown |
|---|---|---|
| Header and navigation | y≈0–55; title, tabs, badge | Title and demo/paper label appear in a separate large header, navigation on a second row. Eight tab buttons visible. Current screenshots do not verify history or each tab. |
| Market strip | y≈55–99 | No market/session/source freshness strip in actual first screen. Public market information exists further down by observed accessibility tree; its suitability as a strip is unverified. |
| Radar and decision cards | x≈11–815 and 829–1661, top≈113, bottom≈765 | The first screen instead has imports, introductory workspace, and monitor controls before radar. Neither completed radar nor selected card is visible in the first screen; synthetic selected view shows them lower in the page. |
| Radar heading and counters | Heading with state counters | Heading and 12 daily watches/no automatic feed are visible; illustrative developing/entry/freshness counters are not shown in first screen. Counter rule coverage unverified. |
| Scope/rings/sweep | Circle x≈145–700, y≈199–755; crosshair, five rings and decorative sweep | Actual radar observed after scrolling, with crosshair and selectable labelled watches; no same-position first-screen equivalent. The synthetic selected capture shows a different ring/scope styling and no reference sweep. Treat the stronger-inward correction as authoritative: R5 inner, R1 outer; unknown does not pass. |
| Watch markers | Dots with nearby tickers | Actual browser exposed twelve named checkbox-like controls and MTN was selected. Multiple-watch collision, long tickers, touch and keyboard interaction are not established by that observation. |
| Evidence legend | Inside radar card bottom left | Actual accessibility observation exposes grey/no usable evaluation, red/unlinked research hypothesis, green/evidence required. Distinct setup and freshness count presentation requires further review. |
| Selected heading | x≈882 y≈137; instrument/product and collapse | Actual selection displayed `MTN · Cash share`; this is below the initial viewport. Optional collapse behavior not verified. |
| Setup badge | Below heading, strategy and count | Actual selection displayed daily `jse_swing_3_5d v1.1.0`, WATCHING, 3/6 passed and three unknown. Its trace is not the mockup's box-breakout strategy. |
| Price and broker units | y≈249, large price and OST copy | Actual selected state displayed ShareData last as STALE with source and receipt timestamps and minimum delay; bid and ask unavailable. No current price or verified broker unit is implied. Copy behavior and exact mapping were not tested. |
| Trade-plan table | x≈846–1255, y≈329–621, copy affordances | Actual accessibility tree exposes a manual hypothetical plan form with entry, quantity, stop, target, costs and assumptions; a compact populated reference-style table was not observed. Calculation, copy and persistence not exercised. |
| Checklist | Adjacent to plan | Actual MTN trace lists six named rules, values/thresholds and PASS/UNKNOWN. Provenance completeness and keyboard/screen reader behavior beyond the exposed tree are not verified. |
| Action row | Backtest, Ask Panel, News & SENS, Costs | Actual MTN selection exposes those actions plus Technical and sector/fundamentals. Destination context and no-auto-run behavior were not exercised in this baseline. |
| Sector context | x≈11–1017, y≈782–911 | Actual selected trace names Telecommunications and benchmark ETF_STX40. This alone is not a breadth calculation; reference sector card is not visible in first screen. |
| Upcoming events | x≈1033–1661, y≈782–911 | Reference card is not visible in actual first screen. Exact issuer matching and dates are unverified. |

## Actions and states

| Action or state | Evidence | Remaining verification |
|---|---|---|
| Load dashboard | Actual browser loaded 12 daily watches; automatic feed refresh/activity lease occurred. | Full request and quota impact not audited; do not assume load is read-only. |
| Select watch | Parent selected MTN in actual UI; selection, trace and manual-plan instrument updated. | Mouse/touch/keyboard variants, focus restoration, reload and other products. |
| Daily / five-minute profile | Both choices exposed in actual control. | Switching and independent data semantics not exercised in this audit. |
| Empty, partial, stale, error | Eight fixed-clock, explicitly synthetic captures generated by isolated harness, two viewports per case; unspecified APIs return 503. | These are not real data or complete production fixtures; examine exact state rendering and transitions before UIM2 acceptance. |
| Monitor | Actual UI showed paused and SOURCE_UNAVAILABLE, with a historical last check. | No lifecycle or toast test in this audit; M7–M9 source-to-alert gaps remain open. |
| Manual form, pin, quote refresh | Controls exposed in actual accessibility tree. | Not activated: may mutate data or fetch from providers. |
| Engine handoffs | Named buttons present in selected MTN view. | Exact identity/version/product propagation, mismatch handling and absence of automatic work remain unverified. |
| 390px layout | Captured at 390 × 844; browser reported document width 375px, navigation has its own horizontal scrollbar. | Full-page clipping, screen-reader, keyboard and physical touch testing remain unverified. |
| Keyboard / loading | Initial browser observation showed loading before watches populated. In a separate offline fixture, the first two Tab presses reached Dashboard then Scan; each of eight focused navigation buttons responded to Enter and retained focus. | Full sequential tab order, visual focus, selection announcement and reduced-motion behavior remain unverified. Fixture findings do not prove live-app behavior. |

## Existing engine baseline

Static template declares Dashboard, Scan / Top 5, Strategies, Backtest Lab, News & SENS, Technical analysis, Portfolio & demo and System via `data-tab` IDs detailed in the source inventory. Only Dashboard and MTN selection were observed by the parent in the running browser during this baseline; per-view rendered behavior, links and listeners for the other seven remain unverified. Existing M6–M9 gaps and source limitations remain independent of this UI audit.

The harness also supports a separately labelled partial historical MTN replay from locally captured watches, swing and quote responses. It returns unavailable for unrecorded APIs; it is neither a complete real-app fixture nor evidence that its recorded values remain current. The precise capture path and run details are in `UIM0_CHECKPOINT.md`.

## Comparison method for later milestones

Use the original at 1672 × 941 and capture the implementation at exactly the same viewport and device scale; compare header/strip/card rectangles, alignment, spacing, text wrapping, controls, ring geometry and legibility. Record measured deltas individually and explain any data-truth or accessibility-driven divergence. A provisional review threshold is ±8 CSS px for major card edges and ±4 CSS px for internal alignment; text must remain readable and unclipped. These are review triggers, not evidence of current conformance or a substitute for owner acceptance. Compare separate named synthetic and actual stale/partial states; never infer visual agreement from the fixture alone. At 390px check page overflow, control hit areas, focus and reading order; physical touch and assistive technology require separate evidence.
