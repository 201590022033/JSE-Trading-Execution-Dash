# Dashboard unavailability sweep

The initial source inventory found 330 literal occurrences in 18 JavaScript and template files. These include fallback text and status values. Live checks determine which messages represent active failures.

| Area | Evidence and status |
| --- | --- |
| Radar and System · ViewPoint export | On 19 November at 14:37:54 SAST, the worker reported partial coverage. ETF_STX40 failed at `verify volume` with `TimeoutError`. The collector now checks the switch state before toggling, and System shows the stage and exception for each failed instrument. The original failure mechanism is plausible from the code and still needs confirmation in a live export. The signed-in collector needs its next normal launch to load the fix. |
| Radar · sources and indicators | Inspect quote origin and bar/receipt clocks per share. Separate data gaps, unsupported fields, stale inputs and request failures. |
| Dashboard and tab-status views | Trace the shared freshness, market data and research endpoints behind their fallback text. |
| Backtest Lab, Zebra and component research | Identify missing exact-version results, unqualified inputs and read failures through separate evidence. |
| Portfolio, costs and onboarding | Check missing inputs against provider evidence and recorded broker terms. |
| Model and research views | Check tool mapping, eligibility, retained outcome coverage and service failures. |

Keep the displayed evidence and underlying failure together. Verify fixes against the running dashboard or the relevant worker, and record any prerequisite for live acceptance.

Live recovery at 14:40:57 SAST on 19 November. A targeted retry through the existing signed-in collector imported 361 native STX40.JSE rows. The cache confirmed a completed 14:35 SAST bar with volume 20 and raw SHA-256 `1e832288b70c11568b77f3ac8a43d9829f39baf50983111c4b16a2f76531d80a`. The retry establishes recovery for this export. The switch fix remains pending live verification on the next collector launch.

The running monitor reported a full collection check at 14:51:42 SAST, including an ETF_STX40 import. NTU was already retained. The signed-in worker still runs its earlier code. Its launcher owns the Edge context and closes it on worker exit.

After the authorized OST and dashboard restart, the updated collector imported 398 native STX40.JSE rows at 16:54:52 SAST. The cache verified the completed 16:50 SAST bar with volume 606 and matching raw SHA-256 `205e5f4db7df68d73e23037e95fad48d370b1a051a2ee7e807fd51cd461d561f`. The 16:55:27 monitor check reported five imports, NTU already retained, and no final instrument errors. This verifies the export path after deployment. The run did not separately record whether the slider reset branch was needed.
## Shared freshness follow-up

The health endpoint and all seven distinct tab status routes returned HTTP 200. The shared freshness view now retains the last successful source clocks when a refresh fails and flags when that snapshot was checked. A public news response with no success clock reports unknown freshness. The view uses the existing 30-minute aggregation rules for complete retained ViewPoint five-minute buckets and labels derived evidence explicitly.

After the dashboard-only restart, the live freshness response reported AVAILABLE with zero errors in 15.1 seconds and returned derived 30-minute evidence for three watches. The other two still need investigation or complete aligned inputs. After-hours five-minute bars, older Sasol daily receipts, and missing manual quote evidence remain separate source gaps. Broker-dependent and research acceptance items remain open.
