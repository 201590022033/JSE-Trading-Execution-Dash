# Zebra field-level replay and technical research — 5 November 2026

The versioned field/window reader and `scripts/backtest_lab_zebra_v2.py` now feed a frozen multi-instrument report into the existing Backtest Lab. They do not modify the earlier hash-pinned evaluator or engine. Individual cells retain the source, actual capture time, source hashes, alternatives and revisions from the retained Zebra merger. HLC, close-only and full OHLCV capability are distinguished. The field endpoint exposes these rows and the Technical Intelligence tab displays close-based 20-session statistics and source details. The endpoint shows up to 600 recent observations per request.

Known exchange-session gaps and missing indispensable fields split windows; for dates outside the reviewed 2026 calendar, uninterrupted weekdays and weekends remain available, but an unexplained weekday gap splits the window rather than assuming a holiday. Replays select one complete OHLCV segment per instrument per report; `--segment-index` selects an earlier eligible segment without joining across gaps. The engine does not invent missing fills. The selected and eligible windows, coverage and field lineage are recorded in the frozen report. Historical availability is reconstructed, and corporate actions, source adjustment semantics and hypothetical execution costs remain stated in its limitations.

Sector benchmark routing uses the current research classification for a sector ETF where present, otherwise STX40, otherwise stock-only. These are current research proxies, not independently dated historical sector membership: a dated membership history is not yet available. The historical selection is therefore explicitly labelled rather than presented as a historical fact.

## Observed replay

Command: `.venv\\Scripts\\python.exe scripts/backtest_lab_zebra_v2.py --instrument SASOL --instrument BTI --output-dir runtime/local-backtest`.

Frozen run `84d49e8402c94416b13e7fa791f01048de2e39afe49ccda26529cf8e03833c67`, grade `ASSUMPTION_LIMITED`, replayed both instruments from 29 December 2025 through 3 November 2026. Each strategy evaluated 328 stock-days. Swing raised 7 signals and closed 5 trades; VCP 0 and 0; box 2 and 1; pullback 8 and 8. The Lab read and verified the new report. On the same input the old source-continuity rule rejected 5 of 328 stock-days for each of the three video-derived strategies, including one otherwise eligible box signal. BTI's 214 close observations were 209 IRESS and 5 ShareData; SASOL's 214 were ShareData. These comparisons do not establish a profitable strategy.

The running Technical Intelligence panel was checked in the browser: SASOL's latest retained close was R265.50 on 3 November, with source, receipt, alternatives, close-based statistics and the STXRES proxy shown. Backtest Lab loaded an earlier report from this v2 implementation and displayed its limitations. Its list of 25 frozen reports responded slowly on the local machine; historical capture loading also has noticeable latency.

## Verification and remaining limits

The isolated offline runner reported `Ran 1803 tests in 135.369s` and `OK`; it excludes five manual online/provider probes. After the final segment-selection change, the focused field/replay and existing backtest suites ran 37 tests, `OK`. JavaScript syntax was checked. All 10 files pinned by the existing prospective plan matched before the final changes, which do not touch those files. A broader, independently sourced dated sector-membership history, performance tuning, and component-level learning remain subsequent work. A current proxy must not be read as historical membership.

Rollback: stop using the v2 runner and the field endpoint; prior replay, snapshots and all source captures remain intact.
