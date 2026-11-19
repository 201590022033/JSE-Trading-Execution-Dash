# R10 strategy-linked trade card — 19 November 2026

Base revision `f51a25a`. The existing manual trade card displays the selected strategy's exact instrument, product, profile, version and timeframe. Entry and volume use the retained evaluation trace. The five-minute card shows the existing shadow stop, target and three-bar exit rule. Daily v1.1.2 displays the observed-session research horizons and explicitly leaves stop, target and holding duration unspecified. Manual scenario values remain independently editable.

The card and Backtest Lab handoff share the same evaluation identity. The handoff reads the current selection at click time. A returned five-minute comparison must match the instrument, strategy, version and timeframe and carry research-only metadata before its result appears. Identical overlapping Radar polls now share the in-flight refresh, so a five-minute evaluation taking longer than 30 seconds can still render.

The live browser showed VOD `jse_swing_3_5d` v1.1.2 on both the daily card and Backtest Lab handoff. It disclosed the missing exact-version daily comparison. The five-minute card and handoff both showed VOD `intraday_5m_research_v1` v1.0.0. The browser check used an isolated Edge profile. The running dashboard served the updated static asset without a server restart. The full-history comparison exceeded the 95-second browser verification window and subsequently retained report `e2e8d1ae1dc8bcefd05f6f8babf44a7201c5b7d534cc54840e7709216dc76c81`. Its verified SHA-256, VOD identity, v1.0.0 and five-minute interval matched the handoff. At an assumed round-trip cost of 10 bps it retained two candidate samples and 12 baseline samples. Browser rendering of the eventual response remains unverified.

The 31 focused tests, JavaScript syntax check and all 54 protected-artifact checks passed. The full offline runner executed 2,260 tests and reported the same four failures, 22 errors and one skip as R09.

Rollback is a revert of the R10 commit and a dashboard page reload. The existing strategy definitions, recorded research and trade simulation remain available. R11 starts with verifying product-specific costs and manual OST input units.
