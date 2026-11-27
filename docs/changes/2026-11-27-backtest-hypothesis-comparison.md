# Backtest Lab hypothesis comparisons

The local Lab accepts independent hypothesis and exact strategy-version selections. The data preview checks daily OHLCV, the pinned sector ETF or broad-market reference, 99 warm-up observations, completed dates and the context required by each cell. Eligible hypotheses use the same longest usable common window. The preview identity binds the evidence and selection to a deduplicated job in the existing Backtester roster. A changed preview requires review again. Report files use the existing immutable Lab format and saved index.

| Hypothesis | Daily cash-share rule |
| --- | --- |
| H1 | Exact base strategy, pinned share benchmark |
| H2 | Positive prior five-observation returns in both the mapped resource proxy and USD/ZAR. AGL and BHP use STXRES. Sasol uses Brent. |
| H3 | Held pending a dated company-to-driver mapping and exact external-demand runner |
| H4 | Held pending dated shocks, sector-recovery evidence and exact reclaim runner |
| H5 | Held pending a currency product, cost and macro-impulse runner. The retained gross price study remains accessible. |
| H6 | Gold-share overlay for GFI and RNG. Positive aligned USD gold and ZAR-converted gold returns. The cash-share trades and volume belong to the selected share. |
| H7 | MTN or VOD with positive prior five-observation return in the other share and the existing STX40 benchmark |

H2, H6 and H7 are versioned exploratory daily overlays on exact base triggers. They use earlier completed dated references, retain rejected triggers and resimulate fills, cash, exits and fees. The resource ETF is a diversified exposure proxy that can include the selected share. Rising USD/ZAR is a declared directional research assumption. The overlays carry reconstructed historical availability and current reference mappings. They have no intraday confirmation, event conditioning, corporate-action verification or forward-validation claim.

Daily gaps show a read-only validation preview with the exact symbol, range and missing sessions covered. The confirmed file goes through the existing daily import endpoint when it is enabled. Separate five-minute preparation delegates recent exports to the installed ViewPoint request and receipt files only on explicit action. A ready session requires 96 qualified five-minute OHLCV bars in the retained cache. Earlier sessions and partial or unavailable exports support a validated native CSV. Download and import acknowledgements require the updated collector code when that process is next started through its usual operating workflow.

The selected-share result opens on matched net return, drawdown, trades, ledger costs and equity. Saved metadata includes dates, assumptions, source clocks, exclusions, unavailable cells and rule evidence. Single-share results use single-share scope. Radar exact links consider H1 cells for the exact profile and retain support for older reports.

## Verification

The isolated Edge workflow submitted a real retained-data AGL comparison, reached Step 4, and reopened the immutable result at 390 px. The matched window was 15 November 2021 to 9 November 2026 with 1,245 sessions and 99 required warm-up observations. STXRES was the pinned benchmark. AGL selected fields were from ShareData, with EODHD and Yahoo alternatives. The preview recorded at least one field disagreement on 1,231 sessions.

| Exact Swing version | H1 net and closes | H2 net and closes | H2 triggers filtered |
| --- | --- | --- | --- |
| 1.1.2 | −R34,563.59 / 27 | +R9,024.09 / 6 | 33 |
| 1.3.0 | −R49,996.37 / 18 | +R17,760.36 / 4 | 15 |

The isolated report hash was `75063095476677b3f8190daa8f1f7f22168783fe1bd921976dc7d5e4b2450fbf`. Both H2 arms had fewer than 30 closed trades. H5 reported the missing currency runner in both versions. The simulated queue exercised duplicate submission, acknowledged stages, sign-in and partial-export handling, validated uploads, and full coverage before Ready. No attended source export was used.

All 54 protected checks passed. The broader offline suite ran 2,321 tests with five skips and the existing momentum-target error involving the unsupported `stop_limit_bps` argument. The error reproduced with the parent checkout's Lab blueprint.

See [ADR 0105](../adr/0105-backtest-lab-hypothesis-comparisons.md).
