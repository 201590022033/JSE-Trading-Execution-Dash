# Strategy Radar hierarchy

1. **Dashboard and decision card:** visual radar, selected share, manual product-aware plan, investigation actions, data and strategy status.
2. **Watches and strategy selection:** canonical Top 5 and at most one manual pin in the visible radar; grace/history records remain retained outside the live choices. Versioned profiles, durable lifecycle and grace period.
3. **Deterministic evaluation:** daily context plus separately defined intraday component rules; pass/fail/unknown traces, threshold proximity and source-linked evidence.
4. **Trade-plan calculations:** product metadata, broker-field units, quantity, stop and target geometry, risk, costs and user assumptions. Unsupported fields do not become invented values.
5. **Data layer:** daily Zebra and separately timestamped intraday bars/quotes; adapters for available public/API sources and optional read-only OST/IRESS captures. Manually uploaded ViewPoint CSVs remain hash-bound raw evidence until units and bar boundaries are verified; preserve field-level lineage and bounded cache.
6. **Operations:** quiet scheduler, source health, durable alert history, desktop and dashboard notifications, controls and recovery.
7. **Context and advice:** existing sector/benchmark, SENS/news, fundamentals, peer cases and explicit LLM desk. These explain or inform research and cannot silently become compulsory quote gates or order actions.

Data travels upwards from sources to evaluation and the decision card. User selections travel down through typed interfaces; no broker write path exists. Retain old dashboard and research APIs as compatibility boundaries. The existing event radar is separate from the new strategy radar but can supply cited event context.
