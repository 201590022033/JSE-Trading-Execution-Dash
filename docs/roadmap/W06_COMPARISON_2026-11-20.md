# W06 exact daily comparison · 20 November 2026

VOD was evaluated first. MTN followed after the B03 execution path was verified. Both comparisons use the retained 4 May–18 November 2026 window and ETF_STX40. The cutoff is 19 November at 14:14:26 SAST. Each instrument uses the same selected Zebra fields, decision dates, hypothetical fills, costs, and sizing across its variants.

| Variant | Definition |
| --- | --- |
| A | Exact daily v1.1.2 rule unchanged. |
| B | Same rule and stop geometry with breakout required instead of breakout or reclaim. |
| C | W05 default breakout/pullback with weighted rank. |
| D | Same W05 rules with equal weights. |

The engine uses the first later completed close, a three-session horizon and 2R target, R1,000,000 starting cash, R100,000 maximum notional, R5,000 risk budget, 8 bps brokerage per leg with R60 minimum, 20 bps spread and 5 bps slippage per leg. Net R divides net realised P&L by initial price risk at the actual hypothetical entry. Drawdown is measured from marked account equity. The realised-net and cost columns cover closed trades. Any open position remains marked.

The retained field receipt clocks are real. Historical replay availability is reconstructed. The point-in-time receipt-window count is shown separately. The common decision window uses 99 observed warmup sessions and reserves the last three observations for exits, matching the existing exact VOD review. Earlier and later are independent replay cohorts split by decision session with the same prior context and later exit bars. Quality rows are independent cohorts using the W05-labelled common daily source evidence. A row marked INSUFFICIENT applies to every metric cell in that row.

The retained [comparison artifact](../../artifacts/research/radar-exact-daily/w06-comparison.json) records source priorities, selected and alternate values, acquisition clocks, raw hashes, signal ranks and actual replay receipts. VOD A reproduced the previously retained signal count, trade count and realised P&L.

## VOD

139 qualified sessions. 1 audited 100-session window(s) met the original receipt cutoff. Shared decision window 2026-09-22 to 2026-11-13 (37 sessions). Quality by decision session: PARTIAL 37.

### Full window

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A | 4 | 3 | 3 | 33.33 | -0.44 | 1902.68 | 1227.08 | 0.09 | 1, 3, 3 | GAP_STOP 1, HORIZON_CLOSE 2 | INSUFFICIENT |
| B | 3 | 2 | 2 | 50.00 | 0.26 | 2594.87 | 768.69 | 0.05 | 3, 3 | HORIZON_CLOSE 2 | INSUFFICIENT |
| C | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| D | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |

### Earlier and later

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A earlier (2026-09-22 to 2026-10-16) | 2 | 2 | 2 | 50.00 | -0.60 | 2489.33 | 922.37 | 0.09 | 1, 3 | GAP_STOP 1, HORIZON_CLOSE 1 | INSUFFICIENT |
| A later (2026-10-19 to 2026-11-13) | 2 | 1 | 1 | 0.00 | -0.06 | -300.86 | 326.60 | 0.08 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| B earlier (2026-09-22 to 2026-10-16) | 1 | 1 | 1 | 100.00 | 0.64 | 3181.52 | 463.98 | 0.02 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| B later (2026-10-19 to 2026-11-13) | 2 | 1 | 1 | 0.00 | -0.06 | -300.86 | 326.60 | 0.08 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| C earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| C later (2026-10-19 to 2026-11-13) | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| D earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| D later (2026-10-19 to 2026-11-13) | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |

VOD A and B had positive net P&L in the earlier cohort and negative net P&L in the later cohort. C and D had their only trade in the later cohort. MTN had no trades in either cohort. These samples are too small to establish stability.

### Data quality cohorts

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A PARTIAL (37 sessions) | 4 | 3 | 3 | 33.33 | -0.44 | 1902.68 | 1227.08 | 0.09 | 1, 3, 3 | GAP_STOP 1, HORIZON_CLOSE 2 | INSUFFICIENT |
| B PARTIAL (37 sessions) | 3 | 2 | 2 | 50.00 | 0.26 | 2594.87 | 768.69 | 0.05 | 3, 3 | HORIZON_CLOSE 2 | INSUFFICIENT |
| C PARTIAL (37 sessions) | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |
| D PARTIAL (37 sessions) | 1 | 1 | 1 | 0.00 | -0.11 | -421.32 | 458.58 | 0.11 | 3 | HORIZON_CLOSE 1 | INSUFFICIENT |

