# ViewPoint collector recovery — 16 November 2026

## Observed failure

The existing signed-in collector timed out opening Periodicity. After the
operator selected five minutes, it reached the MTN table but a later click
timed out, including with Volume visible. Both MTN and STX40 returned
EXPORT_UNAVAILABLE and zero new rows. Earlier GUID-named temporary files
contained CSV columns; GUID storage names are normal Playwright artifacts
and do not prove a native filename validation failure. The exact live click
blocker remains unconfirmed. Separately, Windows computer control could read
accessibility text but failed to obtain click geometry or capture either
Edge or VS Code. No authenticated session was restarted for this patch.

## Change

- Avoid waiting for navigation after chart-control clicks; use normal focus
  and keyboard activation after a bounded pointer timeout.
- Wait for the actual download event even if the click times out. If no
  event arrives, attempt one keyboard download within a second bounded wait.
  Continue validating the native suggested filename against the requested
  exact JSE symbol; read the bytes from Playwright's temporary path.
- Bring the chart forward and check visibility of the five-minute chart.
  Preserve exact chart/table identity, Volume and existing import conventions.
- Return sanitized stage/type/reason diagnostics and successful filename,
  SHA-256, row count, receipt and latest retained interval clocks separately
  from source freshness. Raw page text, URLs and credentials are not logged.
- Isolate SQLite retention failures per instrument so the browser collector
  remains available for later requests.

## Validation and limits

Nine focused collector tests cover timeout/event handling, missing downloads,
keyboard fallback, native symbol mismatch rejection, GUID paths, real SQLite
retention with raw bytes/hash/volume and deduplication, and per-instrument
database failure recovery. The combined collector, adapter, monitor, intraday
integration and store run passed 49 tests; `git diff --check` passed. An
isolated headless Edge page demonstrated normal
keyboard activation of a pointer-obscured button and a native-name CSV
download read from its temporary GUID path. No broker connection was used by
these fixtures.

The already-running collector retains its old code. The operator explicitly
requested leaving the authenticated OST/ViewPoint session connected, so this
patch was not activated by restarting it. Live success, the exact IRESS click
blocker, and post-open freshness remain unverified. Historical pre-market
bars must remain historical. No signal, model, order or milestone promotion
is established by this patch.

## Authorized restart and live browser check

After the operator authorized one controlled restart, the patched collector
verified the existing flow through OST to a ViewPoint chart. An explicit MTN
refresh returned MTN=IMPORTED, 175 new five-minute records, all with volume,
and no rejected inbox files. The native file was
`MTN.JSE (20261113171000000 _ 20261112100500000).csv`; raw bytes are retained
in SQLite with SHA-256
`57c79d6f03dc8173ccf7c6ff2aa8741c7964ef3bd1275e72b2a7b74f5bbad229`.
The latest retained regular interval ended 13 November at 16:50 SAST;
the receipt was 16 November at 08:59:16 SAST. This verifies MTN export and
import of historical data before the open, not live freshness.

The accompanying ETF_STX40 export still returned EXPORT_UNAVAILABLE at
`verify five minute symbol`. Benchmark switching remains unresolved. The
collector and signed-in browser were left open after verification.

## Slow chart rendering isolated

Inspection after that timeout found the exact STX40.JSE five-minute chart had
finished loading. Exporting it through the same running collector then imported
179 records with native filename
`STX40.JSE (20261116090000000 _ 20261110142000000).csv` and raw SHA-256
`c05dacc2905f20661a152c61be877980ec7261c1b8d0d646a4ab0468cd711839`.
The chart switch had completed after the collector's 2.5-second wait.

The code now allows 15 seconds for exact chart-symbol verification. Queue
clients can recover older collectors without closing their browser: retry
only symbol-verification timeouts, one instrument at a time, at most two
recovery requests per failed instrument, within the original 90-second total
budget. Successful exports are not re-requested and all attempts are retained.
Download or database failures do not trigger this chart-specific recovery.

A live MTN request at 09:07:40 SAST retained its initial symbol timeout and
then succeeded on the recovery request: 175 records, native filename
`MTN.JSE (20261116090500000 _ 20261112101500000).csv`, SHA-256
`3cb46daffdcfb1c7f2c3b83e22ff9b2f88e6770939700fd591152404767e7560`.
Its newest 09:05–09:10 candle was provisional at receipt; this must not be
represented as a completed interval. The market had opened by this check.

Installed versions were Playwright 1.65.1 and Edge 157.0.4341.46. The collector
uses the officially supported `msedge` channel. The version numbers alone do
not establish an incompatibility; the live evidence identifies short chart
render waits as a concrete failure in this integration. No browser/package
upgrade was made and no additional broker login was needed for these checks.

## Dashboard API recovery verified

Restarted only the dashboard server to load queue recovery; the OST/ViewPoint
collector and browser remained connected. The actual MTN refresh API then
returned MTN=IMPORTED (175 records) and ETF_STX40=IMPORTED (179 records), no
remaining errors and zero rejected inbox files. It preserved the initial
STX40 symbol timeout and the successful targeted retry. Receipts were
09:10:26 and 09:10:38 SAST respectively. Native raw SHA-256 values were
`552c4aea6fc12a483fd0b7977cd7a62e70143d3a02e70949ba925d61258fe1a4`
and `7d8ec9576c877c10b9c0cbc491c3fe6e256a130fd9ad59dca3c836c51058ee2b`.
The 09:10–09:15 source candles were still provisional at receipt. The combined
collector/adapter/monitor/integration/store suite passed 53 tests, including
multi-symbol sequential recovery and preserved attempt evidence.
