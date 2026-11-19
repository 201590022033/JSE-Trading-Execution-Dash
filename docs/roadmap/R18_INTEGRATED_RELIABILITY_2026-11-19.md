# R18 integrated reliability and handover — 19 November 2026

R18 closes the unified reconnect and research roadmap. Base revision `f43c7bf`. This document and the implementation are tracked together in the R18 commit. The first outstanding-issues sweep follows R18, then the HR series resumes from its existing research briefs. The unified roadmap ends at R18.

## Archive delivery and recovery

The existing scheduled SENS bridge reads up to 12 pages of 500 records per archive kind in one invocation. When a kind needs more work, the bridge records a continuation in `runtime/sens-runtime-bridge-cursors.json` after delivery commits. Subsequent runs process the newest page as well as the older backlog. Record and receipt IDs and original clocks survive delivery. An immutable conflict rolls back the invocation. Hermes news transfer remains opt-in.

The fixture crossed 5,000 records, obtained a continuation, resumed after a new receipt arrived and copied zero records on replay. A separate check used the real retained PostgreSQL archive in read-only mode and a temporary SQLite destination. The first delivery copied 2,780 records, including 2,651 SENS source records, 65 discovery attempts and 64 discovery results. The second copied zero and returned the same bridge receipt, `radar-sens-bridge-3bb36ca62d1703b3f44ab97993ec4286badf257d91739e2083ae67a3411b8b6c`. The scheduled production destination was outside that replay.

A read-only comparison of the two configured PostgreSQL databases found the latest record of each SENS kind identical across both. The latest SENS source and discovery result were received at 12:03:17.067810 SAST and the discovery attempt at 12:00:02.246730 SAST. The dashboard database already held the same bridge receipt ID, received at 12:04:19.627545 SAST.

## Running dashboard and collection

The local dashboard at port 5000 was restarted twice during verification. The final listener was PID 15064. Health showed the configured PostgreSQL database available and mode RESEARCH. The paper endpoint reported PAPER and both endpoints returned `live_execution: false`. The four existing worker processes observed before restart were still present afterward. No browser session or collector was restarted for this check.

ViewPoint initially showed `BROWSER_UNAVAILABLE` with a timeout closing the Search for security dialog. Its existing worker subsequently reported `CHECKED` at 13:56:50 SAST. CSB, ETF_STX40, MTN, SSU and VOD imported, and NTU was already retained with an older completed bar. The monitor displayed `PARTIAL_SOURCE` independently of the running worker and collection check. A later poll showed `COLLECTOR_TIMEOUT` at 14:03:35 SAST after the per-request wait budget, with the worker still running.

An isolated headless Edge check opened the live VOD Radar indicator card after restart. The Five-minute section displayed a completed bar ending at 13:55 SAST and the close source `IRESS_VIEWPOINT_TABLE_CSV`. The retained VOD export was received at 13:56:16.395713 SAST with SHA-256 `49d507671d4280ad53b76893663570434537102b794f18bd25b9bdd280c48d70`. The System tab displayed the same collection check and per-instrument results.

The indicator card uses an indicator-only query on the existing local endpoint. The full-history response still serves existing clients. The integration check compares both views' indicator payloads and verifies the indicator-only query skips 30-minute aggregation. Two live reads during test activity returned identical provenance in 29.51 and 18.28 seconds. The indicator response was 159 kB, compared with 5.7 MB for the full VOD history.

## Tests and rollback

The Windows offline runner permits the internal loopback socket pair needed by asyncio. The full run reported 2,262 tests, five skips and zero failures or errors. The manual SARB browser integration and real loopback OAuth callback checks run separately from that runner. All five OAuth tests passed in the standalone fixture-backed run. The 48 focused Python checks, 25 Sasol protected-evidence checks, Radar JavaScript syntax check and Backtest Lab sector-selection harness passed. All nine frozen AI modules matched the starting revision.

Revert the R18 commit to restore the previous bridge, dashboard API and tests, then restart only the dashboard and refresh its page. With the bridge runner idle, preserve a copy of any continuation checkpoint before setting it aside. The bridge can replay from the archive while retaining immutable receipts. Issue a new replay only through the configured local paths. Keep the ViewPoint session, retained source files and existing receipts in place.

## Outstanding-issues sweep before HR

| Area | Next observation |
| --- | --- |
| ViewPoint completeness | Check repeated unattended market-open cycles for Top 5 plus benchmark, including the intermittently missing NTU bar and the search-dialog timeout. R18 observed one recovery. |
| Dashboard latency | Check indicator response time during normal trading and across retained-history sizes. R18 reduced the response and observed variable latency under concurrent load. |
| Scheduled work | Observe the next eligible unattended share and macro AI attempts. Review the Windows task's historical `0x800710E0` result and diagnostic logging. Confirm the next scheduled SENS delivery to the configured dashboard database. |
| Desktop alerts | Observe the transient Windows popup during a real eligible alert. Notification History delivery was verified in R12. |
| Manual trading evidence | Verify OST account tariff, units and broker-field mappings against actual source evidence. Exact daily fill history for the R10 workflow remains outstanding. |
| HR handoff | Review the [existing HR11 checkpoint](HR11.md) after the sweep and agree the next bounded research question using frozen historical evidence. |