### Score buckets

| Variant | Rank band | Signals | Closed | Target reach % | Avg net R | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| C | 0–<20 | 0 | 0 | — | — | INSUFFICIENT |
| C | 20–<40 | 0 | 0 | — | — | INSUFFICIENT |
| C | 40–<60 | 0 | 0 | — | — | INSUFFICIENT |
| C | 60–<80 | 1 | 1 | 0.00 | -0.11 | INSUFFICIENT |
| C | 80–100 | 0 | 0 | — | — | INSUFFICIENT |
| D | 0–<20 | 0 | 0 | — | — | INSUFFICIENT |
| D | 20–<40 | 0 | 0 | — | — | INSUFFICIENT |
| D | 40–<60 | 0 | 0 | — | — | INSUFFICIENT |
| D | 60–<80 | 0 | 0 | — | — | INSUFFICIENT |
| D | 80–100 | 1 | 1 | 0.00 | -0.11 | INSUFFICIENT |

These buckets are too thin for calibration. Weighted and equal-weight ranks do not change the entry gates. Their hypothetical trades are therefore the same.

## MTN

The earlier B03 smoke used the requested range with additional prior history for warmup. W06 uses the same short decision window as the VOD exact review, so the earlier B03 trade count does not apply here.

139 qualified sessions. 1 audited 100-session window(s) met the original receipt cutoff. Shared decision window 2026-09-22 to 2026-11-13 (37 sessions). Quality by decision session: PARTIAL 37.

### Full window

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| B | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| C | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| D | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |

### Earlier and later

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| A later (2026-10-19 to 2026-11-13) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| B earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| B later (2026-10-19 to 2026-11-13) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| C earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| C later (2026-10-19 to 2026-11-13) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| D earlier (2026-09-22 to 2026-10-16) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| D later (2026-10-19 to 2026-11-13) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |

VOD A and B had positive net P&L in the earlier cohort and negative net P&L in the later cohort. C and D had their only trade in the later cohort. MTN had no trades in either cohort. These samples are too small to establish stability.

### Data quality cohorts

| Variant / cohort | Signals | Entries | Closed | Win % | Avg net R | Net ZAR | Costs ZAR | Max DD % | Sessions held | Exit reasons | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| A PARTIAL (37 sessions) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| B PARTIAL (37 sessions) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| C PARTIAL (37 sessions) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |
| D PARTIAL (37 sessions) | 0 | 0 | 0 | — | — | 0.00 | 0.00 | -0.00 | — | None | INSUFFICIENT |

### Score buckets

| Variant | Rank band | Signals | Closed | Target reach % | Avg net R | Evidence |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| C | 0–<20 | 0 | 0 | — | — | INSUFFICIENT |
| C | 20–<40 | 0 | 0 | — | — | INSUFFICIENT |
| C | 40–<60 | 0 | 0 | — | — | INSUFFICIENT |
| C | 60–<80 | 0 | 0 | — | — | INSUFFICIENT |
| C | 80–100 | 0 | 0 | — | — | INSUFFICIENT |
| D | 0–<20 | 0 | 0 | — | — | INSUFFICIENT |
| D | 20–<40 | 0 | 0 | — | — | INSUFFICIENT |
| D | 40–<60 | 0 | 0 | — | — | INSUFFICIENT |
| D | 60–<80 | 0 | 0 | — | — | INSUFFICIENT |
| D | 80–100 | 0 | 0 | — | — | INSUFFICIENT |

These buckets are too thin for calibration. Weighted and equal-weight ranks do not change the entry gates. Their hypothetical trades are therefore the same.

## Limits

All cohorts are under 30 closed trades. The run is descriptive and does not establish a robust edge or calibrated probability. It makes no adoption decision. No protected evidence was written.
