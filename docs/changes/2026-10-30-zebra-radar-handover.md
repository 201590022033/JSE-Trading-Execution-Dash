# Zebra handover, historical freshness and radar public prices

The earlier zebra panel lived in the research repository and was not consumed by
the execution dashboard. `scripts/zebra_handover.py` now verifies its content
hash and derives a source-labelled close handover. It retains each close's raw
and row hashes, actual acquisition time and reconstructed availability. The
read-only `/api/v1/backtest-lab/zebra-history` and paged `/observations` routes
expose the retained history independently of the age of its latest capture.
The Backtest Lab shows coverage and the last observed close. The existing panel
contains 8,467 usable closes through 20 October 2026. Five later source-verified
IRESS closes extend the derived handover to 8,472 through 27 October. Their
individual source hashes and clocks are retained, and older rows are not
rewritten. It is not a current quote. The scheduler rebuilds the handover from
the configured source panel and validated local IRESS dataset without modifying
the frozen original panel.

Historical Swing funnel refresh now saves the latest as-of technical snapshot,
so Trading Strategies and Technical Intelligence can display it even when a
current source is unavailable. Daily collector refreshes it after an accepted
local source update and retains the previous output if refresh fails. Current
worker, order and prospective outcome freshness requirements are not changed.

The old collector refused to proceed once all OST receipts expired and had no
Yahoo fallback in that branch. Its daily scheduled task now first runs a
separate, bounded radar-linked Yahoo research capture before that branch. The
capture uses only explicit registered issuer links in active watches or source
leads, at most ten per run, prioritizing missing/old captures. Unmapped and
deferred identities are reported, not guessed. The task stores append-only
normalized provider snapshots and acquisition clocks; raw Yahoo HTTP bytes are
not retained. Each share can fail independently. The 5-year Yahoo request
does not guarantee 600 rows; it is a research supplement, not an OST/IRESS
replacement or an upload. Close eligibility uses 17:20 SAST as an explicit
research convention, not proof of provider finality. Intraday rows stay in the
capture but are not presented as completed closes before that time. Source
revisions, exchange exceptions and adjustment basis remain unverified.

On 30 October an initial one-year public-capture check returned 250 completed
closes each for ABSPJ and IMPJ, latest 28 October: Yahoo had not provided 29 October
in those results. The subsequent five-year check returned 1,248 completed
closes for each, still ending on 28 October. Both are available through the read-only per-instrument
history endpoint. Other issuers, including BVT, need explicit catalog mappings;
the radar does not currently supply linked identities for every headline.
Scheduling uses the existing local task, observed Ready with the next 07:30
run. Login-dependent IRESS/OST extraction is not automated by this change.
New Yahoo captures remain separate from the Sasol handover: automatic Yahoo
fusion, wider-universe replay and changing current trading gates are outstanding.

The focused suite passed 72 tests, and the final changed capture/handover tests
passed separately. The offline suite ran 1,663 tests with two failures in
`test_sens_discovery_bridge`: those tests use the actual wall clock and expected
a scheduled 08:00-or-later run while the suite ran before 08:00 SAST. The
original tests were not changed. Browser viewport checks remain outstanding.

## Freshness audit: different purposes

| Path | Existing behavior | Effect and follow-up |
| --- | --- | --- |
| `ost_data.fresh_charts` and `supplemental_data.current_research_charts` | Four-day receipt age | Removes whole charts from current worker inputs. The new historical views retain earlier observations; this worker rule still needs a session-aware redesign. |
| `swing_technical.usable_bars` | Last bar older than four days raises an error | Current snapshot becomes unavailable. New historical snapshot evaluates at its own last observation, keeping its actual historical date. |
| `swing_research` worker | Dataset older than four days stops the run | Keeps a stale input out of current decisions but also prevents independent historical work in that worker. Do not silently reuse old prices as current; separate the two uses. |
| `research_data_requests._coverage` | Receipt must have been acquired on the current SAST date | Requests a fresh download even where the latest completed close is unchanged. This is an acquisition-maintenance flag, not proof that the existing prior close is invalid. Session-aware readiness remains to be implemented. |
| `calendar_outcomes` and `sasol_refinement` | Four-day limits on prospective endpoints | These protect existing registered prospective comparisons. They have not been changed or retroactively altered by the historical route. |
| `collect_swing_data` | No fresh OST charts terminates the primary collector branch | New public radar capture and zebra handover run first and remain available independently; the existing live/upload branch still stops rather than substituting another provider. |
| SENS source clocks | Source/event routines use publication, receipt and freshness checks for their particular operations | Historical source material remains archived; event-specific future facts must still not enter an earlier decision. This audit does not claim every SENS display is repaired. |
