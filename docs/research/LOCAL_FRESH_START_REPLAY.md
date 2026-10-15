# Local fresh-start retrospective: actual receipts, not historical admission

15 October 2026. This is an offline, read-only recalculation over retained local receipts. The reproducible script and JSON result are ignored private artifacts at `runtime/local-migration/2026-10-15/audit_fresh_start_receipts.py` and `fresh-start-replay-audit.json`. It uses the existing `swing_technical.snapshot` and `prospective_prices` functions at Git `03fbc17aa1db08490dcaa41b4aeb9f94fe795d81` (technical code SHA256 `e6e6a979b1f43972ed2e16fb22cdf6bd28bcc8f1a8ee2dbfacf24af90a5099eb`). No repository ledger, frozen decision, worker, model or broker operation was run.

## Saved evidence and genuine availability

Seven immutable IRESS Sasol captures, acquired 7, 8, 9, 12, 13, 14 and 15 October, each anchor only their newest completed session: 6, 7, 8, 9, 12, 13 and 14 October respectively. The 14 October evening receipt legitimately anchors 13 October; the separate 15 October receipt anchors 14 October. Five OST Top40 captures anchor 7, 8, 9, 12 and 14 October, and four OST Sasol captures anchor 8, 9, 12 and 14 October. Their older history rows were visible when each export was acquired, but are **not** past point-in-time receipts. All three provider-specific capture streams report zero observed revisions.

The latest imported local dataset contains only OST Sasol/Top40 as canonical HLCV and separate full IRESS Sasol OHLCV for research. Four validated v3 dataset snapshots are retained locally in `runtime/local-swing-data/pending-uploads/`: 12 October, 13 October, and two successive 15 October snapshots, each with its original observation time and file hash. Recorded hosted upload attempts on 12 and 13 October returned HTTP 404; the final 15 October snapshot was explicitly retained without hosted upload. None is evidence of hosted learning or a fresh session today merely because it can be read now.

## Numerical replay at actual acquisition times

The table recalculates the frozen candidate thresholds from each IRESS capture. “At capture” uses only benchmark receipts already acquired at that exact instant. “After paired OST” waits until a separately acquired Top40 receipt for the *same completed session* exists; it never backdates that benchmark. `PARTIAL` means the aligned benchmark was unavailable, not a negative setup.

| Sasol session | At IRESS acquisition | After same-session Top40 acquisition | RSI14 | Relative volume20 | Candidate outcome after pair |
| --- | --- | --- | ---: | ---: | --- |
| 6 Oct | PARTIAL, no benchmark receipt | none | 65.01 | 0.754 | unavailable |
| 7 Oct | PARTIAL, Top40 acquired later | AVAILABLE | 68.05 | 0.687 | no setup; volume condition failed |
| 8 Oct | PARTIAL, Top40 acquired later | AVAILABLE | 74.83 | 1.059 | no setup; RSI condition failed |
| 9 Oct | PARTIAL, Top40 acquired later | AVAILABLE | 71.20 | 0.793 | no setup; RSI and volume failed |
| 12 Oct | PARTIAL, Top40 acquired later | AVAILABLE | 73.16 | 0.681 | no setup; RSI and volume failed |
| 13 Oct | PARTIAL, latest Top40 was 12 Oct | none | 74.94 | 1.160 | unavailable |
| 14 Oct | AVAILABLE, Top40 was already acquired | none needed | 75.93 | 0.493 | no setup; RSI and volume failed |

This is a **descriptive numerical rerun at genuine local acquisition clocks**, not a historical B5 engine replay, actual trading decision, or causal learning cycle. The source's older history may contain provider revisions before acquisition; only the seven anchor sessions support the forward-observation claim. The source price/action/volume definitions, exchange calendar and historical availability remain unverified. The candidate filters are shadow-only and their costs, fills and stop execution are not established by this computation.

The existing provider-specific prospective price labels yield IRESS Sasol clean counts of **4/3/2** for 3/4/5 observed-session horizons, with **3/4/5** still pending. The corresponding OST Sasol counts are **1/0/0**; OST Top40 counts are **2/1/0**. IRESS's clean cohort means of +4.4031%, +5.9551% and +8.8379% subtract only an illustrative 10 basis points. These observations overlap heavily, arise from one rising stock over one week, and do not measure the candidate setup's performance (the available paired snapshots show no setup). No strategy edge or model training claim follows from them.

Two retained learning overviews, taken 8 and 9 October, show 31 and 33 decisions in their respective bounded read windows, **zero matured** and all 3/4/5-session outcomes pending; both report `OST_SOURCE_SEMANTICS_UNVERIFIED`, real-data backtest admission false and automatic promotion false. These files are old read-only views of the previous ledger, not records in a newly initialized local PostgreSQL lineage. The local SQLite backup is likewise not a copy of the hosted ledger.

## Safe continuation boundary

For a fresh local lineage, start prospective processing only from a newly observed, valid source session after local ingestion and worker readiness. Archive the 7–15 October snapshots as historical receipts with their actual timestamps; do not submit them to a fresh worker as if newly captured, splice IRESS opens into OST, or manufacture prior decisions/outcomes. The separate IRESS chart can continue to supply current descriptive numerical research after a fresh capture and aligned benchmark. Historical AI/B5 admission remains false and live execution remains disabled. A genuine strategy evaluation still needs independently resolved corporate-action and source semantics, point-in-time coverage, realistic costs/fills and sufficient forward samples.
