# ViewPoint CSV import and session review

Date: 12 November 2026  
Status: Owner-accepted normalization completed for local research; exact idle-timeout measurement remains open.

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
  `UNVERIFIED`-unit evidence in the original import. The owner subsequently
  directed normalization using a documented interpretation; the earlier rows
  remain retained and are hidden from the merged view once their normalized
  versions exist.
- The eight normalized bars use ZAR cents converted to rand, integer Volume as
  shares, and the UTC `Date` as each interval start. Each bar retains the
  convention ID and the original source bytes/row strings remain hash-bound.
  The normalization is explicitly an owner-accepted interpretation, not a
  representation that IRESS certified those semantics.
- The bars are available for local research shadow only. They do not enter the
  daily Zebra ranking or broker execution path.

The upload path requires an exact JSE symbol mapping, explicit operator
acceptance of the interpretation and a bounded CSV. The import preserves raw
response bytes by hash and exposes normalized bars with their convention and
lineage.

## Normalization continuation — 12 November 2026

The retained MTN daily closes around R230 agree in scale with the CSV values
around 23,000 and the ViewPoint display, supporting a 100:1 cents-to-rand
conversion. Integer volumes are treated as shares as exported. UTC timestamps
advance at five-minute intervals and align to the JSE session; the operator
accepts them as interval starts. These assumptions are now explicit in
`OPERATOR_ACCEPTED_VIEWPOINT_CSV_CONVENTION_V1`.

The cache now contains eight normalized 5-minute bars (09:20–09:55 SAST),
with prices converted to rand. The raw-only earlier records remain persisted,
but the read/merge view deduplicates them against normalized records for the
same CSV hash. The last bar ends at 10:00 SAST and the original import was
received at 10:14:23 SAST; ordinary freshness checks therefore keep it from
appearing as a current five-minute observation. The source hash and raw bytes
did not change.

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

The focused `test_strategy_radar_intraday_integration.py` file passed 11 tests
with the repository virtual environment. Tests verify CSV shape and symbol
validation, operator-accepted normalization, chronological output for reversed
input rows, duplicate raw-record suppression and shadow eligibility.
`node --check static/js/strategy-radar.js` and
`git diff --check` passed.

See the [Strategy Radar M10 milestone](../strategy-radar/milestones/M10.md),
[checkpoint](../strategy-radar/CHECKPOINT.md) and
[source qualification](../strategy-radar/M3_SOURCE_QUALIFICATION.md).
