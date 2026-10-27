# IRESS 600-session history completed

27 October 2026. The signed-in ViewPoint session supplied the native SOL.JSE daily
OHLCV export. **The 600-session target is now met**, and the accepted local
PostgreSQL dataset contains the separate 600-bar IRESS series.

The narrow chart layout hid the 5Y/All controls. Widening the view exposed them.
All initially selected monthly candles; periodicity was explicitly restored to
1 D. Expanding the visible daily range then supplied 645 rows, dated 28 March 2024
through the live 27 October 2026 row. Additional Columns exposed exact whole
volumes. The native Download control saved the CSV without altering its bytes.
Browser sizing was restored afterward.

Actual download completion: **27 October 2026 14:39:51 SAST**. The CSV is 57,375
bytes; SHA256 `dd44e2c465023d3ec774a33176fcca53596543d68045ab4b63c682eb118be39d`.
It contains 644 completed daily rows plus one live row. The existing parser excludes
27 October and retains the latest **600 completed sessions, 4 June 2024–26 October
2026**. The 44 earlier completed rows remain in the unchanged raw archive. All
native prices were checked as exact integer cents and all volumes as whole source
units. No transformation or row grafting was needed.

The existing source installer, local collector and accepted loopback PostgreSQL
ingress were used. Database readback confirms 600 IRESS bars and the exact source
hash. Share and OST Top40 endpoints align on 26 October, and worker-input readiness
passes. All five separate OST series still have 600 bars and their missing Open
fields remain null. Previous source artifacts were not overwritten: all 64 earlier
archived source/capture hashes remain unchanged, with mutable pre-import snapshots
also preserved in a dated diagnostics folder.

## Verification

- **79 focused tests pass** in 2.726 seconds.
- Earlier 324-session IRESS capture versus this capture: **zero OHLCV revisions**
  on all 324 overlapping completed sessions.
- Independent OST versus IRESS: **600/600 closes match**; seven highs, nine lows
  and ten volumes differ. Fifteen distinct sessions differ on high or low. These
  remain source-semantic differences, not reasons to splice providers.
- Saved request projection reports `daily_ready=true`, `benchmark_aligned=true`
  and `history_target_met=true`; the history shortfall is **zero**.
- Price-only clean observed-session samples remain IRESS Sasol **6/5/4**, OST
  Sasol **3/2/1**, and OST Top40 **4/3/2** at the 3/4/5-session horizons. Extending
  history at the same latest session does not fabricate new prospective outcomes.
- The existing paired experiment remains operational with two observed sessions,
  two episodes and zero informative trade pairs. No paper worker or model batch
  was forced by this import.

The archive grew by 719,624 bytes, including native source, candidate/capture and
preservation snapshots; the download adds 57,375 bytes in Downloads. Measured
PostgreSQL size grew by 81,920 bytes. Browser cache/WAL/allocated blocks were not
isolated. No files were deleted.

The 600-row gap is closed. The stale canonical Top5 ranking, SENS/corporate actions
and source definitions remain separate requests. These do not invalidate this
completed acquisition or change historical AI/adoption gates. No broker order,
chargeable quote request, cloud upload, credential storage or strategy change
occurred.
