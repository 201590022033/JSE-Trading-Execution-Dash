# R09 Sasol target comparison — 19 November 2026

Base revision `c26b23c`. The existing Sasol diagnostic and component replay tested the Swing research profile `jse_swing_3_5d` v1.3.0 with a 2R baseline and a 1.5R candidate. Only `target_r` changed. Both used the same 224 contiguous Sasol OHLCV observations from 29 December 2025 through 18 November 2026, STXRES sector-proxy closes, and R1 million starting cash. The retained study carries per-field source choices and alternatives, acquisition clocks and raw hashes for both instruments. Selected inputs came from EODHD, IRESS and ShareData. Missing benchmark observations remain unavailable to the benchmark rule. Availability is reconstructed and the study is retrospective.

| Measure | 2R control | 1.5R candidate |
| --- | ---: | ---: |
| Signals | 3 | 3 |
| Closed trades / wins | 3 / 2 | 3 / 2 |
| Unknown decision sessions | 49 | 49 |
| Gross closed P&L | −R3,719.57 | −R3,719.57 |
| Fees | R416.13 | R416.13 |
| Spread and slippage impact | R679.13 | R679.13 |
| Net closed P&L | −R4,814.83 | −R4,814.83 |

The same signals fired on 30 April, 5 June and 8 September 2026. All exits occurred at the three-session horizon, so neither target affected a fill. The cost assumptions were 8 bps fee per side with an R60 minimum, 20 bps spread and 5 bps slippage per side. Three observations are insufficient to infer target equivalence or validate performance. The 2R control remains the baseline.

The first replay uncovered that sorting JSON field keys could select a different receipt for the manifest. Explicit OHLCV field order fixed the issue. Replaying from the archived study then reproduced the original bytes and hash. The intermediate report is retained under the ignored `runtime/r09-audit` directory. The running Backtester list and detail endpoints returned the final two-trial study. Reconciliation verified the same signal sessions, identical input and cost identities, the sole configuration difference and gross-to-net arithmetic for every trade. All 32 focused tests and 54 protected-artifact checks passed.

```powershell
$study = '660e2f8f04d5f38fab16a9210c8cae7ea1501069e88e07337bb2ae370d957a3c'
.\.venv\Scripts\python.exe scripts/component_sasol_probe.py --replay-report "runtime/local-backtest/component-research/$study.json" --output-dir runtime/local-backtest/component-research
```

The full offline suite ran 2,260 tests with four failures, 22 errors and one skip in the broader provider/browser and tool-research paths. The periodic monitor was still running after the live check.

Rollback is a revert of the diagnostic CLI change. Keep the frozen study and market-data receipts. R10 starts with connecting the selected strategy and its version to the trade card.
