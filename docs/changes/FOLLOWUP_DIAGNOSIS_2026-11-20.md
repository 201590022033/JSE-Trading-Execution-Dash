# Follow-up diagnosis — 20 November 2026

## Daily capture and Radar cache

The 19 November morning source capture started at 07:30:15 SAST, before that day's market session. The audited 20 November snapshot at 07:19:50 SAST also predates the next scheduled capture. Replaying retained selection at that cutoff returned 17–18 November for ETF_STX40, MTN and VOD, all from ShareData. At 08:00 SAST on 20 November, the same loader selected 19 November for all three. Their new retained ShareData receipt clocks were 07:30:52.794479, 07:31:12.919090 and 07:31:37.326409 SAST respectively. The source refresh receipt is `runtime/local-swing-data/zebra-refresh-receipts/2026-11-20T053017.598478_0000.json`.

The three Radar daily-cache files still ended on 18 November. The ETF_STX40 cache recorded 07:14:35 SAST on 20 November. Passing its retained content to the benchmark cache reader at the 08:00 cutoff returned `CACHE_STALE` for the 18 November target and no target data for 19 November. The collector's source refresh and Radar's daily-cache prewarm are separate paths. The scheduled `scripts/collect_swing_data.py` refreshes Zebra sources and then runs the forward monitor. It does not prewarm the Radar daily-cache as part of that step. `RadarService._save_prewarm_locked` writes that snapshot on Radar's existing refresh and reconciliation paths. The already-retained 19 November records remove the need for a historical capture backfill. A later Radar cache refresh remains unverified.

## BTI and SASOL forward check

The collector's receipt stores `ValueError` only. Re-running the read-only path of `scripts.monitor_sector_forward.run(capture_current=False)` reproduced:

```text
scripts/monitor_sector_forward.py, line 18, run
    plan = read_plan(folder, plan_id, root)
application/backtest_lab/forward_monitor.py, line 36, read_plan
    raise ValueError('frozen implementation changed: '+name)
ValueError: frozen implementation changed: application/backtest_lab/strategies.py
```

Plan `e39b498c38944c793cf0ba5afeab919c36fec8fc9a03e8681b9151baaba38a45` expected `345ee6b14ca4c70a8b0d944d7df345d09c2d6c458f739bd9660829e16bb331bd`, matched by the file at `17d34a0`. The current checkout yielded `677d8276414bf11a92e42709bc87d270081096ca8c4ce3e49a5d2f8559b32937`. LF normalization did not restore the expected hash. The change added a version parameter, made v1.3.1 the default and bound that version to prior median volume. The old v1.3.0 keeps the average as an explicit option. The guard fails before market data is loaded, so it cannot account for the missing share cache session.

## SASOL refinement

The stored PostgreSQL definition on 55432 is `sasol-definition-c01ee81a9c8b72386631c447fbf30479bf064019fd5d7af4b3d4089568318787`, registered 20 October 2026 at 09:16:19.502402 UTC. The configuration matched exactly. Of nine recorded implementation hashes, these three differed. The reference commit matches the old hash for that file independently.

| Module | Stored | Current | Reference commit and material differences |
| --- | --- | --- | --- |
| `application.opportunities.swing_technical` | `eb757f6da821ec8a7455a8ffac0544141e63e915640e2e10c278cdd8c74ea567` | `c385e65b0b121093e069e064ced795eb8981d7b2b01cf24166eecb7ab9ffeafd` | `0de1073`. EMA20 reclaim lookback and feature profiles, prior median volume and changed snapshot metadata. |
| `application.opportunities.swing_research` | `9b8505c0885a22c72f088600ec7f5a9a4c243781f8a15d733b7ab1d426b7a725` | `acf94210a076056f42580d4a284f4b82b04d495f7a4830814d6cfa8b891207ed` | `2d72089`. Sector-aware historical research, expanded evaluation and status, and proposal/provider handling. |
| `application.opportunities.public_research` | `e10603f0fc56ec9fd4903c89df2a26c4ed8320f106b9e17f7be97da17253e0b6` | `56b9569eaa80cca78dd9595c817f78f2e726576faa25c6a6f6fa99baaee832a9` | `d48cfc1`. The public list now uses shared sector and industry classification. |

Possible decisions are to retain the block and view historical outputs, inspect the exact frozen dependencies in an isolated reference checkout, or design separate registrations with current dependencies and explicitly prospective starting dates. Each original guard and record remains in place. Re-enabling either monitor against historical rules requires a verified complete dependency tree, since individual hash matches do not establish an executable reference revision.


## Verification and deployment gate

Previous accepted baseline was 2,298 tests, five skips and zero failures. The first follow-up suite had 2,298 tests, five skips, one failure. With the two bounded-read regression tests, the next suite had 2,300 tests, five skips, one failure, and 2,294 passes. Both failures were `test_explicit_saved_key_session_is_in_memory_and_bounded` in `test_uim5_oauth.py`. Windows monotonic-clock arithmetic produced `1800.0000000000005` seconds against a strict `1800` threshold. The test passed on its own from master. The OAuth test and implementation are identical to master. The new test counts precede the final UI-only checks. The protected manifest checked 54 artifacts without failures.

