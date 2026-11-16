# Macro scope and News/SENS health verification

Separate USDZAR/ZAR_RATES/DXY scope and hash are returned by a new read-only
macro-health endpoint. The original issuer catalog and frozen calendar
implementation remain unchanged. Confirmed macro events include the sidecar
attribution/hash, countdown to their date-only anchor, and SAST warning times.

Real trading database: four confirmed macro events; two within seven days.
Stats SA CPI 18 November: exact row explicitly names October 2026 data.
US CPI 10 December: exact captured row explicitly names November 2026 data.
FOMC 9 December: immutable raw rendered capture plus separate derived source
combining December 2026 heading and December 8–9 meeting range. No release
time was invented. SARB and ZA CPI 168h receipts remain missed-before-confirmation.

The restarted app's actual News/SENS page was opened in the installed Edge
Playwright stack. DOM showed count 2, four macro events, countdowns and
Automated official-schedule sync labels with hashes. Screenshot:
runtime/macro-calendar-captures/live-health.png. The source-status rows were
added afterward and have JavaScript syntax validation, not separate visual QA.

An authorized empty PostgreSQL scratch database macro_health_stage3_test was
created, migrated, queried with the same health reader, and dropped. Its exact
response was replayed into an isolated browser page (not the live dashboard's
database connection). DOM showed count zero and six missing/stale/empty
warnings. Screenshot: runtime/macro-calendar-captures/empty-health.png.

Coverage limits: captured Stats SA page lists only the current visible CPI
release; BLS capture is the 2026 annual calendar, not January 2027. No claim of
exhaustive 60-day calendar coverage. No Monday macro look-ahead/preparation
packet implementation is included in these scope/display stages. The countdown
is a News/SENS macro event list, not a plotted marker on the price Strategy
Radar canvas. Source-clock automation firing at future due times remains to
be observed. No model or trading action was performed.
