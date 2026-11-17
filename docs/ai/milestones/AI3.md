# AI3 — connected share and South African macro preparation

State is QUEUED after AI2. Load mandatory repository context, `../CONTEXT.md`,
`../EXECUTION.md`, `../STATUS.md`, and AI1/AI2 evidence. Read the Strategy Radar
README/HIERARCHY for the existing decision-card and context interfaces. This is
one complete assignment. Protect Xebra/Zebra, the five-minute ticker, running
processes, source storage, tasks, ViewPoint settings and all frozen modules.

## Outcome

For an approaching confirmed event, the user sees an official date/countdown,
existing warning/preparation state, relevant retained sources and the latest
cited model expectation or explicit abstention in one reachable place. The
same item is connected to News & SENS and the instrument's research view.

## Load these implementation files

Read `market_intelligence/macro_calendar.py`, `macro_lookahead.py`, `macro_prep.py`,
`macro_expectations.py`, `calendar_expectations.py`, `weekly_brief_api.py`,
`scripts/macro_expectations.py`, `scripts/share_expectations.py`, the existing
macro calendar clock script, and relevant dashboard/radar rendering. Read
`research_calendar.py` and `calendar_outcomes.py` as interfaces only. These two
files are frozen. Reuse existing macro look-ahead/preparation and sidecar APIs.

## Implementation requirements

1. Join existing confirmed event IDs to preparation packets, official quotes,
   standing-rule sidecar attribution, model attempts/results and retained
   related SENS/news. Use the existing seven-day model eligibility window and
   event-family mappings. Make date-only precision and SAST timezone explicit.
2. PRIMARY macro enrichment covers SARB MPC, Stats SA CPI and retail sales on
   USDZAR/ZAR_RATES. Shares use the active registered share catalog. Preserve
   existing event families and US rows/warnings. This milestone creates no new
   source calendar, event confirmation or warning schedule.
3. An advisory expectation states what the retained evidence supports, a cited
   rationale, a condition that would weaken it, and unknowns. Keep ABSTAIN
   available. A calendar date alone cannot establish an economic outcome or
   direction. Validate quote membership and selected source IDs deterministically.
   Honor model response bounds and existing allowed expectation schema. Extend
   outside frozen modules only when a concrete UI requirement needs it.
4. Reuse existing 168h/48h preparation receipts and late-packet labeling. Link
   the 168h/24h/2h calendar warnings using their existing IDs and statuses. Missed
   pre-confirmation windows stay missed. Historical analogues use the same event
   family and existing local USDZAR five-minute data where available. Report
   exact coverage, missing intervals or no five-minute data for each date.
   No new ViewPoint capture or data-storage rule is introduced.
5. Show the latest preparation, advisory generation clock, stale-input state and
   next existing warning on the related card. Source/hash attribution for macro
   confirmation reads "Automated official-schedule sync". Model attribution
   reads "model-generated, advisory". Keep actual data/provider clocks visible.
6. Make share and macro panel refreshes independent of each other. A failure in
   one API must not erase the other results or the underlying calendar/news.

## Agent allocation and skills

The lead implements projections, expectation validation and linked UI. One
reviewer checks event-ID joins, clock/timezone arithmetic, citation membership,
historical analogue coverage and frozen-file isolation. Recommended skill is
`computer-use:computer-use` for the calendar-to-radar-to-source flow.

## Acceptance and evidence

- Tests cover confirmed share, SARB, CPI, retail, date-only event, no relevant
  news, ABSTAIN, stale expectation, quote mismatch, timezone boundary, missing
  analogue data and independent API failure. No AI result mutates calendar state.
- The existing real SARB/CPI/retail rows in trading are read without changing
  dates, confirmations or warning receipts. List actual IDs and linked packet
  counts. If those events have passed by execution time, display historical
  outcomes honestly and use future confirmed rows only if already registered.
- Run `test_macro_expectations`, `test_macro_calendar`, the current macro prep
  and look-ahead tests, `test_calendar_expectations`,
  `test_calendar_expectations_api`, and frozen checks. Fake model tests require
  zero real requests. Existing schema callers and old saved drafts still render.
- Browser evidence shows source quote, confirmation attribution, actual model
  state, relevant instruments, countdown or past state, and packet coverage.
  Demonstrate blocked/empty data states in isolated fixtures without modifying
  trading or the live processes. Record zero calls from reads.
- Update STATUS, commit and push, then continue AI4. Later unattended generation
  is recorded when an actual eligible idle event is processed.
