# B03 · Exact cash-share replay from Backtest Lab

19 November 2026

The Backtest Lab can submit a watched share and an exact compatible daily cash-share strategy version to the existing Backtester work roster. This step implements H1 selected-share research. The family remains explicit on every job and saved result. Existing dedicated sector hypothesis workflows retain their own research contracts.

- The exact Radar v1.1.2 setup trace uses its retained review's hypothetical research replay assumptions. The strategy still leaves trade planning to the operator.
- Swing v1.3.0 uses the existing pinned baseline component configuration and component replay.
- Swing v1.3.1 and the three daily VCP, box-breakout and pullback approximations use the existing Zebra mixed-source Lab evaluator and its existing replay engine.
- Other registered versions appear with a reason in the unavailable list. Historical technical traces, canonical paper and per-signal shadow outputs retain their original contracts.

The worker reads Zebra-selected fields and applies the B04 policy for each evaluated session. The B03 branch depends on B02 for the saved-results index and B04 for benchmarks. If B04 is absent, the selector and submission route explain the dependency. Result details disclose cost and sizing assumptions, quality, exact profile and original position of missing data. The replay uses completed qualified observations and flags any gaps. A gap can hide a stop. Missing Open or activity stays unavailable. All fills and costs are hypothetical. Results with fewer than 30 closed trades carry the small-sample label.

## Existing VOD job

The earlier explicit VOD request `r04-signoff-20261119-vod` completed at 09:21:30 SAST on 19 November. It used the same Backtester roster and invoked `run_component_learning.py --instrument VOD --cycles 1`. Its retained VOD status is under `runtime/local-backtest/component-learning`. That older request shape and runner are preserved. B03 introduces a separate job kind for the requested identity/range and publishes a new content-addressed file in the existing `lab` folder.

## Verify and revert

After approved integration of B02, B04 and B03, open Backtest Lab, choose MTN, and use **Run a backtest for this share**. Select a daily cash-share version and a historical date range, then submit. The status moves through queued, running and complete, or shows the retained failure reason. Open the saved result and expand **Details** to verify the chosen version, input coverage and assumptions. Older results remain available.

To remove B03, revert its commit and restart only the dashboard after approval. Keep the retained journal and saved reports. This isolated branch did not launch or restart the running dashboard.
