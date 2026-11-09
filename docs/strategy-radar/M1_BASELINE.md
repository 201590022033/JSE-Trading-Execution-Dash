# Strategy Radar M1 baseline — 6 November 2026

| Area | Verified current state and boundary |
| --- | --- |
| Dashboard | Existing Flask dashboard at localhost:5000; eight navigation buttons, with data-status descriptions from `static/js/tab-data-status.js`. Existing welcome shortcuts use `data-open-tab`. M1 adds an inactive, minimisable workspace and collapsible outer daily-import panel. |
| Top 5 | `application/opportunities/api.py`: GET `/api/v1/opportunities?limit=5`, POST refresh; default cash-equity research screen, no live execution. Ranking is retained research, not a quote. |
| Strategies | `domain/strategy/registry.py`, `application/strategy_profiles.py` and `/api/v1/strategy-profiles`; versioned profiles, not automatic intraday equivalence. |
| Daily Zebra | `application/opportunities/zebra_screen_data.py` selects available observations per field/session, with source and revision evidence; `zebra_field_windows.py` supplies segments. Other strict-consensus paths remain separate. |
| Quotes | `dashboard_feeds.py` uses public Yahoo chart data and short in-memory caching; 30-minute chart bars and delayed-public labels do not establish a durable multi-provider or verified live feed. `/api/market-intelligence/ticker` holds selections, not live prices. |
| Costs | `application/backtest_lab/share_cost_estimate.py` and `cfd_cost_estimate.py`, exposed by Backtest Lab; assumptions and product-specific evidence remain necessary. OST field units are not established by this scaffold. |
| Alerts | Existing dashboard calendar/event radar warnings and research clocks are separate. A Windows price-alert path is not verified. No new scheduler or notification is installed. |
| Reference | `assets/radar-mockup.png` depicts a large radar beside a plan/checklist and contextual actions. Its figures, product units and statuses are illustrative; proximity will follow the hierarchy, with developing setups nearer the centre. |

Before M1, `git status --short` showed modified AGENTS.md, backtest blueprint and target design, both roadmap files, run_target_design, dashboard and target-design JavaScript, dashboard template and test_target_design; untracked cost-aware replay note, Strategy Radar documentation and dashboard visual CSS. These are preserved. No reset or commit was made. The dashboard visual/navigation changes were already underway; they are not a completed radar.

Browser observation: the existing local dashboard was reachable. Status descriptions showed saved daily data and historical backtests, and an available news feed; those are observed interface states, not verification of a live market feed. Existing page loading may refresh its own feeds; M1 added no provider requests.
