# Real historical swing funnel — 29 October 2026

The local Backtest Lab now has a separate historical rule funnel. Run
`python scripts/backtest_lab_real_funnel.py --output runtime/local-backtest/lab-swing-funnel.json`
to regenerate it from the retained v3 dataset and the verified IRESS archive.
The server reads this derived file from `LOCAL_BACKTEST_REPORT_DIR`; its API is
read-only. It is a feature diagnostic, not a portfolio replay or live signal.

On the retained dataset, 600 Sasol IRESS bars from 5 June 2024 to 27 October
2026, paired with OST STX40 closing prices, yielded 550 evaluated stock-days
after 50 days of warm-up. The cumulative counts were 217 trend, 50 breakout or
reclaim, 29 momentum, 15 volume, 12 benchmark, 12 complete snapshot; 12 signals.
No evaluated stock-day lacked its benchmark endpoints. Signal counts were 0 in
2024, 5 in 2025 and 7 in 2026. The calendar and historical availability are
reconstructed/unverified and the source adjustment semantics remain unknown.
The issuer and benchmark are not combined into a fabricated OHLCV bar.

The separate observed-history replay adapter now accepts this source-bound
Sasol series without claiming a verified calendar, raw adjustment basis or
corporate actions. It treats provider-observed dates as the replay schedule,
assumes availability at the next UTC day, and applies no corporate actions.
This is **ASSUMPTION_LIMITED** retrospective research, not live price or a
validated strategy. OST benchmark closes remain separate; their raw export is
reparsed and matched before use. No OHLC fields are manufactured. Generate a
replay with `python scripts/backtest_lab_run.py --dataset
runtime/local-swing-data/latest.json --output-dir runtime/local-backtest`.
Repeated runs gave the same report hash
`6c1542deaa96a2823f9d565b1d790f8e2113d2453edf5186c3a4e362de5bae43`.
Swing produced 12 signals and 10 hypothetical closed trades; VCP 0/0, box 0/0,
and pullback 16/14. All are single-stock exploratory samples. The desk bucket
marks fewer than 30 trades inconclusive.

Trading Strategies and Technical Intelligence provide a read-only link to the
historical funnel and lab. They do not replace the current instrument screen,
production ranking or trading input. The four-day current-input freshness checks
still apply to live technical previews; the saved historical report does not
become a current quote merely because it is read later. The research repository's
full zebra panel and wider instrument universes are not yet wired into replay.
The app must load the new code to expose the new routes. Browser viewport checks
remain outstanding. Focused verification: 36 tests passed for the lab, source
resolution, technical snapshot and strategy registry modules. The offline
suite `python scripts/run_tests.py` ran 1,657 tests successfully in 127.214s.
