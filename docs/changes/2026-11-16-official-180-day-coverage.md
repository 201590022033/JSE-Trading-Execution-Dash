# Official-only 180-day coverage

Owner disabled IG/EODHD use. No calls to either provider were made. The
previously enabled Radar monitor was paused to honor the attended-only
ViewPoint rule; the signed-in collector/browser were left alone.

New official pages were discovered and captured through installed Playwright
Edge, without stealth or challenge bypass: BLS 2027 annual schedule, SARB MPC
upcoming announcements and Fed annual FOMC calendar. Each returned HTTP 200
with no visible challenge. Raw HTML stays ignored; visible fixtures and raw
HTML hashes are checked in. Existing 2026 BLS, November Stats SA and December
Fed captures were reused.

Real trading database has 28 active confirmed events within 180 days:
SARB Nov/Jan/Mar; ZA CPI and retail Nov; US CPI/NFP/PPI Dec–May;
FOMC Dec/Jan/Mar/Apr; FOMC minutes Dec. Later dates outside 180 days were not
registered. Stats SA PPI/GDP/QLFS remain unverified: no dated rows appeared
in the captured current-month schedule. Future monthly absence is displayed
as no captured date, not an assertion that a release is expected that month.

An initial annual Fed parse stopped on an abbreviated historical month; parsing
was corrected. A BLS label error included Employment Situation of Veterans as
NFP. The rule now requires Employment Situation for. The misclassified event
and redundant identities were cancelled via public calendar functions; history
and parser-correction discrepancies are retained rather than deleted. Final
active NFP dates are Dec 4, Jan 8, Feb 5, Mar 5, Apr 2 and May 7. Final repeated
sync created zero records. Full source hashes/quotes and sidecars stay in trading.

Official sync is called by the existing daily look-ahead, reuses captures less
than seven days old, and supports explicit refresh within the browser cap.
Revisions preserve the original event identity for the same named publication,
including cross-month date moves. Different-body date revisions append a
discrepancy; identical-body parser corrections are labelled separately.

Health API/UI includes per-family captured months, next month lacking a captured
date, source refresh times and discrepancy history. Macro capture expiry is now
seven days; the daily look-ahead freshness deadline remains 26 hours. Live DOM
verification and screenshot: runtime/macro-calendar-captures/coverage-180-days.png.
Annual marker SVG height expands to avoid clipping added events.

275 relevant tests passed, including real-visible-text fixtures, unrelated
publication rejection, exact sidecar pairing, cross-month revision/idempotence,
calendar, Sasol refinement and source-price guards. Frozen research_calendar.py
diff is empty. Phase 0C FX probes and historical statistics have not been run
as part of this calendar work. Future weekly execution/reschedule arrival and
actual warning delivery at due instants remain observational acceptance items.
