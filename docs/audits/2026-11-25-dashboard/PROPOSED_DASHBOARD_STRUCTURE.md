# Proposed workspace structure

Keep the existing engines and routes. Introduce one predictable trader path and move diagnostics behind progressive disclosure. The component inventory maps existing features to these workspaces.

| Workspace | Default trader view | Contextual and advanced controls |
|---|---|---|
| Market Overview | Indices, freshness, Top 5, watch radar and current alerts | Daily/5m profile, benchmarks, detailed universe and source clocks |
| Market Intelligence | Visual calendar, today's SENS and related catalysts | Source details, warnings, provenance, candidate evidence, archived alerts, AI usefulness and weekly briefs |
| Share Research | Selected share, technical and fundamental coverage, relevant dates, sector and source age | Zebra histories, provider disagreement, bar quality, indicator and rule details |
| Strategy and Backtesting | Choose share → supported family → exact version and dataset → compare result | Existing advanced Lab panels, archived runs, experiments, training/holdout and AI desk |
| Trade Planner | Direction and product, entry/stop/target, estimated costs/size, validated paper draft | Tariff/units, trailing capability and stress cases |
| Trade Management | Clearly separate paper history, open simulations and replay | Logs, worksheet, position lifecycle and demo account journal |
| System Administration | Source, worker and lease health | Collection, configuration, provenance, experiments and local model diagnostics |

Use a visible research context containing immutable instrument ID, display label, product, strategy ID/version, timeframe, source/window, and optional run/plan ID. Consumer screens should either preserve that context or state why a field has to be reselected. End-user acceptance includes back navigation, two independent browser tabs, stale/missing inputs, and an explicit switch from research to draft planning. Support direct links without auto-writing a plan, increasing watch scope or generating orders. Preserve alternative benchmark and source provenance.
