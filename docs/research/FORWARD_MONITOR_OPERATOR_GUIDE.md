# Forward research monitoring — local operator guide

The registered BTI/SASOL comparison uses the original frozen plan and its separate hash-verified dependency supplement. The read-only Backtest Lab view shows the number of observed sessions, recorded strategy states, partial states and descriptive later close observations. The existing local daily swing collector now runs the monitor after source refresh; opening the dashboard does not start a model, collector or trade. The installed Windows task was observed at 07:30 SAST; its next actual successful run remains to be observed.

After obtaining fresh completed daily sources into Zebra, run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/monitor_sector_forward.py --capture
.\.venv\Scripts\python.exe scripts/monitor_sector_forward.py
```

The first command retains an immutable daily input snapshot and the original frozen strategy rules' `SIGNAL`, `NO_SIGNAL` or `PARTIAL` states for each available instrument. The second only reports status. Captures retain their original source and acquisition times. The monitor does not backfill sessions that occurred before registration or arrive out of sequence. A later revision does not rewrite a frozen decision. Daily 3/4/5-observation close changes are descriptive. Separately, the frozen daily engine replays eligible signals with the plan's stops, targets, horizon, cash and costs across each complete consecutive observation segment. Each segment has a separate starting cash ledger; do not add segments as a continuous portfolio. Missing observations remain visible, and partial decisions are not signals. The twenty-session decision window is bounded; later observations can still settle existing signals.

The collector writes a secret-free local `daily-forward-status.json` for its forward step, and the Lab displays its latest outcome separately from the overall collector status. A damaged saved receipt marks only the affected instrument unavailable; independent instruments remain visible. A partial decision shows missing field counts from its own saved inputs. A later source does not retroactively change that decision.

Zebra's IRESS Time Series importer can retain the completed same-day OHLC after 17:20 SAST without modifying the earlier next-day archive:

```powershell
.\.venv\Scripts\python.exe scripts/import_iress_price_only.py --after-close 'C:\path\Time Series (SOL.JSE)_actual-download.csv'
```

The importer uses the real file write time; rounded provider volume is absent. A missing volume can make the current frozen volume-dependent rules `PARTIAL`; it does not remove other Zebra prices or prevent other instruments being captured. The source's finality remains unverified. Optional incomplete source histories do not cause orders or live execution. The local incoming collector accepts supported Time Series files; no new scheduled task was created.

The H1–H4 research families can use retained equity/sector histories and the existing experimental strategy/component reports. The Backtest Lab H1–H6 coverage panel distinguishes hash-verified component examples from separate FX/gold reference captures. One bounded NewGold component-learning cycle uses listed-ETF units and the original gold adapter; one USD/ZAR price-only study compares two breakout windows and three holding horizons using gross observed-price returns without fabricated volume or a broker product. Neither is validated performance. Sector context and retrospective studies are leads, not forward validation. The full H1–H6 autonomous feedback loop, a continuous prospective comparison and comprehensive dashboard handover remain to be completed.

The component runner supports `--family swing`, `box`, `pull`, or `vcp`. For example, `python scripts/run_component_learning.py --instrument BTI --family box --cycles 1` runs one bounded cycle without a cloud model. Families share the same instrument trial budget; `--status-only` reads retained status without a new trial. The deterministic fallback cycles through distinct supported components rather than repeatedly testing only the same filter. Gold's separate runner also offers `--status-only` and reconciles prior registered namespaces before allowing another trial.

Rollback: remove or disable the forward-monitor hook in `scripts/collect_swing_data.py`; retain the immutable plan, snapshots and receipts. The dashboard is read-only and existing frozen histories and broker settings remain untouched.
