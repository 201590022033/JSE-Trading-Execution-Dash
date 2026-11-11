# ADR 0102: Version the three-session EMA20 reclaim

The existing Swing technical feature contract 1.1.0 is consumed by persisted
research records and the separate 1.2.0 shadow policy. Changing its reclaim
calculation in place would make old and new records share an identity despite
different semantics.

Add technical profile 1.1.1 with feature version
`swing-ohlcv-wilder-v2`, where an EMA20 reclaim is a close crossing above EMA20
on any of the latest three sessions. Keep 1.1.0 and its one-session calculation
available and unchanged. The Strategy Radar selects 1.1.1; the paper worker and
1.2.0 policy remain pinned to 1.1.0.

This is a research-rule version, not evidence of improved accuracy or
profitability. Historical records are not relabelled, and Radar M6 remains
partial pending its existing dashboard verification.
