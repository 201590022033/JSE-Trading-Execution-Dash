# M5 cross-sector context evaluation — 5 November 2026

The existing matched context replay was extended to BTI, FSR and ABSPJ, each with swing and pullback controls and three separate retrospective context filters in the training and inner-validation windows. Each filter reruns the same engine, starting capital and hypothetical costs as its paired control. The filters independently suppress a signal when the prior proxy return indicates falling Brent, falling sector ETF or rising USD/ZAR. Missing proxy data does not suppress the signal. The protected holdout was not used. Six new studies, 36 proxy-window replays and six matched event comparisons were retained under `runtime/local-backtest/context-research/`; no model calls or execution actions were made.

These are exploratory filters, not sector-optimized strategies. Sector ETFs are retrospective proxies: BTI uses STXIND and FSR/ABSPJ use STXFIN. Proxy histories were acquired later; source availability at the historical decision time is not established. Training and validation windows use the retained split with a six-session purge. Each instrument has 214 retained sessions in this split; no future price is inserted into a prior decision.

For all four instruments the training dates are 29 December 2025–2 July 2026 and validation dates are 13 July–2 September 2026. The later 11 September–3 November 2026 holdout was not used in these comparisons. Returns shown are hypothetical net trade P&L in rand, not a benchmark-adjusted return.

| Instrument | Family | Training control closed trades / net | Validation control closed trades / net |
|---|---|---:|---:|
| SASOL | swing | 2 / -R5,966.41 | 0 / no closed trades |
| SASOL | pullback | 3 / -R7,251.49 | 1 / -R4,470.23 |
| BTI | swing | 2 / -R1,452.80 | 0 / no closed trades |
| BTI | pullback | 1 / +R3,741.73 | 0 / no closed trades |
| FSR | swing | 1 / -R4,787.62 | 2 / +R9,258.88 |
| FSR | pullback | 2 / -R1,896.25 | 0 / no closed trades |
| ABSPJ | swing | 1 / -R2,693.56 | 0 / no closed trades |
| ABSPJ | pullback | 2 / +R137.15 | 0 / no closed trades |

The variation results caution against a universal rule. In BTI pullback training, the falling-Brent filter removed its only trade, a winner. In FSR swing validation, the sector filter left one trade at +R621.06 versus the two-trade control at +R9,258.88; the Brent filter left no closed trades. In ABSPJ pullback training, the rising-USD/ZAR filter left one trade at -R6,184.25 versus the two-trade control at +R137.15. Earlier Sasol pullback training produced +R5,065.22 for the rising-USD/ZAR filter versus -R7,251.49 for the control, but validation then had no filtered closed trade. These small results do not support promotion, causal conclusions or a claim of learned predictive skill.

No eligible recent event suppressed a signal in these studies. BTI had 18 retained context records; FSR and ABSPJ each had zero linked context records, so their event comparisons do not test the usefulness of issuer news. Finding and retaining those sources with actual timestamps is separate remaining work. The source availability constraint applies to event comparisons, not to the availability of Zebra prices for research.

Study hashes (content addressed): BTI swing `bdf0ca3480687b086e9113272ff65616d791b6ee695c200a81bce37ca50d4c5f`, BTI pull `dd89e541fa6ca7f2e0ac80cabb1aaea0f010440b7886f24c5731b802f3f6c58a`, FSR swing `3cca7af2d964ca7d983c664fc6cfeac3f3448dfcc33900c783df3dd7c2d49edf`, FSR pull `5d3eaa9f9e2d967a5bb9e7b63b64845f356c38e249f9eb2ab538f6cb5a82d3c5`, ABSPJ swing `7e5c68b107d3805cb9b5c8e9252628cf5cb63056c84f946146636df67a1985fa`, ABSPJ pull `c4ba1b0fa2c2db587fd7513bb42b44fb3c6222fb5eeeaa373384be05b09e8248`. Original Sasol studies are documented in `2026-11-05-sasol-context-research.md`.

Command for each combination: `.venv\\Scripts\\python.exe scripts/run_context_replay.py --instrument INSTRUMENT --family FAMILY --proxy-variants`. All six commands completed successfully. Each retained report's filename was checked against its SHA-256, and the baseline and candidate trade counts and results above were read from those reports. Rollback: retain the immutable local reports but do not use these experimental filters; no strategy default or live setting changed.
