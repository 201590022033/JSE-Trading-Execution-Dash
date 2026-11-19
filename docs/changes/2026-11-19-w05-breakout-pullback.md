# W05 breakout and pullback research — 19 November 2026

The new research family is breakout_pullback_daily_research v1.0.0. It is registered for exact research lookup and runs through the deterministic evaluator and existing component replay engine.

- The evaluator reads Zebra-selected completed daily fields, freezes the original breakout level, and classifies the pullback and resumption sequence. It returns rule states, weighted and equal-weight scores, field receipt clocks, alternate-provider volume sensitivity, and coverage labels. Gaps within the configured allowance remain eligible. Longer verified gaps reset indicator windows. Dates outside the reviewed exchange calendar retain observed-session order with partial coverage.
- The RSI adapter calls the frozen calculation at period 14. Other periods seed the gain and loss averages and reuse the existing EMA with an equivalent Wilder smoothing factor. ATR and Ichimoku use their existing calculators.
- Replay uses the existing component engine for sizing, costs, fills and exits. The engine requires native execution fields. A missing decision-time field stays unavailable. A retrospective run explicitly declares reconstructed availability and retains the actual acquisition clocks.

## Verification

Run python -B -m unittest test_breakout_pullback in the W05 worktree with the project virtual environment. The tests cover all six states, RSI parity at 14, another period with a hand-calculated result, gaps, expiry, prefix stability, alternate volume, and both scoring schemes. They reproduce a hash of the existing Swing v1.1.2 output from the base branch and replay a synthetic trade through the component engine.

The read-only retained smoke check used the frozen VOD exact-review cutoff and 139 selected VOD and ETF_STX40 sessions from 4 May through 18 November. The source hashes reproduced the retained audit. The new family produced 108 WATCHING, 14 BREAKOUT_SEEN, 10 IN_PULLBACK_ZONE, three EXPIRED, two INVALIDATED and two TRIGGERED observations. The three-session replay reported two closed trades using reconstructed availability and the same hypothetical cost assumptions as the exact VOD review. This checks the code path and leaves comparison and calibration to W06.

The score is a research rank. Native OHLC and activity admission are reported separately from setup coverage. W06 and W07 retain their separate review gates. A rollback after approved integration can revert the W05 commit.
