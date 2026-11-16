# Macro look-ahead and preparation evidence

Prior clock/marker commit: 29fe412. Runtime logs, dumps, captures and .env
remain ignored. Frozen research_calendar.py remains byte-identical to HEAD.

## Look-ahead

Real local PostgreSQL trading run produced macro-lookahead-2026-11-16:
LOOKAHEAD_RECORDED, counts_by_day 2026-11-18=1 and 2026-11-19=1, no capture
failures. Second run returned ALREADY_RUN_TODAY without another sync.
New modules append receipts; --refresh explicitly requests capture refresh
subject to the existing two-attempt daily browser cap.

S4U tasks Trading System Macro Lookahead (five-minute gated checks) and
Trading System Monday Macro Lookahead (Monday 06:00, --force) installed through
an elevated transcript launcher. The five-minute task ran on 16 November
13:42 SAST with LastTaskResult 0. Monday task is enabled, next run 23 November
06:00; the future Monday trigger itself has not been observed.

Actual News/SENS browser DOM showed the last look-ahead receipt. Isolated
browser replay of stale/failed-source test data showed six red role=alert
messages, including older-than-26-hours and BLS PARSE_FAILED. This was a
fixture replay, not a claim the live database currently has those failures.
Screenshots retained locally as lookahead-health.png and stale-failed-warning.png.

## Preparation

Real SARB packet macro-prep-6d5a4190fc042958084718902d865c6df712221c756313cc62f82f1086e387ea
was created at actual run time, state LATE_PACKET, hours=168. It contains the
source-quoted event and instruments. USDZAR five-minute cache coverage is zero,
and no prior same-family event dates are retained, so analogues=[] and no
price statistics are invented. A daily USDZAR CSV exists in analysis/data/hr2;
it is not an intraday substitute. Entitled historical five-minute USDZAR bars
and verified release instants are needed for genuine analogue windows.
The unattended clock now invokes preparation; packets deduplicate by event
and lead window. Tests cover both deadlines, restart deduplication and a
prior same-family event with explicitly missing five-minute data.

## Extended capture coverage

Uncapped future registration against existing captures ran twice with zero new
source/event/confirmation/sidecar records on both runs. Captured dates: ZA CPI
18 November; BLS monthly January–December 2026 (only December remains future);
FOMC 9 December; SARB 19 November. These pages do not establish later months.
Further SARB/Stats SA months, January 2027 BLS and other FOMC meetings remain
UNVERIFIED; this is not comprehensive annual coverage.

## Limits

The clock/marker work is active, and no broker or model operation was requested.
Optional enrichment is explicitly UNAVAILABLE. No forward warning due time,
logged-out desktop capture, future Monday trigger or historical price-window
statistics are claimed proven. The separate legacy Sasol frozen-definition
mismatch is untouched and is not resolved by passing offline guard tests.