Before figures are the previous running audit under its workload. After figures are isolated Flask requests with the existing retained inputs. Differences in load prevent a direct speedup claim.

| Read | Before | Follow-up observation |
| --- | --- | --- |
| VOD Research indicators | 31.3 s | 7.185 s cold and 0.001 s retry from memory |
| Shared freshness | 65 s client timeout | Configured 8 s wait bound and retry state, route timing unmeasured |
| Historical readiness | 65 s client timeout | First three waits 8.006, 8.010 and 8.051 s. A later retry settled in 0.001 s. |
| Zebra field coverage | 65 s client timeout | VOD first wait 8.026 s. A later retry settled in 5.698 s. This limits request wait while aggregation continues. |
| Daily volume reconciliation | Had failed to settle in the prior coverage audit | VOD 0.121 s cold and 0.001 s from memory. The SASOL cache-only view returned no data because that instrument had no Radar daily-cache snapshot. |

Flask allows each query one active task at a time, with one or two concurrent reads per endpoint and successful replies held in memory for 60 seconds. No new persistent cache was introduced. Protected files and saved replay data are outside this diff.

The merge gate failed. The proposed rollback tag is `pre-followup-2026-11-20`. The tag, merge, dashboard-only restart, smoke test and push are pending. Dashboard startup invokes Radar reconciliation and SQLite writes, including resetting outstanding jobs and pruning intraday data. Clarify explicit authorization for normal startup writes before attempting deployment. Read-only inspection still found 21 retained five-minute alerts. Configuration was enabled, 300-second interval, desktop notifications enabled, autostart disabled, `intraday_5m_research_v1`.

## Manual verification after an authorized deployment

1. Open Radar on VOD. Check selected-setup momentum, hypothetical sizing with a user-entered stop and budget, the W07 state and Validation line, and the checklist note beside its count. On a daily case with two or fewer evaluable components, confirm the value still renders and its rank is dimmed with the thin-input count. Switch to the five-minute lane and confirm its independent settings and 21 retained alerts.
2. Open Research indicators and use its Refresh control if it times out. In News and SENS choose Check status. In Backtest open Data quality and run Historical research data. Inspect Zebra field coverage and daily volume reconciliation for VOD from Technical View. Check that each settles to a result, retryable timeout or a no-data message. Capture cold and repeated request timings in the browser network panel.
3. Open Backtest. Select VOD and a saved portfolio replay. Check the four steps, result scope, exact W06 sample, trade floor and the full-run totals heading. Every default Trades row must be VOD with an Instrument column. Price chart should show VOD. Enable Show whole portfolio and verify broader Trades scope and the instrument chart picker. Disable it to return to VOD. Repeat for MTN. A share with no saved result should show an explicit empty state.
4. Open saved-run metadata for a replay configured with a simulated date and check the replay cutoff label. Open Research detail to check the instrument in the historical funnel title and its selected-share mismatch notice. Exercise sector selection, windows and alternatives. Check the fixed instrument in the Sasol panel and a no-data or timeout outcome for an unavailable panel. Browser fixtures exercised the sector timeout and retry. Full live settlement for all research and external-context panels remains unverified.
5. Open System. Verify the five-minute worker state and last retained alert beside existing monitor controls. The retained last alert was 19 November at 16:33:50 SAST. A later observation may legitimately differ.


## Follow-up decisions and startup dry run

The owner elected to retain the frozen SASOL refinement and BTI/SASOL forward blocks. The cause in each case is implementation drift after registration. No guard, frozen hash or registered definition was changed.

After the 07:30 SAST source capture, a direct read of the running dashboard's Radar-cache files at about 07:53 SAST found VOD, MTN and ETF_STX40 still ending on 18 November. The 19 November ShareData bars already exist in retained input. No restart was used in this check. A proposed display/cache-only change is to watch the successful local Zebra refresh receipt's identity and coalesce one bounded prewarm for the current watches and their benchmarks. Use existing retained inputs and the existing atomic cache writer. On result failure or incomplete data, keep the older snapshot and report its date. Avoid watch reconciliation, intraday pruning, provider recapture and all database writes. Verify with an offline clock and file fixture, then observe a natural 07:30 capture. The trigger change remains a proposal.

At approximately 07:53 SAST, seven Radar SQLite files were copied by SQLite's backup API from read-only sources into a dated folder, including the intraday store. Each destination passed `PRAGMA integrity_check`. The manifest contains a SHA-256, byte size and per-table counts, and all destination hashes were reread and matched. The startup-prune projection used read-only connections, the integrity-checked ranking snapshot and the 10-session cutoff of 9 November. It identified zero eligible bar rows and zero orphan raw responses, including for the retained alert instruments BTI, DTC, MTN and VOD and benchmark ETF_STX40. Monitor event IDs were 1–21. There were no queued or running Radar daily jobs at inspection. Repeat the projection immediately before any authorized restart because runtime inputs can change.
