# Sector review of frozen Backtest Lab replay

Run: `ced796a36b5cfef53fb9a0c7455400122c8154b9cf6f88c96d6460a22605344f`. Grade: `ASSUMPTION_LIMITED`. Instrument count: 34.

Sector assignments use the current research taxonomy and were not frozen with this older run. Unmapped instruments are shown separately; AGOGE is an ETF.

Values are sums of closed-trade net P&L from the original shared-cash portfolio replay, not standalone sector portfolios. They exclude any open-position mark-to-market, and capital competition and position sizing affect which trades occurred. Counts are trades; figures are hypothetical rand after the replayed costs.

| Sector | Instruments with trades | Swing | VCP | Box | Pullback |
|---|---|---:|---:|---:|---:|
| Consumer | BTI, GPL, NWL | 16; R30,847.90 | 16; R-10,899.99 | 17; R10,746.77 | 13; R-28,909.60 |
| Energy | SASOL | 6; R4,955.68 | 0; R0.00 | 0; R0.00 | 7; R-26,368.32 |
| Financial Services | ABSPJ, FSR, NED | 19; R-18,887.76 | 3; R15,354.58 | 20; R-16,812.70 | 27; R-25,948.11 |
| Funds | AGOGE | 3; R-2,097.73 | 0; R0.00 | 1; R-1,879.57 | 0; R0.00 |
| Healthcare | LHC | 4; R101.83 | 1; R45.60 | 5; R22,213.00 | 4; R-1,255.89 |
| Industrials | BVT, TPC | 6; R-20,204.29 | 3; R9,185.71 | 8; R-16,639.42 | 9; R-59,443.85 |
| Investment | REM | 8; R19,321.04 | 0; R0.00 | 5; R1,162.29 | 6; R8,405.25 |
| Luxury Goods | CFR | 5; R18,320.62 | 2; R-779.78 | 4; R-5,969.04 | 8; R-17,698.40 |
| Mining | AGL, BHP, GFI, IMPJ, KIO, RNG | 58; R39,988.41 | 10; R-185.70 | 12; R-4,967.68 | 53; R-101,597.86 |
| Real Estate | HET, HYP, TEX, TMT, VIS | 13; R-41,910.89 | 12; R-21,822.31 | 18; R-49,711.42 | 11; R-62,452.95 |
| Retail | CLS, CSB, MTH, SHPJ, TFMJ | 18; R14,732.31 | 3; R-8,249.27 | 24; R2,758.48 | 27; R-5,437.72 |
| Technology | DTC, NPN, PRX | 15; R-40,290.27 | 4; R-28,231.05 | 15; R-689.13 | 13; R-21,558.11 |
| Telecommunications | MTN, VOD | 16; R-7,643.32 | 1; R-2,824.77 | 6; R-1,135.29 | 14; R-42,377.27 |

Unclassified in research taxonomy (0 of 34): none.

## BAT (BTI)

| Strategy | Signals | Closed trades | Winning trades | Net P&L |
|---|---:|---:|---:|---:|
| Swing baseline | 15 | 10 | 6 | R32,295.78 |
| VCP daily approximation | 6 | 5 | 4 | R18,071.04 |
| Box breakout daily approximation | 12 | 10 | 7 | R22,493.93 |
| Pullback daily approximation | 10 | 7 | 2 | R-33,162.38 |

These are exploratory in-sample observations, not evidence that BAT represents its sector or that a sector-specific strategy is validated. No new model, hypothesis selection, replay or trading action was performed by this audit.
