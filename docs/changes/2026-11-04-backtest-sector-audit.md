# Sector review of frozen Backtest Lab replay

Run: `ced796a36b5cfef53fb9a0c7455400122c8154b9cf6f88c96d6460a22605344f`. Grade: `ASSUMPTION_LIMITED`. Instrument count: 34.

Sector assignments use the current local research catalog, which was not frozen with this run. Unmapped instruments are shown separately; AGOGE is an ETF. The broad local Consumer label contains BTI alone in this run.

Values are sums of closed-trade net P&L from the original shared-cash portfolio replay, not standalone sector portfolios. They exclude any open-position mark-to-market, and capital competition and position sizing affect which trades occurred. Counts are trades; figures are hypothetical rand after the replayed costs.

| Sector | Instruments with trades | Swing | VCP | Box | Pullback |
|---|---|---:|---:|---:|---:|
| Consumer | BTI | 10; R32,295.78 | 5; R18,071.04 | 10; R22,493.93 | 7; R-33,162.38 |
| ETF - unclassified | AGOGE | 3; R-2,097.73 | 0; R0.00 | 1; R-1,879.57 | 0; R0.00 |
| Energy | SASOL | 6; R4,955.68 | 0; R0.00 | 0; R0.00 | 7; R-26,368.32 |
| Financial Services | ABSPJ, FSR, NED | 19; R-18,887.76 | 3; R15,354.58 | 20; R-16,812.70 | 27; R-25,948.11 |
| Industrials | BVT | 4; R-9,308.74 | 1; R-13,072.56 | 6; R-11,220.70 | 7; R-54,401.85 |
| Investment | REM | 8; R19,321.04 | 0; R0.00 | 5; R1,162.29 | 6; R8,405.25 |
| Luxury Goods | CFR | 5; R18,320.62 | 2; R-779.78 | 4; R-5,969.04 | 8; R-17,698.40 |
| Mining | AGL, BHP, GFI, IMPJ, KIO | 53; R11,160.97 | 7; R-6,395.69 | 9; R-8,758.94 | 52; R-91,725.51 |
| Retail | CLS, SHPJ, TFMJ | 8; R-2,163.40 | 2; R-8,795.55 | 17; R-20,876.55 | 15; R-39,660.15 |
| Technology | NPN | 2; R1,521.46 | 0; R0.00 | 5; R-1,200.81 | 3; R-8,965.24 |
| Telecommunications | MTN, VOD | 16; R-7,643.32 | 1; R-2,824.77 | 6; R-1,135.29 | 14; R-42,377.27 |
| UNCLASSIFIED | CSB, DTC, GPL, HET, HYP, LHC, MTH, NWL, PRX, RNG, TEX, TMT, TPC, VIS | 53; R-50,241.07 | 34; R-49,964.25 | 52; R-16,726.33 | 46; R-52,740.85 |

Unclassified in current catalog (15 of 34): AGOGE, CSB, DTC, GPL, HET, HYP, LHC, MTH, NWL, PRX, RNG, TEX, TMT, TPC, VIS.

## BAT (BTI)

| Strategy | Signals | Closed trades | Winning trades | Net P&L |
|---|---:|---:|---:|---:|
| Swing baseline | 15 | 10 | 6 | R32,295.78 |
| VCP daily approximation | 6 | 5 | 4 | R18,071.04 |
| Box breakout daily approximation | 12 | 10 | 7 | R22,493.93 |
| Pullback daily approximation | 10 | 7 | 2 | R-33,162.38 |

These are exploratory in-sample observations, not evidence that BAT represents its sector or that a sector-specific strategy is validated. No new model, hypothesis selection, replay or trading action was performed by this audit.
