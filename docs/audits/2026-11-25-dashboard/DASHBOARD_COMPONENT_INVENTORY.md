# Dashboard component inventory

Coverage refers to the live view sampled on 25 November. “Visible” is not execution coverage. Top-level navigation source is templates/dashboard.html:5.

| Existing location and component | Purpose and dependency | Observed state | Proposed home |
|---|---|---|---|
| Dashboard market/source strip, indices, session | Orient trader using retained index/market/source state | Initial unknown/unavailable; full source integrity unverified | Market Overview |
| Dashboard Strategy Radar, daily and 5m profiles, watch list, alert history | Watches, rule proximity, profile-specific retained bars, monitor receipts | Daily rendering and MTN selection observed; transient unavailable map; 5m execution unverified | Market Overview, with Share Research details |
| Radar checklist, evidence badge, indicators, momentum, relative volume, breakout/pullback, sources | Explain watch using versioned strategy and cache | Controls/cards visible; evidence loading persisted in sampled state; detailed calculations unverified | Share Research advanced |
| Radar plan editor, OST field mapping, fee and size readouts | Manual scenario using product/tariff contract | Long and short calculations verified; dynamic execution unverified | Trade Planner |
| Radar sector and issuer events/news | Contextual research using sources and benchmark mappings | MTN telecommunications/ETF_STX40 visible, retained sector loading observed | Market Intelligence / Share Research |
| Scan Top 5 and discovered watches, review/pin/shadow controls | Rank history; radar/store handoffs | Five ranked items and MTN technical handoff verified; watch mutations and shadow checks not exercised | Market Overview / Share Research advanced |
| Scan share and CFD estimators | Round-trip fee assumptions | Controls visible; overlaps planner economics | Trade Planner |
| Strategies profiles, Sasol refinement, historical AI/learning, experiment status | Read profiles and model/worker evidence | Three named profiles rendered; multiple unavailable fields; runtime dependency failures not traced | Strategy and Backtesting; diagnostics in System Administration |
| Backtest Lab share/hypothesis, saved index, exact replay, date window, strategy and result | Daily research, artefacts and queue | SOL and MTN selection, saved results and MTN form verified; SOL run blocked; H1 only | Strategy and Backtesting |
| Lab trades/chart, benchmark and research details, target/exit, tape, experiments, momentum, sector, prospective, FX, Zebra coverage, desk | Research diagnostics and immutable studies | MTN saved result and trade table visible; advanced functions not individually executed | Strategy and Backtesting advanced; Data Quality in Share Research |
| News feeds, SENS, sentiment, weekly brief, themes and issuer filters | Public stories, disclosure receipts, optional annotations | News and SENS rendered; briefing import and model feedback unverified | Market Intelligence |
| Anticipatory Radar, Research Calendar, macro health, event prep, warnings, archived outcomes, AI expectation panels | Source-backed dates, candidate evidence and advisory analysis | Calendar and future SARB cards visible; independent APIs 200; limited evidence and stale capture warnings visible | Market Intelligence |
| Technical analysis market pulse, price history, instrument technical screen, Zebra diagnostics | Selected share/history and benchmark | MTN handoff and screen observed; feed refresh and fundamentals unverified | Share Research / Market Overview |
| Portfolio/demo journal, account-linked trades, printable worksheet and paper affordances | Record or manage simulated/manual results | IG unavailable; worksheet code present; order and position lifecycle unverified | Trade Management |
| System monitor, work roster, source onboarding/uploads, provenance, local models and legacy status | Operator inspection and configuration | Rendered; failed receipts observed; no controls mutated | System Administration |

Legitimate overlap includes different source clocks, baseline versus newer strategy versions, and official versus advisory event records. Reuse the presentation and handoff contract while preserving those distinctions. Expand this inventory with per-panel live evidence before retiring or moving any component.
