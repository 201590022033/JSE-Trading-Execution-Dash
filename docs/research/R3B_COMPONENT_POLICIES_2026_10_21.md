# R3b independent component policies — 21 October 2026

Owner authorized R3b. Implemented and verified for local review in the independent
research repository: immutable role-specific entry/exit/volume/timing/initial-stop/
risk/cost-fill components and same-input controlled comparisons. Initial fixed,
percent, arithmetic mean true-range and completed-window structure stops freeze
from observable decision data. Entry/exit feature settings remain independent;
stop-risk sizing effects require a declared interaction.

Research repository: `C:/Users/Deon/Documents/GitHub/jse-strategy-research`.
See its `docs/R3B_COMPONENT_POLICIES.md`, ADR0006 and
`docs/evidence/r3b-component-qualification.json`.134 research tests pass (40 new
+94 retained);9 synthetic controlled comparisons match independent cash answers.
Seven frozen R3a results match exactly with policies disabled. Dependency/compile
and54 protected execution checks pass. No new model call or download.

A small opt-in research replay hook cancels protection on a close-based signal
exit and submits the market exit for next open. Native Backtrader still owns cash
and fills. Earlier protective fills and maximum time exits retain priority.
The strategy and request both enter policy-enabled replay identity. Prefixes are
split-aware without future back-adjustment. Unavailable/no-setup cases are retained.
Risk cash is an intent at known close-to-stop distance, excluding gaps/fees;
it is not a maximum loss guarantee or capacity claim. No arbitrary expressions,
trailing update, partial fill, intraday or derivative execution support.

Reuse shared-core0.4.0 StrategyComponent references; no shared schema update,
accepted StrategyRelease or execution evaluator is fabricated. Legacy execution
Wilder ATR/later-observable-close replay remains unchanged. Research ATR here is
explicitly separately versioned arithmetic mean true range. No scorer copy.

Next daily-track code card R4a: canonical metrics and frozen OutcomeContract.
R3c remains separately pending genuine intraday data/paired-clock qualification;
daily work can proceed independently under the prepared plan. R4b/R5 and real
discovery/data/time/cost evidence remain P1 gates. R2b's real trial stays rejected.

Local commits only; no R3b push. Stop for owner review; exact IDs in task receipt.
R12 remains sole ACTIVE/PARTIAL. Execution changes are documentation only; no
runtime/default/account/provider/service/order/deployment changes. Last retained
full execution safe-suite remains X5's1484 pass, not a new R3b full-suite run.
