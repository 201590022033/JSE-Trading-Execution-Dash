# R3a cash lifecycle replay — 21 October 2026

Owner authorized R3a. Independent research implementation is verified for local
review: pinned native Backtrader cash-long replay with2/3/4/5-session holds,
dated fee scenarios, split units, net dividend accrual/payment and complete daily
portfolio equity. Source/clock/scope/fee/action lineage and capability refusals
are explicit. No execution application imports or runtime wiring.

Research repository: `C:/Users/Deon/Documents/GitHub/jse-strategy-research`.
See its `docs/R3A_CASH_REPLAY.md`, ADR0005 and
`docs/evidence/r3a-synthetic-qualification.json`. Independent hand answers cover
cash/fee/gap/timing, protective ambiguity, splits and dividend receivables.
94 research tests pass (33 new +61 retained);11 synthetic proof scenarios pass.
54 protected execution checks and research dependency/compile checks pass.
Earlier research source/tests/tools/evidence and lock remain unchanged.

Legacy later-observable-close execution semantics remain untouched, separately
versioned from `cash-next-open-accrual/1`. Public tariff values are a sensitivity
scenario, with synthetic validity dates and explicit rounding; account/historical
invoice qualification is pending. No actual JSE calendar/action/price series or
performance acceptance is supplied. Unpaid dividends are receivables, not
spendable cash. Native fills enforce actual cash, with no second matcher.

Next proposed code card R3b: explicit policy/component interfaces. R3c is needed
for intraday claims; R4/R5 and accepted real discovery/data/time/cost qualification
remain P1 gates. R2b's real trial stays rejected; no new inference/price download.

R3a is locally committed and stops for review; no R3a push. Exact IDs are in the
task receipt. R12 remains sole ACTIVE/PARTIAL. Execution runtime/defaults/accounts/
providers/services/order connections/deployment stay unchanged. This execution
commit changes documentation only; last retained full safe-suite remains X5's
1484 pass, not a new R3a execution-suite run.
