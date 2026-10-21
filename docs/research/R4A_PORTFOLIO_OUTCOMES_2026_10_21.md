# R4a portfolio metrics and frozen outcomes — 21 October 2026

Owner authorized R4a. Independent research implementation is verified for local
review: complete daily portfolio metrics, explicit risk-free/annualization and
period-end flow conventions, canonical Sharpe, economic/risk/cost/trade metrics,
frozen OutcomeContract and exact same-context baseline/predecessor comparisons.

Research repository: `C:/Users/Deon/Documents/GitHub/jse-strategy-research`.
See its `docs/R4A_PORTFOLIO_OUTCOMES.md`, ADR0007 and
`docs/evidence/r4a-portfolio-qualification.json`.171 research tests pass (37 new
+134 retained);7 metric examples,4 native accounting adapters,1 component adapter
and4 outcome states match independent expectations. Dependencies/compile and54
protected execution checks pass. Earlier research source/tests/tools/evidence,
shared-core0.4.0 and dependency lock remain unchanged.

Sharpe uses complete non-overlapping portfolio returns, aligned period risk-free
returns, sample excess-return SD and explicit annualization. Missing rates/context,
zero variance and sparse periods are unavailable. Deposits are removed; dividends
and receivables stay internal income. Net equity already includes costs, which
are not deducted twice. Gross cost add-back is the fixed executed path only.

OutcomeContract exclusively freezes exact references, threshold inputs and finite
uncertainty settings. Both baselines and all contexts must match; absent optional
predecessor is not applicable. A confirmation contract postdating produced results
is blocked. Paired session blocks provide descriptive time-block uncertainty,
not event-cluster or selection-adjusted proof. Criteria met means numeric review
required; research_gate_passed stays false. Fixture thresholds are illustrative,
not owner-approved success hurdles. No accepted strategy/release or actual market
performance is claimed; R2b's real-model trial stays rejected.

Next daily-track code card R4b: bounded campaign runner, durable attempts,
chronological isolation, screening/finalists and event/selection evidence. R3c
still needs genuine intraday/paired-market data; R5 and real source/data/time/cost
qualification still gate P1. No new model call or download.

Local commits only; no R4a push. Stop for review. R12 remains sole ACTIVE/PARTIAL.
Execution changes are six documentation pointers only; runtime/defaults/accounts/
providers/services/orders/deployment remain unchanged. No new full execution
suite run claimed; retained X5 full safe-suite evidence remains1484 pass.
