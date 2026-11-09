# ADR 0095: Strategy Radar boundaries and scaffold

Status: accepted for Strategy Radar M1, 2026-11-06.

The existing dashboard and research APIs remain compatibility boundaries. A separate Strategy Radar workspace uses an inactive empty state until later milestones supply real watches and evaluations. It does not create an execution, monitoring, provider or model path. The existing event radar remains separate and may later provide attributed context.

`application/strategy_radar/contracts.py` defines typed planning boundaries for watch, quote, per-field bar observations, versioned strategy, rule trace, product plan and alert. Fields preserve source and receipt clocks, source identity, units and explicit availability; missing fields remain missing. A historical observation is not a current quote. Source clocks may be unknown rather than invented. Broker mappings require explicit evidence; product calculations are outside this scaffold. Contracts do not alter existing storage or public interfaces and are not yet connected to a service.

Later milestones should adapt existing Top 5, field-level Zebra, strategy registry, cost and news interfaces, rather than duplicate their implementations. Daily and intraday rules remain distinct. Monitoring must be separately enabled and deterministic, with no broker writes; advisory models use existing budgets. Optional source failures affect only dependent fields or computations. The mockup is visual guidance, not evidence of real prices, costs, units or validation.
