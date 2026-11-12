# ViewPoint CSV import and session review

Date: 12 November 2026  
Status: Manual raw-evidence import verified; source qualification and idle-timeout measurement remain open.

## Import

The owner-supplied `MTN.JSE (20261112095500000 _ 20261112092000000).csv`
was imported through the local Strategy Radar endpoint into
`runtime/local-swing-data/strategy-radar/intraday.sqlite3`.

- Source file: 823 bytes; SHA-256
  `D64F5286D80D81995F75343EF48BCEFF96FF137D2C278EE8F63CDD4236A4BCD3`.
- Eight raw rows span 07:20–07:55 UTC (09:20–09:55 SAST); timestamps are five
  minutes apart.
- File modification time (07:56:16 UTC) and local import receipt
  (08:14:23 UTC) are retained separately from source timestamps.
- Rows are manually supplied, provisional, unknown-clock and
  `UNVERIFIED`-unit evidence. Raw OHLCV strings are retained, but canonical
  fields remain null. The sample creates zero aligned bars and cannot feed
  shadow evaluation or daily Zebra ranking.
- Manual local research use was authorized. Entitlement or permission for
  automated collection was not established.

The upload path requires an exact JSE symbol mapping, an explicit raw-only
confirmation and a bounded CSV. The import preserves raw response bytes by
hash. The dashboard exposes the retained values with their unverified status;
it does not relabel them as normalized prices or exact volume.

## Save-step and session observations

The CSV appeared in the local Downloads folder after the manual Save action.
The browser automation did not expose a Save dialog, so it is unknown whether
the pause came from a browser confirmation, an application download prompt or
another focus-dependent step. No download preference was changed.

At approximately 10:07 SAST, both the OST and ViewPoint pages were accessible.
The successful login start time and a controlled idle interval were not
recorded; consequently this observation establishes neither the idle timeout
nor a keepalive option. No automated mouse movement, page polling, login
automation or session keepalive was attempted. Measure only through a
user-controlled timed observation or obtain the provider's approved session
policy before considering any persistence behavior.

## Verification

The focused `test_strategy_radar_intraday_integration.py` file passed 10 tests
with the repository virtual environment. Tests verify CSV shape and symbol
validation, raw-only handling, chronological output for reversed input rows,
and exclusion from scoring. `node --check static/js/strategy-radar.js` and
`git diff --check` passed.

See the [Strategy Radar M10 milestone](../strategy-radar/milestones/M10.md),
[checkpoint](../strategy-radar/CHECKPOINT.md) and
[source qualification](../strategy-radar/M3_SOURCE_QUALIFICATION.md).
