# Versioned Swing EMA20 reclaim window — 11 November 2026

The daily Strategy Radar uses new technical profile 1.1.1
(`swing-ohlcv-wilder-v2`): a close-back-above-EMA20 reclaim counts if it
occurred on any of the latest three sessions. The frozen 1.1.0 feature snapshot
and 1.2.0 shadow policy remain on their prior one-session input; no historical
record is reinterpreted. The UI combines breakout and reclaim into one
three-valued OR trace row, matching the existing setup rule.

Validation: `.\.venv\Scripts\python.exe -m unittest test_swing_technical
test_swing_policy test_strategy_radar_swing test_strategy_radar_context
test_strategy_radar_integration test_strategy_radar_contracts test_radar_releases
test_strategy_profiles_api test_strategy_profiles` passed (85 tests).
`node --check static/js/strategy-radar.js` and the merged-rule
PASS/UNKNOWN/FAIL checks passed. No exact-profile fill backtest is available
for 1.1.1, so the Radar skips the legacy fill-run scan for this version. The
actual dashboard was not restarted, so M6 remains partial. This change
establishes no forecast accuracy or profitability.
