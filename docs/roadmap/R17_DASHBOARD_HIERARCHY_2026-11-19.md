# R17 dashboard hierarchy and selected-share handoffs — 19 November 2026

Base revision `9033517`. The live dashboard was compared at 1672 × 941 against the preserved original `UIM_exact_user_mockup.png` in the 6 November planning workspace, SHA-256 `d0a632cf52048e7e13a07e8d191c8f2d881e1c6ed593d28905b7aea60cc19a9c`. The earlier UIM2 layout and UIM4 handoff checkpoints supplied the existing structure and unresolved verification items.

| Reference area | Live verification |
| --- | --- |
| Navigation and market strip | Separate engine tabs remain reachable. The market strip sits above Radar and shows actual source/clock states. The separate local freshness checks sit below the workspace context. The real alert remains visible in a compact strip. |
| Radar | Five watched shares, rings, strength labels, crosshairs, sweep and evidence legend were visible. Status counters use actual evaluation states, and stronger setups remain farther inward. Enter selected VOD, and Enter on the Radar summary collapsed and reopened it while retaining the selection. |
| Selected-share header and plan | VOD cash-share profile, version, evidence badge and quote availability were visible. Costs and net appear first, followed by entry, stop, target, quantity and hold. The fee and strategy detail, indicators and manual editor remain accessible. Live quote and OST format were unavailable in the observed example. |
| Checklist and actions | The checklist remained next to the plan at desktop width. Backtest, Ask Panel, News & SENS and Costs form the first action row. Technical, sector and pin tools remain under More actions. |
| Sector and events | Retained sector and selected-share news/event cards follow the primary workspace. The illustrative prices, broker-specific formatting, example checklist and forecast values remain absent when unsupported by real records. |
| Narrow layout | At 390 px the document and scroll widths were both 390 px. Radar and decision card stacked, and actions used two columns. |

The real handoffs preserved `VOD / CASH_SHARE / jse_swing_3_5d v1.1.2 / daily` in Backtest Lab, Ask Panel and News & SENS. Backtest disclosed that no exact-version comparison was available. The server-validated Ask prompt preview kept VOD and v1.1.2 and made no model call. News loaded retained Vodacom sources scoped to VOD. The browser used an isolated Edge profile and forwarded only localhost GETs and explicit read-only preview or calculator requests. No provider refresh, model, backtest or order was started by handoff navigation.

The 390 px Costs handoff kept VOD selected. A manual cents-based scenario displayed R292.54 estimated costs and R707.46 projected net in the first two rows. The fee and indicator disclosures opened independently, and the document remained 390 px wide. Local captures are `runtime/r17-before-desktop.png`, `runtime/r17-after-desktop.png`, `runtime/r17-after-mobile.png` and `runtime/r17-mobile-calculated-costs.png`. Changes were served as static assets by the running dashboard. The 22 focused tests, JavaScript syntax checks and 54 protected-artifact checks passed.

The full offline suite repeated R16's four failures, 22 errors and one skip across 2,261 tests. Rollback is a revert of the UI commit and a browser reload. Existing sessions and stored research persist. The next unified milestone is R18 integrated reliability and handover.
